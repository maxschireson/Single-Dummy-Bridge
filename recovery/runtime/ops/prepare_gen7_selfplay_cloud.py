"""New independently seeded, fast-only cohort from verified published Gen6 actors."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import secrets
import shutil
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.corpus import generate, load, save
from bridge_harness.loop_registry import sha, source_hash
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops.prepare_gen6 import verify_source

def prepare(source, run, count=25000):
    source, run = Path(source), Path(run)
    if run.exists(): raise ValueError('Refusing to overwrite a cohort')
    old = json.loads((source/'manifest.json').read_text())
    verify_source(source, old)
    assert old['bots']['6-32']['samples'] == 32
    assert old['audit']['probability'] == .5
    assert old['gap_fork'] == dict(per_band=2,bands=[.125,.5],max_cpu_share=1.5)
    blocked = {deal_key(b.hands,True) for b in load(source/old['corpus'])}
    seed = secrets.randbits(63)
    boards=[]
    for b in generate(count+1000,seed):
        family=deal_key(b.hands,True)
        if family in blocked: continue
        blocked.add(family)
        boards.append(Board('gen7-cloud-'+family,b.hands,None,b.dealer,b.vulnerability,auction=(),auction_source='fresh-unbid'))
        if len(boards)==count: break
    assert len(boards)==count
    run.mkdir(parents=True)
    for d in ('episodes','receipts','failures','artifacts','assets'): (run/d).mkdir()
    bots={k:deepcopy(old['bots'][k]) for k in ('6-32','3')}
    for spec in bots.values():
        for role in spec['artifact_sha256']:
            dest=run/spec[role];dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source/spec[role],dest)
    save(boards,run/'corpus.jsonl')
    m=dict(schema=old['schema'],generation=6,variant='6',campaign='gen7-fast-selfplay-cloud-20261111',
        title='Gen 7 capture · cloud fast self-play only',target=count,seed=seed,
        roster=['6-32','3'],order=['6-32'],bots=bots,labels={'6-32':'Gen 6 fast (32)','3':'Gen 3 audit reference'},
        pair_weights={'6-32~6-32':1},pair_schedule=['6-32~6-32'],audit_references={'6-32':'3'},common_bidder='6-32',
        corpus='corpus.jsonl',corpus_sha256=sha(run/'corpus.jsonl'),source_sha256=source_hash(),
        runtime_sha256={n:sha(ROOT/n) for n in ('ops/gen5_runtime.py','ops/prepare_gen7_selfplay_cloud.py')},
        audit=old['audit'],ben_audit=old['ben_audit'],gap_fork=old['gap_fork'],bidding_conditions=['self'],two_self_rooms=False,
        created_epoch=time.time(),independent_cohort=True,artifact_source_manifest_identity=old['identity'],
        capture_source_commit=old['capture_source_commit'],
        model_note='Gen6 fast32/list trick7/cap256; frozen models. Guess-size and best-share logs, gap forks 2/band, CPU cap1.5, 50% tie audits. Gen3 exists only as audit selector; no scheduled old-bot or BEN matches.',
        interpretation='100% fast self-play; one physical root table per fresh family, null comparison IMPs. Training split by family; test families mod10=0 must not train or select models.')
    m['identity']=digest(m)
    atomic_json(run/'manifest.json',m)
    atomic_json(run/'state.json',dict(manifest_identity=m['identity'],completed=0,target=count,by_pair={},root_games=0,tables=0,epoch=time.time()))
    atomic_json(run/'heartbeat.json',dict(epoch=time.time(),completed=0,in_flight=[],workers=3,ben_workers=0))
    verify_generation(run,m)
    return m

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--count',type=int,default=25000)
    a=p.parse_args();print(json.dumps(prepare(a.source,a.run,a.count)))
