"""Freeze the next Gen6 mix after the BEN16 lead gate, without changing any net."""
import argparse
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.corpus import generate,load,save
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.prepare_gen6 import verify_source,check_mix,gap_fork_block


def load_plan(path):
    p=json.loads(Path(path).read_text())
    if p['schema']!='gen6-ben-followups-plan-v1':raise ValueError('Wrong followup plan')
    ben_keys=[key for key in ('ben32','ben64') if key in p]
    if len(ben_keys)!=1:raise ValueError('Choose exactly one medium BEN sample budget')
    ben_key=ben_keys[0]
    required={'6-256~'+ben_key,'6-32~ben'}
    if not required<=set(p['pair_weights']):raise ValueError('Both requested BEN matches are required')
    if any(isinstance(n,bool) or not isinstance(n,int) or n<1 for n in p['pair_weights'].values()):
        raise ValueError('Positive integer match weights required')
    if p[ben_key]['samples']!=int(ben_key[3:]) or p['common_bidder']!='6-32':raise ValueError('Changed BEN budget or common bidder')
    gap_fork_block(p)
    return p


def prepare(root,source,plan_path,preflight=False):
    root,source=Path(root).resolve(),Path(source).resolve();plan=load_plan(plan_path)
    if root.exists():raise ValueError('Refusing to overwrite a frozen run')
    if not preflight and not all((source/n).exists() for n in ('STOP','WATCHDOG_STOP')):
        raise ValueError('Source must drain before the followup cohort is frozen')
    lock=(source/'.writer.lock').open('a+')
    try:
        if not preflight:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=json.loads((source/'manifest.json').read_text());verify_source(source,old)
        for bot,key in (('6-32','fast_identity'),('6-256','medium_identity'),('ben','ben16_identity')):
            if old['bots'][bot]['identity']!=plan['gate'][key]:raise ValueError('Baseline actor changed')
        boards=load(source/old['corpus']);done=set()
        if not preflight:
            if list((source/'failures').glob('*.json')):raise ValueError('Preserved failures need inspection')
            receipts=sorted((source/'receipts').glob('*.json'))
            if len(receipts)!=len(list((source/'episodes').glob('*.json.gz'))):raise ValueError('Incomplete source archive')
            for file in receipts:
                r=json.loads(file.read_text());i=r['index']
                if i in done or not 0<=i<len(boards) or r['manifest_identity']!=old['identity']:
                    raise ValueError('Wrong source receipt')
                if r['family']!=deal_key(boards[i].hands,True) or r['episode_sha256']!=sha(source/'episodes'/f'{i:06d}.json.gz'):
                    raise ValueError('Changed source episode')
                done.add(i)
        keep=list(range(min(40,len(boards)))) if preflight else [i for i in range(len(boards)) if i not in done]
        fresh=not keep
        if fresh:
            blocked={deal_key(b.hands,True) for b in boards};selected=[]
            for b in generate(plan['fallback_target']+1000,plan['seed']):
                family=deal_key(b.hands,True)
                if family in blocked:continue
                blocked.add(family);selected.append(Board('gen6-followup-'+family,b.hands,None,b.dealer,b.vulnerability,auction=(),auction_source='gen6-followup-unbid'))
                if len(selected)==plan['fallback_target']:break
            if len(selected)!=plan['fallback_target']:raise ValueError('Insufficient fresh families')
        else:selected=[boards[i] for i in keep]
        ben_key=next(key for key in ('ben32','ben64') if key in plan);samples=plan[ben_key]['samples']
        bots=deepcopy(old['bots']);b=deepcopy(bots['ben']);b.pop('identity')
        config=ROOT/plan[ben_key]['config'];config_name=f'assets/ben-{samples}.conf'
        b.update(id=f'ben-{samples}',url=plan[ben_key]['url'],samples=samples,config=config_name)
        b['artifact_sha256']['config']=sha(config);b['identity']=digest(b);bots[ben_key]=b
        references=dict(old['audit_references'],**plan['audit_references']);check_mix(plan,bots,references)
        root.mkdir(parents=True)
        for folder in ('artifacts','assets'):shutil.copytree(source/folder,root/folder)
        shutil.copy2(config,root/config_name)
        for folder in ('episodes','receipts','failures'):(root/folder).mkdir()
        save(selected,root/'corpus.jsonl');atomic_json(root/'source-indices.json',keep)
        labels=dict(old['labels'],**{ben_key:f'BEN ({samples})'})
        runtime=('ops/gen5_runtime.py','ops/prepare_gen6_ben_followups.py','ops/watch_gen5.py','ops/publish_gen5.py','ops/export_gen5.py')
        m=dict(schema='gen5-arena-manifest-v1',generation=6,variant='6',campaign=plan['campaign']+('-preflight' if preflight else ''),
            title=plan['title'],target=len(selected),seed=plan['seed'],roster=plan['roster'],bots=bots,
            pair_weights=plan['pair_weights'],pair_schedule=[p for p,n in plan['pair_weights'].items() for _ in range(n)],
            common_bidder=plan['common_bidder'],audit_references=references,
            corpus='corpus.jsonl',corpus_sha256=sha(root/'corpus.jsonl'),source_sha256=source_hash(),
            runtime_sha256={name:sha(ROOT/name) for name in runtime},audit=old['audit'],ben_audit=old['ben_audit'],
            bidding_conditions=['common','native'],created_epoch=time.time(),source_generation=old['identity'],source_completed=len(done),
            source_indices='source-indices.json',source_indices_sha256=sha(root/'source-indices.json'),fresh_corpus=fresh,
            labels=labels,order=plan['roster'],plan_sha256=sha(plan_path),engine_commit=old.get('engine_commit'),preflight_only=preflight,
            model_note=f'Gen6 networks and fast/medium play settings are unchanged. BEN{samples} uses neural-only bidding and {samples} opening-lead/play samples on its own server. New fast/BEN16 games are authorized followups; the original accidental games stay archived.',
            interpretation='Same-deal common Gen6 and native partnership auctions, swapped partnerships, complete raw records and per-decision timing. Only unused source families enter the followup; a fresh cohort is generated if the source is exhausted.')
        if gap_fork_block(plan):m['gap_fork']=gap_fork_block(plan)
        m['identity']=digest(m);atomic_json(root/'manifest.json',m)
        atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=m['target'],by_pair={},root_games=0,tables=0,epoch=time.time()))
        atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
        shutil.copy2(plan_path,root/'plan.json');verify_generation(root,m)
        return m
    finally:lock.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--preflight',action='store_true');a=p.parse_args()
    print(json.dumps(prepare(a.run,a.source,a.plan,a.preflight)))
