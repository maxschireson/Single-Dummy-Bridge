"""Assemble promoted Gen5 components, freeze fresh deals and exact allocations."""
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.corpus import generate,save,load
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from bridge_harness.round5 import load_plan

def prepare(root,source,ben,count=25000):
    if root.exists():raise ValueError('Refusing to overwrite frozen Gen5 run')
    plan=load_plan();old=json.loads((source/'manifest.json').read_text());root.mkdir(parents=True)
    for name in ('artifacts','assets'):shutil.copytree(source/name,root/name)
    bots={k:deepcopy(old['bots'][{'4b':'Q'}.get(k,k)]) for k in ('4b','3','2','1')}
    paths={'belief':ROOT/'models/cardplay/gen5-belief-2026-11-10/belief.npz',
        'policy':ROOT/'models/cardplay/gen5-2026-11-10/policy.npz',
        'bidding':ROOT/'models/bidding/gen5-2026-11-10/bidder.keras'}
    spec=dict(id='v5',samples=192,near_tie=.125,exploration=0.,belief_kind='public',artifact_sha256={})
    for key,path in paths.items():
        target=root/'artifacts/v5'/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        spec[key]=str(target.relative_to(root));spec['artifact_sha256'][key]=sha(target)
    spec['identity']=digest(spec);bots['5']=spec
    small=deepcopy(spec);small.pop('identity');small.update(id='v5-32',samples=32);small['identity']=digest(small);bots['5-32']=small
    config=ROOT/'configs/ben-gen5-16.conf';ben_model=ben/'models/TF2models/GIB-BBO-8742_2026-10-23-E30.keras'
    for path,target in [(ben_model,root/'assets/bidding/ben.keras'),(config,root/'assets/ben-16.conf')]:shutil.copy2(path,target)
    spec=dict(id='ben-16',engine='ben',url='http://127.0.0.1:8087',samples=16,bidding='assets/bidding/ben.keras',config='assets/ben-16.conf',artifact_sha256=dict(bidding=sha(ben_model),config=sha(config)))
    spec['identity']=digest(spec);bots['ben']=spec
    blocked={deal_key(b.hands,True) for b in load(source/'corpus.jsonl')}
    original=source.parent/'v4-recovery/arena-v4/g0004/corpus.jsonl'
    if original.exists():blocked.update(deal_key(b.hands,True) for b in load(original))
    previous=Path('/workspace/work/gen5-codex/corpus.jsonl')
    if previous.exists():blocked.update(deal_key(b.hands,True) for b in load(previous))
    with gzip.open(ROOT/'models/cardplay/gen5-2026-11-10/training-families.json.gz','rt') as f:
        blocked.update(r['family'] for r in json.load(f))
    for path in (Path('/workspace/work/legacy-restore-verification/gen2-gen3/family-splits.json'),Path('/workspace/work/legacy-restore-verification/pimc-baseline/family-splits.json')):
        if path.exists():blocked.update(json.loads(path.read_text()))
    boards=[];seen=set()
    for b in generate(count+1000,plan['seed']):
        family=deal_key(b.hands,True)
        if family in blocked or family in seen:continue
        seen.add(family);boards.append(Board('gen5-'+family,b.hands,None,b.dealer,b.vulnerability,auction=(),auction_source='gen5-unbid'))
        if len(boards)==count:break
    if len(boards)!=count:raise ValueError('Insufficient fresh deals')
    save(boards,root/'corpus.jsonl')
    pair_schedule=[p for p,n in plan['pair_weights'].items() for _ in range(n)]
    m=dict(schema='gen5-arena-manifest-v1',generation=5,campaign='gen5-codex-32-20261110',
        target=count,seed=plan['seed'],roster=plan['roster'],bots=bots,pair_schedule=pair_schedule,
        pair_weights=plan['pair_weights'],audit_references={'5':'3','5-32':'3'},common_bidder='5',
        corpus='corpus.jsonl',corpus_sha256=sha(root/'corpus.jsonl'),source_sha256=source_hash(),
        runtime_sha256={name:sha(ROOT/name) for name in ('ops/gen5_runtime.py',)},
        audit=dict(probability=.5,multiplier=3.,max_depth=2,max_forks=64),
        ben_audit=dict(probability=0.,multiplier=1.,max_depth=0,max_forks=0),
        bidding_conditions=['common','native'],created_epoch=time.time(),source_generation=old['identity'],
        labels={'5':'Gen 5 (192)','4b':'Gen 4b','3':'Gen 3','2':'Gen 2','1':'Gen 1','ben':'BEN (16)','5-32':'Gen 5 (32)'},
        order=['5','4b','3','2','1','ben','5-32'],exclusion_families=len(blocked),
        fresh_deals='New seed; no available excluded family or previous Gen4 cohort overlap.',
        interpretation='Same deals and swapped partnerships. Common Gen5 auction and native partnership auctions reported separately; identical auctions reuse physical games. Gen5 uses 32 worlds vs historical bots at 32, and 192 only vs BEN at 16 or its identical-network 32-sample control. The 32-vs-192 Gen5 matchup measures sample budget with identical networks. No automatic model replacement or next generation.')
    m['identity']=digest(m);atomic_json(root/'manifest.json',m)
    atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=count,by_pair={},root_games=0,tables=0,epoch=time.time()))
    atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
    return m

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--ben',type=Path,required=True);p.add_argument('--count',type=int,default=25000);a=p.parse_args()
    m=prepare(a.run.resolve(),a.source.resolve(),a.ben.resolve(),a.count);print(json.dumps(dict(manifest_identity=m['identity'],target=m['target'],bots={k:v['artifact_sha256'] for k,v in m['bots'].items()})))
