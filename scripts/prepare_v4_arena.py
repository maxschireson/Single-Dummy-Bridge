"""Freeze a fresh v4 arena with explicit native bidders and immutable models."""
import argparse
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_env import make_board
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['out','belief','policy','current-bidder','native-v3','native-v2','native-v1']:
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--target',type=int,default=25000);p.add_argument('--seed',type=int,default=2026110924)
    a=p.parse_args();root=a.out.resolve()
    if root.exists():raise ValueError('Use a new campaign directory')
    root.mkdir(parents=True);models=root/'models';models.mkdir()
    repo=Path(__file__).resolve().parents[1];old=repo/'models/cardplay/gen3-2026-11-09'
    archive=json.loads((old/'manifest.json').read_text())
    for model in archive['models']:
        b=b''.join((old/c['file']).read_bytes() for c in model['chunks'])
        path=models/model['output'];path.write_bytes(b)
        if sha(path)!=model['sha256']:raise ValueError('Historical model mismatch')
    sources={'belief-v4.npz':a.belief,'policy-v4.npz':a.policy,
        'bidder-v4.keras':a.current_bidder,'bidder-v3.keras':a.native_v3,
        'bidder-v2.keras':a.native_v2,'bidder-v1.keras':a.native_v1}
    for name,path in sources.items():shutil.copy2(path,models/name)
    bots={}
    for gen,belief,kind,policy in [('4','belief-v4.npz','public','policy-v4.npz'),
            ('3','public-belief.npz','public','auction-policy.npz'),
            ('2','auction-belief.npz','auction','prior-policy.npz'),('1',None,None,None)]:
        spec=dict(id='gen'+gen,label='Gen '+gen,samples=32,near_tie=.125,exploration=0.,
                  bidding='models/bidder-v'+gen+'.keras',belief='models/'+belief if belief else None,
                  belief_kind=kind,policy='models/'+policy if policy else None)
        spec['artifact_sha256']={k:sha(root/spec[k]) for k in ['belief','policy','bidding'] if spec.get(k)}
        spec['identity']=digest(spec);bots[gen]=spec
    boards=[make_board(a.seed,i,'train').to_dict() for i in range(a.target)]
    corpus=root/'boards.jsonl';corpus.write_text(''.join(json.dumps(b)+'\n' for b in boards))
    m=dict(schema='v4-two-auction-arena-v1',roster=['4','3','2','1'],opponent_weights=[.5,.25,.125,.125],
        bots=bots,seed=a.seed,target=a.target,corpus=corpus.name,corpus_sha256=sha(corpus),
        audit=dict(probability=.5,multiplier=3.,max_depth=2,max_forks=64),
        archived_generations=['3-early'],generation_aliases={'auction-policy-v2':'3','public-belief-v2':'3-early'},
        bidding_behavior='greedy neural-only',regimes=['common','native'],self_play_competitive_score=False)
    m['identity']=digest(m);atomic_json(root/'manifest.json',m)
    print(root/'manifest.json')

if __name__=='__main__':main()
