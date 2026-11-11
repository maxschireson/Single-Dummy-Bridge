"""Prepare a new independently seeded, fast-only training cohort."""
import copy, json, secrets, shutil, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.corpus import generate,load,save
from bridge_harness.core import Board
from bridge_harness.bidding_env import deal_key
from bridge_harness.loop_registry import sha,source_hash
from bridge_harness.training import digest
from bridge_harness.selfplay import atomic_json
from bridge_harness.mixed_arena import verify_generation

source=Path('/workspace/scratch/c7932514d17d/gen6-fast-selfplay/runs/gen6-chatgpt-fast-selfplay-20261111')
run=ROOT/'runs/fast-only-20261111'
assert not run.exists()
old=json.loads((source/'manifest.json').read_text())
assert digest({k:v for k,v in old.items() if k!='identity'})==old['identity']
bots={k:copy.deepcopy(old['bots'][k]) for k in ('6-32','3')}
blocked=set()
for p in Path('/workspace/scratch/c7932514d17d').glob('*/runs/*/corpus.jsonl'):
    blocked.update(deal_key(b.hands,True) for b in load(p))
seed=secrets.randbits(63);count=25000;boards=[]
for b in generate(count+1000,seed):
    family=deal_key(b.hands,True)
    if family in blocked:continue
    blocked.add(family)
    boards.append(Board('gen6-extra-'+family,b.hands,None,b.dealer,b.vulnerability,auction=(),auction_source='gen6-extra-unbid'))
    if len(boards)==count:break
assert len(boards)==count
run.mkdir(parents=True)
for spec in bots.values():
    for key,expected in spec['artifact_sha256'].items():
        assert sha(source/spec[key])==expected
        dest=run/spec[key];dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/spec[key],dest)
for folder in ('episodes','receipts','failures'):(run/folder).mkdir()
save(boards,run/'corpus.jsonl')
plan=dict(pair_weights={'6-32~6-32':1},gap_fork=old['gap_fork'],audit=old['audit'],target=count,
          instruction='Max: latest Gen6 fast self-play only, for Gen7 training; no other matches')
atomic_json(run/'plan.json',plan)
m=dict(schema='gen5-arena-manifest-v1',generation=6,variant='6',campaign='gen6-extra-fast-only-20261111',
       title='Gen 6 fast self-play · additional Gen7 data',target=count,seed=seed,
       roster=['6-32','3'],order=['6-32'],bots=bots,pair_weights=plan['pair_weights'],pair_schedule=['6-32~6-32'],
       common_bidder='6-32',audit_references={'6-32':'3'},audit=old['audit'],ben_audit=old['ben_audit'],
       gap_fork=old['gap_fork'],two_self_rooms=False,bidding_conditions=['self'],
       corpus='corpus.jsonl',corpus_sha256=sha(run/'corpus.jsonl'),source_sha256=source_hash(),
       runtime_sha256={n:sha(ROOT/n) for n in ('ops/gen5_runtime.py','ops/smoke_gen6.py','ops/prepare_additional_selfplay.py')},
       created_epoch=time.time(),artifact_source_manifest_identity=old['identity'],independent_cohort=True,
       engine_commit='b81d674d983e2bb3b158400192a82c41177fde55',plan_sha256=sha(run/'plan.json'),
       labels={'6-32':'Gen 6 fast (32)','3':'Gen 3 audit reference only'},
       interpretation='All scheduled games are Gen6 fast self-play. Gen3 supplies the existing tie-audit reference only. No strength IMP estimate. Fresh seed; known local corpus families excluded.')
m['identity']=digest(m);atomic_json(run/'manifest.json',m)
atomic_json(run/'state.json',dict(manifest_identity=m['identity'],completed=0,target=count,by_pair={},root_games=0,tables=0,failures=0,epoch=time.time()))
verify_generation(run,m)
control=ROOT/'runs/control-preflight';shutil.copytree(run,control)
off=copy.deepcopy(m);off.pop('identity');off.pop('gap_fork');off['identity']=digest(off)
atomic_json(control/'manifest.json',off)
print(json.dumps(dict(run=str(run),manifest=m['identity'],target=count,seed=seed,pairs=m['pair_weights'])))
