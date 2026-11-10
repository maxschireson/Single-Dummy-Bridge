"""Freeze a root-only, opponent-stratified Gen5 data-efficiency pilot.

No held-out record is prepared. Initial high-effort cohort is finite and small;
this is a screening study, not a randomized collection trial or a play claim.
"""
import argparse, collections, gzip, hashlib, json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.belief_capacity import FIELDS, encode_play, sha
from bridge_harness.core import Board, Game, card
from bridge_harness.bidding_env import deal_key
from bridge_harness.auction_policy import encode_decision
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from scripts.screen_attention_belief import selected_observations, split
from scripts.freeze_clean_belief_sources import BAD_POLICY

def read(p):return json.loads(p.read_text())
def rank(f):return hashlib.sha256(('effort-pilot-20261110|'+f).encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);a=ap.parse_args();root=a.run.resolve()
    root.mkdir(parents=True,exist_ok=True)
    if (root/'plan.json').exists():return
    lab=Path('runs/belief-lab-20261110').resolve();base=read(lab/'data/dataset.json');lm=read(lab/'data/manifest.json')
    policy_base=Path('/workspace/scratch/9a559aafe909/bridge-policy-v5/runs/v5-clean/experiment/data')
    pm=read(policy_base/'dataset.json');excluded=set(lm['reserved_families'])
    for e in base['shards']:
        with np.load(e['file']) as z:excluded.update(map(str,z['split_group']))
    part=read(Path('/workspace/scratch/8fd3c92bf5b8/timing-v4/restored-v4/partition.json'))
    excluded.update(part['train_families']);excluded.update(part['validation_families'])
    excluded.update(e['family'] for e in read(policy_base/'families.json'))
    pools={};provenance={};rejected=collections.Counter()
    for label,folder,actor,effort in [('high','effort-high','5',192),('low','effort-feed','5-32',32)]:
        checkout=Path('/workspace/scratch/e9691f0e7615')/folder;source=checkout/'recovery';m=read(source/'manifest.json')
        assert digest({k:v for k,v in m.items() if k!='identity'})==m['identity']
        provenance[label]=dict(commit=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip(),manifest=m,manifest_sha256=sha(source/'manifest.json'))
        receipts={z['index']:z for z in (read(p) for p in (source/'receipts').glob('*.json'))}
        pool=collections.defaultdict(list)
        for path in sorted((source/'episodes').glob('*.json.gz')):
            raw=path.read_bytes();r=json.loads(gzip.decompress(raw));f=r['family']
            if r['candidate']!=actor or r['opponent'] not in ('4b','3','2','1'):continue
            if f in excluded:rejected[label+'_inherited_family']+=1;continue
            if split(f)!='train':rejected[label+'_holdout']+=1;continue
            assert r['split']=='train' and r['manifest_identity']==m['identity']
            assert receipts[r['index']]['episode_sha256']==hashlib.sha256(raw).hexdigest()
            for bot in (actor,r['opponent']):assert m['bots'][bot]['artifact_sha256'].get('policy')!=BAD_POLICY
            assert m['bots'][actor]['samples']==effort
            rooms={k:r['unique_tables'][k] for k in set(r['regimes']['common']['tables'])}
            for room in rooms.values():
                if room.get('schema_version')=='v4-passed-out-v1':continue
                assert room['status']=='ok' and deal_key(Board.from_dict(room['board']).hands,True)==f
                t=next(t for t in room['tables'] if t.get('node')=='root')
                assert all(z.get('samples') in (0,effort) for z in t['actions'] if z.get('player')=='candidate')
            entry=dict(family=f,opponent=r['opponent'],path=str(path),sha256=hashlib.sha256(raw).hexdigest(),index=r['index'],effort=effort)
            pool[r['opponent']].append(entry)
        pools[label]=pool
    assert provenance['high']['manifest']['bots']['5']['artifact_sha256']==provenance['low']['manifest']['bots']['5-32']['artifact_sha256']
    selected={k:[] for k in ('high','low','quantity')};strata={}
    for opponent,hi in pools['high'].items():
        hi=sorted(hi,key=lambda e:rank(e['family']));lo=sorted(pools['low'][opponent],key=lambda e:rank(e['family']))
        n=min(len(hi),len(lo)//6);strata[opponent]=dict(high_available=len(hi),low_available=len(lo),selected=n)
        selected['high']+=hi[:n];selected['low']+=lo[:n];selected['quantity']+=lo[:6*n]
    if len(selected['high'])<20:raise ValueError('Insufficient clean high-effort families')
    frozen={};costs={};counts={};(root/'sources').mkdir(exist_ok=True)
    for label in ('high','quantity'):
        for entry in selected[label]:
            f=entry['family']
            if f in frozen:continue
            original=json.loads(gzip.decompress(Path(entry['path']).read_bytes()));r=dict(original)
            r['unique_tables']={k:original['unique_tables'][k] for k in set(original['regimes']['common']['tables']) if original['unique_tables'][k].get('status')=='ok'}
            dest=root/'sources'/f'{f}.json.gz';dest.write_bytes(gzip.compress(json.dumps(r,separators=(',',':')).encode(),mtime=0))
            e=dict(family=f,split='train',sources=[dict(path=str(dest),sha256=sha(dest))]);belief=[];policy=[];cost=0.
            for key,o,y in selected_observations(e):
                x,support=encode_play(o);mask=support.sum(-1)>1
                if mask.any():belief.append(dict(**x,owner_target=y.astype(np.int8),owner_loss_mask=mask,support=support,kind=np.int8(2),split_group=np.array(f),card_weight=np.ones(52,np.float32)))
            for room in r['unique_tables'].values():
                board=Board.from_dict(room['board'])
                if board.contract is None:continue
                t=next(t for t in room['tables'] if t.get('node')=='root');cost+=float(t['cpu_seconds'])
                eligible=[i for i,z in enumerate(t['actions']) if z.get('estimates') and sum(v>0 for v in z.get('proposal_probabilities',z.get('behavior_probabilities',{})).values())>=2]
                take=set(sorted(eligible,key=lambda i:rank(f+'|'+str(room['seed'])+'|'+str(i)))[:16]);g=Game(board)
                for i,z in enumerate(t['actions']):
                    o=g.observation()
                    if i in take:
                        x,cards=encode_decision(o,z,synthetic=board.auction_source in (None,'synthetic'))
                        ix=np.flatnonzero((cards[0]==card(z['card']))&(x['mask'][0]>0));assert len(ix)==1
                        decl=o.actor%2==o.contract.declarer%2;final=t['declarer_tricks'] if decl else 13-t['declarer_tricks'];already=o.declarer_tricks if decl else len(o.history)//4-o.declarer_tricks
                        row={k:v[0] for k,v in x.items()};row.update(chosen=np.int8(ix[0]),y=np.float32(final-already),group=np.array(f));policy.append(row)
                    assert z['seat']=='NESW'[o.actor];g.play(card(z['card']))
                assert g.done and g.declarer_tricks==t['declarer_tricks'] and g.ns_score()==t['ns_score']
            for z in policy:z['weight']=np.float32(1/len(policy))
            frozen[f]=dict(belief=belief,policy=policy);costs[f]=dict(common_root_cpu_seconds=cost,whole_record_cpu_seconds=original['base_cpu']+original['branch_cpu'])
    # Identical original development pools for every arm; reserved predictions untouched.
    for label,entries in selected.items():
        count={};arm=root/'data'/label;arm.mkdir(parents=True,exist_ok=True)
        for kind in ('belief','policy'):
            rows=[z for e in entries for z in frozen[e['family']][kind]];count[kind+'_rows']=len(rows)
            path=arm/(kind+'.npz');np.savez_compressed(path,**{k:np.stack([z[k] for z in rows]) for k in rows[0]})
        count['families']=len(entries);counts[label]=count
        manifest=dict(schema='effort-pilot-data-v1',arm=label,entries=entries,base_sha256=sha(lab/'data/dataset.json'),common_root_only=True)
        atomic_json(arm/'manifest.json',manifest)
        shard=dict(file=str(arm/'belief.npz'),sha256=sha(arm/'belief.npz'),rows=count['belief_rows'],source='play',cohort='recent',split='train')
        atomic_json(arm/'dataset.json',dict(shards=base['shards']+[shard],manifest_sha256=sha(arm/'manifest.json')))
    plan=dict(schema='effort-pilot-v1',created=time.time(),deadline_utc='2026-11-11T04:30:00+00:00',provenance=provenance,strata=strata,excluded=dict(rejected),counts=counts,selected=selected,costs=costs,
        belief_base=str(lab/'data'),policy_base=str(policy_base),policy_parent='/workspace/scratch/63fa72341134/bridge-v5-calibration/runs/v5-ben-100/models/policy.npz',
        rule='Opponent-stratified root-only common-auction data; all historical families excluded. Canonical hash training families only. No outcome-based selection. Smaller low arm is nested in quantity arm. Sixfold volume is a nominal search-budget comparison; report actual CPU costs separately.',
        caveats=['Separate collection batches; not a paired randomized intervention','Only historical-opponent high-effort cohort; BEN/budget matchup excluded','Existing older development distribution may understate gains on Gen5 positions','First seed is a screen; seed and data-subset uncertainty require replication'],promoted=False)
    atomic_json(root/'plan.json',plan)
    cfg=read(lab/'fits/dense_added/config.json');jobs=[]
    for name in ('high','low','quantity'):
        out=root/'fits'/('belief_'+name);out.mkdir(parents=True,exist_ok=True);c=dict(cfg,data=str(root/'data'/name),threads=2)
        atomic_json(out/'config.json',c);jobs.append(dict(name=out.name,config=str(out/'config.json')))
    atomic_json(root/'jobs.json',jobs)
    print(json.dumps(dict(counts=counts,strata=strata,excluded=dict(rejected))),flush=True)

if __name__=='__main__':main()
