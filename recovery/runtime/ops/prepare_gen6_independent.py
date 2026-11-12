"""Freeze a fresh, independently seeded Gen6 cohort using published actor artifacts."""
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
import secrets
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.corpus import generate,load,save
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.prepare_gen6 import load_plan,make_bots,check_mix,release_file,GEN6_FILES


def prepare(root,artifacts,source_manifest,plan_path,count=25000,seed=None):
    root,artifacts=Path(root).resolve(),Path(artifacts).resolve()
    if root.exists():raise ValueError('Refusing to overwrite a frozen run')
    if count<1:raise ValueError('Positive board count required')
    plan=load_plan(plan_path)
    old=json.loads(Path(source_manifest).read_text())
    if digest({k:v for k,v in old.items() if k!='identity'})!=old['identity']:raise ValueError('Source manifest changed')
    for spec in old['bots'].values():
        if digest({k:v for k,v in spec.items() if k!='identity'})!=spec['identity']:raise ValueError('Source actor changed')
        for role,expected in spec['artifact_sha256'].items():
            if sha(artifacts/spec[role])!=expected:raise ValueError('Source artifact changed')
    bots=make_bots(old,plan)
    references=dict(old.get('audit_references',{}),**plan['audit_references'])
    check_mix(plan,bots,references)
    blocked=set()
    corpus=artifacts/'published-corpus.jsonl'
    if corpus.exists():
        if sha(corpus)!=old['corpus_sha256']:raise ValueError('Published exclusion corpus changed')
        blocked.update(deal_key(b.hands,True) for b in load(corpus))
    training=ROOT/'models/cardplay/gen5-2026-11-10/training-families.json.gz'
    if training.exists():
        with gzip.open(training,'rt') as f:blocked.update(r['family'] for r in json.load(f))
    releases={k:release_file(v) for k,v in plan['artifacts'].items()}
    seed=secrets.randbits(63) if seed is None else seed
    boards=[];seen=set()
    for b in generate(count+1000,seed):
        family=deal_key(b.hands,True)
        if family in blocked or family in seen:continue
        seen.add(family)
        boards.append(Board('gen6-independent-'+family,b.hands,None,b.dealer,b.vulnerability,auction=(),auction_source='gen6-independent-unbid'))
        if len(boards)==count:break
    if len(boards)!=count:raise ValueError('Insufficient fresh deals')
    root.mkdir(parents=True)
    for folder in ('artifacts','assets'):shutil.copytree(artifacts/folder,root/folder)
    for k,target in GEN6_FILES.items():
        (root/target).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(releases[k],root/target)
    for name in ('episodes','receipts','failures'):(root/name).mkdir()
    save(boards,root/'corpus.jsonl')
    labels=dict(old['labels'],**plan.get('labels',{}))
    labels.update({k:v.get('label',k) for k,v in plan['gen6_bots'].items()})
    m=dict(schema='gen5-arena-manifest-v1',generation=6,variant='6',campaign=plan['campaign'],title=plan['title'],
        target=count,seed=seed,roster=plan['roster'],bots=bots,pair_weights=plan['pair_weights'],
        pair_schedule=[p for p,n in plan['pair_weights'].items() for _ in range(n)],audit_references=references,
        common_bidder=plan['common_bidder'],corpus='corpus.jsonl',corpus_sha256=sha(root/'corpus.jsonl'),
        source_sha256=source_hash(),runtime_sha256={n:sha(ROOT/n) for n in ('ops/gen5_runtime.py','ops/prepare_gen6_independent.py')},
        audit=old['audit'],ben_audit=old['ben_audit'],bidding_conditions=['common','native'],
        created_epoch=time.time(),artifact_source_manifest_identity=old['identity'],labels=labels,order=plan['roster'],
        plan_sha256=sha(Path(plan_path)),engine_commit=plan['authorized_engine_commit'],exclusion_families=len(blocked),
        independent_cohort=True,
        model_note='Gen6 fast: 32 layouts until trick7; medium: 256 until trick6. Lead belief net only on opening lead, then hand-fit scorer; late compatible-layout list solves up to 256. Policy breaks exact ties. Gen5 is the frozen 5RZ32 actor; BEN uses 16 samples.',
        interpretation='Independent fresh seed and cohort. Excludes the published prior corpus and available Gen5 training families. Common Gen6 auctions and native partnership auctions are paired on each board, with swapped rooms; identical full auctions reuse physical games. Play=common IMPs; total=native IMPs; bidding=total-play (includes auction/play interaction). Exploratory paired intervals are unadjusted for repeated monitoring.')
    m['identity']=digest(m)
    atomic_json(root/'manifest.json',m)
    atomic_json(root/'state.json',dict(manifest_identity=m['identity'],completed=0,target=count,by_pair={},root_games=0,tables=0,epoch=time.time()))
    atomic_json(root/'heartbeat.json',dict(epoch=time.time(),completed=0,workers=4,ben_workers=1,in_flight=[]))
    verify_generation(root,m)
    return m


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--artifacts',type=Path,required=True)
    p.add_argument('--source-manifest',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--count',type=int,default=25000);p.add_argument('--seed',type=int)
    a=p.parse_args();m=prepare(a.run,a.artifacts,a.source_manifest,a.plan,a.count,a.seed)
    print(json.dumps(dict(identity=m['identity'],target=m['target'],seed=m['seed'])))
