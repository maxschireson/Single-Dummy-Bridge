"""Export replay-validated, whole-game policy-clean data for predictive fitting."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.auction_policy import encode_decision
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board, Game, card
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.runner import replay
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

V4_POLICY='e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed'

def permitted(spec):
    return spec.get('artifact_sha256',{}).get('policy') != V4_POLICY

def candidates(run, manifest, paths):
    bots=manifest['bots']
    if manifest['schema']=='gen4-hybrid-mix-v1':
        for path in paths:
            receipt=run/'receipts'/(path.name.removesuffix('.json.gz')+'.json')
            info=read(receipt) if receipt.exists() else read(path)
            x,y=info['pair']
            if not all(permitted(bots[v]) for v in (x,y)):continue
            r=read(path)
            if receipt.exists() and sha(path)!=info['episode_sha256']:raise ValueError('Receipt changed')
            if r['pair']!=info['pair']:raise ValueError('Pair mismatch')
            for room,e in sorted(r['unique_tables'].items()):
                yield path,r,e,dict(candidate=x,environment=y),'unique_tables.'+room
    elif manifest['schema']=='gen4-component-ablation-v1':
        for path in paths:
            r=read(path)
            for version,match in r['matches'].items():
                if not all(permitted(bots[v]) for v in (version,'3')):continue
                for room,e in enumerate(match['rooms']):
                    yield path,r,e,{version:version,'3':'3'},f'matches.{version}.rooms.{room}'
    else:raise ValueError('Unsupported source schema; explicit actor mapping required')

def validate_game(e, actor_bots, manifest):
    bots=manifest['bots'];replay(e)
    if e.get('status')!='ok' or any(t.get('status')!='ok' for t in e['tables']):raise ValueError('Incomplete game')
    active={actor_bots[role] for role in e['assignments']}
    if not all(permitted(bots[v]) for v in active):raise ValueError('Forbidden policy participant')
    for v in active:
        if e['versions'][v]!=bots[v]['identity']:raise ValueError('Wrong participant identity')
    board=Board.from_dict(e['board']);family=deal_key(board.hands,True)
    if e['family']!=family:raise ValueError('Changed family')
    stats=Counter(tables=len(e['tables']));encodings=0
    for table in e['tables']:
        game=Game(board)
        for action in table['actions']:
            stats['actions']+=1
            spec=bots[actor_bots[action['player']]]
            if not permitted(spec):raise ValueError('Forbidden acting policy')
            estimates=action.get('estimates')
            if estimates:
                stats['actions_with_pimc']+=1
                for value in estimates.values():
                    for key in ('utility','gap_to_best','declarer_tricks'):
                        if not math.isfinite(value[key]):raise ValueError('Invalid PIMC estimate')
                proposal=action.get('proposal_probabilities',action.get('behavior_probabilities',{}))
                eligible=[c for c,p in proposal.items() if p>0]
                if any(c not in estimates for c in eligible):raise ValueError('Missing eligible estimate')
                probabilities=action.get('behavior_probabilities',{})
                probability=probabilities.get(action['card'],action.get('selected_probability'))
                if probability is None or not 0<probability<=1:raise ValueError('Missing chosen behavior probability')
                if len(eligible)>=2:
                    stats['eligible_policy_decisions']+=1
                    if encodings<2:
                        x,cards=encode_decision(game.observation(),action)
                        valid=x['mask'][0]>0
                        if not any(cards[0][valid]==card(action['card'])):raise ValueError('Chosen card outside encoded support')
                        encodings+=1
            elif not (action.get('forced') or action.get('counterfactual_forced') or action.get('fixed_opening_lead')):
                raise ValueError('Non-forced decision lacks PIMC estimates')
            else:stats['forced_or_fixed_actions_without_pimc']+=1
            game.play(card(action['card']))
    stats['sampled_gen3_encodings']=encodings
    return family,stats

def export(runs,out):
    if out.exists():raise ValueError('Refusing to overwrite frozen export')
    cutoff=time.time();snapshots=[]
    for run in runs:
        m=read(run/'manifest.json');verify_generation(run,m)
        paths=sorted(p for p in (run/'episodes').glob('*.json.gz') if p.stat().st_mtime<=cutoff)
        snapshots.append((run,m,paths))
    out.mkdir(parents=True);totals=Counter();families=set();splits={};provenance=[];sources=[]
    trajectories=set()
    for run,m,paths in snapshots:
        dest=out/'runs'/run.name;dest.mkdir(parents=True)
        shutil.copy2(run/'manifest.json',dest/'manifest.json')
        counts=Counter();pairs=Counter();source_files=set();i=0
        for path,parent,e,actor_bots,game_path in candidates(run,m,paths):
            if parent['manifest_identity']!=m['identity']:raise ValueError('Wrong source manifest')
            if e['board']!=parent['board']:raise ValueError('Source board mismatch')
            family,stats=validate_game(e,actor_bots,m)
            split=e['split']
            if splits.setdefault(family,split)!=split:raise ValueError('Cross-run split conflict')
            # Preserve distinct decision/search observations, omit exact duplicate games.
            key=digest([family,e['board'],e['assignments'],
                [[{k:v for k,v in a.items() if k not in ('seconds','cpu_seconds')} for a in t['actions']] for t in e['tables']]])
            if key in trajectories:totals['exact_duplicate_games_omitted']+=1;continue
            trajectories.add(key)
            name=f'episodes/{i:06}.json.gz';atomic_json(dest/name,e,compressed=True)
            entry=dict(file=str((dest/name).relative_to(out)),sha256=sha(dest/name),
                source_run=run.name,source_manifest_identity=m['identity'],source_index=parent['index'],
                source_file=path.name,source_file_sha256=sha(path),source_game_path=game_path,
                actor_bots=actor_bots,active_bots={v:dict(identity=m['bots'][v]['identity'],policy_sha256=m['bots'][v].get('artifact_sha256',{}).get('policy')) for v in set(actor_bots.values())},
                family=family,split=split,trajectory_sha256=key,counts=dict(stats))
            provenance.append(entry);counts.update(stats);counts['games']+=1;i+=1
            source_files.add(path.name);families.add(family)
            pairs[parent.get('pair','4b vs 3')]+=1
        counts['source_deals']=len(source_files);totals.update(counts)
        sources.append(dict(run=run.name,manifest_identity=m['identity'],manifest_sha256=sha(dest/'manifest.json'),
            source_snapshot_files=len(paths),selected_source_deals=len(source_files),games=i,
            pairs=dict(pairs),counts=dict(counts)))
        print(json.dumps(dict(run=run.name,counts=dict(counts))),flush=True)
    atomic_json(out/'provenance.json',provenance);atomic_json(out/'family-splits.json',splits)
    code=out/'recipe-source'
    for path in (ROOT/'bridge_harness').glob('*.py'):
        target=code/'bridge_harness'/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    for name in ('prepare_policy_bootstrap.py','train_policy_bootstrap.py'):
        target=code/'scripts'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'scripts'/name,target)
    for name in ('LICENSE','CREDITS.md'):shutil.copy2(ROOT/name,code/name)
    atomic_json(out/'sources.relative.json',[dict(path='runs/'+r.name+'/episodes',role='training') for r in runs])
    summary=dict(schema='non-v4-policy-play-export-v1',cutoff_epoch=cutoff,
        cutoff_utc=datetime.fromtimestamp(cutoff,timezone.utc).isoformat(),sources=sources,counts=dict(totals),
        unique_families=len(families),families_by_split=dict(Counter(splits.values())),
        excluded_policy_sha256=V4_POLICY,
        selection='Both partnerships must avoid the Gen4 policy artifact. Gen4 belief is allowed. No outcome selection.',
        games_are_unmodified_nested_records=True,
        recipe='Gen3 predictive auction-aware policy: scripts/prepare_policy_bootstrap.py and train_policy_bootstrap.py; observed remaining partnership tricks for chosen action, PIMC estimates are inputs, never labels for unplayed moves.',
        split_note='Preserve these canonical family splits and all historical parent-training exclusions when merging with existing data. Family overlap across source runs is explicit; do not treat games as independent families.',
        availability='Complete local records from this environment as of cutoff; other environments remain owned by their existing collectors.')
    atomic_json(out/'export.json',summary)
    hashes={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    atomic_json(out/'FILE_SHA256.json',hashes)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,action='append',required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(export([r.resolve() for r in a.run],a.out.resolve())),flush=True)
