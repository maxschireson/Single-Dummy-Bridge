"""Freeze fresh belief-only games, keeping the promoted v5 bidder and policy fixed."""
import argparse,copy,json,shutil,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.bidding_env import make_board,deal_key
from bridge_harness.belief_capacity import sha
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

def prepare(root,candidate,reference,data,boards=2000,seed=202611106172):
    if (root/'manifest.json').exists():return
    root.mkdir(parents=True,exist_ok=True);models=root/'models';models.mkdir(exist_ok=True)
    policy=Path('/workspace/scratch/63fa72341134/bridge-v5-calibration/runs/v5-ben-100/models/policy.npz')
    bidding=Path('/workspace/scratch/bbe90ba77a68/bridge-bidding-refresh/models/bidding/gen5-2026-11-10/bidder.keras')
    shutil.copyfile(policy,models/'policy.npz');shutil.copyfile(bidding,models/'bidder.keras')
    specs={}
    for name,path in [('5b',candidate),('4b',reference)]:
        path=Path(path);recipe=json.loads(path.read_text()) if path.suffix=='.json' else dict(model=str(path.resolve()),temperature=1.,projection=False)
        model=Path(recipe['model']);model=model if model.is_absolute() else path.parent/model
        shutil.copyfile(model,models/f'{name}.npz');recipe['model']=f'{name}.npz';atomic_json(models/f'{name}.json',recipe)
        spec=dict(id=name,label=name,samples=32,near_tie=.125,exploration=0.,bidding='models/bidder.keras',policy='models/policy.npz',belief=f'models/{name}.json',belief_weights=f'models/{name}.npz',belief_kind='lab')
        spec['artifact_sha256']={k:sha(root/spec[k]) for k in ('belief','belief_weights','policy','bidding')}
        spec['identity']=digest(spec);specs[name]=spec
    excluded=set();ds=json.loads((data/'dataset.json').read_text());dm=json.loads((data/'manifest.json').read_text())
    excluded.update(dm['reserved_families'])
    for e in ds['shards']:
        with np.load(e['file']) as z:excluded.update(map(str,z['split_group']))
    part=Path('/workspace/scratch/8fd3c92bf5b8/timing-v4/restored-v4/partition.json')
    partition=json.loads(part.read_text());excluded.update(partition['train_families']);excluded.update(partition['validation_families'])
    families=[];corpus=[];i=0
    while len(corpus)<boards:
        b=make_board(seed,i,'dev');i+=1;f=deal_key(b.hands,True)
        if f in excluded:continue
        excluded.add(f);families.append(f);corpus.append(b.to_dict())
    (root/'boards.jsonl').write_text(''.join(json.dumps(b)+'\n' for b in corpus))
    atomic_json(root/'families.json',families);atomic_json(root/'created_epoch.json',time.time())
    repo=Path(__file__).resolve().parents[1]
    runtime={str(p.relative_to(repo)):sha(p) for p in (repo/'bridge_harness').glob('*.py')}
    runtime['bridge_harness/libbridge_dds.so']=sha(repo/'bridge_harness/libbridge_dds.so')
    runtime['scripts/run_supplemental_arena.py']=sha(repo/'scripts/run_supplemental_arena.py')
    m=dict(schema='v4-two-auction-arena-v1',title='Belief lab independent confirmation',roster=['5b','4b'],bots=specs,
        target=boards,seed=seed,corpus='boards.jsonl',corpus_sha256=sha(root/'boards.jsonl'),runtime_sha256=runtime,
        audit=dict(probability=0.,multiplier=1.,max_depth=0,max_forks=0),pair_schedule=[['5b','4b']],audit_references={'5b':'4b'},
        common_bidder='4b',two_self_rooms=True,independent_room_seeds=False,excluded_families=len(excluded)-boards,
        evaluation_only=True,promoted=False,interpretation='Identical v5 policy and candidate-2 v5 bidder; 32 worlds per decision; two swapped tables; common/native identical and counted once; fresh families excluded from all future training.')
    m['identity']=digest(m);atomic_json(root/'manifest.json',m)
    atomic_json(root/'RESERVED_EVALUATION.json',dict(families=families,training_allowed=False,purpose='Final belief comparison'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--boards',type=int,default=2000);p.add_argument('--seed',type=int,default=202611106172);a=p.parse_args()
    prepare(a.run,a.candidate,a.reference,a.data,a.boards,a.seed)
