"""Freeze policy-only 4p and belief-only 4b without changing an existing run."""
import argparse,json,shutil,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_env import make_board,deal_key
from bridge_harness.loop_registry import sha
from bridge_harness.training import digest
from bridge_harness.selfplay import atomic_json

def component_bots(bots):
    from copy import deepcopy
    result=deepcopy(bots)
    for name,field in [('4p','policy'),('4b','belief')]:
        spec=deepcopy(bots['3']);spec.update(id='gen'+name,label='Gen '+name)
        spec[field]=bots['4'][field]
        spec['artifact_sha256'][field]=bots['4']['artifact_sha256'][field]
        spec['identity']=digest({k:v for k,v in spec.items() if k!='identity'})
        result[name]=spec
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--target',type=int,default=10000)
    p.add_argument('--seed',type=int,default=797611091640);a=p.parse_args()
    source=json.loads((a.source/'manifest.json').read_text());root=a.out.resolve()
    if root.exists():raise ValueError('Use a new cohort directory')
    root.mkdir(parents=True);shutil.copytree(a.source/'models',root/'models')
    bots=component_bots(source['bots'])
    for spec in bots.values():
        for kind,expected in spec['artifact_sha256'].items():
            if sha(root/spec[kind])!=expected:raise ValueError('Artifact mismatch')
    # A fresh seed and explicit family rejection prevent overlap with source run.
    excluded=set()
    from bridge_harness.core import Board
    for line in (a.source/source['corpus']).read_text().splitlines():
        excluded.add(deal_key(Board.from_dict(json.loads(line)).hands,True))
    boards=[];families=set();i=0
    while len(boards)<a.target:
        b=make_board(a.seed,i,'train');i+=1;family=deal_key(b.hands,True)
        if family in excluded or family in families:continue
        families.add(family);boards.append(b.to_dict())
    corpus=root/'boards.jsonl';corpus.write_text(''.join(json.dumps(b)+'\n' for b in boards))
    # Most comparisons test each new component against Gen 3. Retain
    # direct comparisons to full Gen 4 and between the two component variants.
    pairs=[['4p','3']]*3+[['4b','3']]*3+[['4p','4b'],['4p','4'],['4b','4'],['4','3']]
    repo=Path(__file__).resolve().parents[1]
    runtime={str(f.relative_to(repo)):sha(f) for f in (repo/'bridge_harness').glob('*.py')}
    runtime['bridge_harness/libbridge_dds.so']=sha(repo/'bridge_harness/libbridge_dds.so')
    runtime['scripts/run_supplemental_arena.py']=sha(repo/'scripts/run_supplemental_arena.py')
    m=dict(schema='v4-two-auction-arena-v1',title='Gen 4 component arena',
        roster=['4','4p','4b','3','2','1'],display_order=['4','4p','4b','3'],bots=bots,
        seed=a.seed,target=a.target,corpus=corpus.name,corpus_sha256=sha(corpus),
        audit=dict(probability=.5,multiplier=3.,max_depth=2,max_forks=64),
        pair_schedule=pairs,common_bidder='4',two_self_rooms=True,independent_room_seeds=True,
        audit_references={'4':'3','4p':'3','4b':'3'},runtime_sha256=runtime,
        cohort='gen4-components-20261109',source_manifest=source['identity'],
        component_definitions={'4p':'Gen 3 plus only the Gen 4 policy','4b':'Gen 3 plus only the Gen 4 belief'},
        bidding_behavior='greedy neural-only',regimes=['common','native'],self_play_competitive_score=False)
    m['identity']=digest(m);atomic_json(root/'manifest.json',m);atomic_json(root/'created_epoch.json',time.time())
    atomic_json(root/'status.json',dict(completed=0,workers=4,failures=0,updated_epoch=time.time()))
    atomic_json(root/'families.json',sorted(families));print(root/'manifest.json')

if __name__=='__main__':main()
