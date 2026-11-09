"""Comparable CPU timing by replaying completed games; no opponent recomputation."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['BRIDGE_DDS_CACHE']=''
import argparse,json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,card
from bridge_harness.belief_plus import BeliefPlusPlayer
from bridge_harness.belief_capacity import Weights
from bridge_harness.approx_dds import ApproximatePIMCPlayer
from bridge_harness.selfplay import atomic_json
from scripts.evaluate_belief_plus import baseline

def main():
    p=argparse.ArgumentParser();p.add_argument('--games',type=Path,required=True);p.add_argument('--models',type=Path,required=True);p.add_argument('--weights',type=Path,required=True);p.add_argument('--count',type=int,default=50);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();files=sorted(p for p in a.games.glob('*.json') if len(p.stem)==64)[:a.count];rows=[]
    for i,path in enumerate(files):
        r=json.loads(path.read_text());family=r['family'];seed=int(family[:12],16);side=r['focal_side'];row=dict(family=family,times={},decisions={})
        for name in ('control','neural','hybrid7','approx1000'):
            if name=='control':player=baseline(a.models)
            elif name=='neural':player=BeliefPlusPlayer(a.weights)
            elif name=='hybrid7':player=BeliefPlusPlayer(a.weights,baseline(a.models),7)
            else:player=ApproximatePIMCPlayer(Weights(a.models/'public-belief.npz'),budget=1000,exact_remaining=7)
            game=Game(Board.from_dict(r['board']));total=0.;decisions=0
            trace=r['control'] if name=='control' else r['variants'][name]
            try:
                for act in trace['actions']:
                    o=game.observation()
                    if o.actor%2==side:
                        rng=random.Random(seed+104729*len(game.history)+1009*o.actor);t=time.process_time();d=player.choose(o,rng);total+=time.process_time()-t;decisions+=1
                        if d.card!=card(act['card']):raise AssertionError('Timing replay changed a move')
                    game.play(card(act['card']))
                if game.ns_score()!=trace['ns_score']:raise AssertionError('Replay score mismatch')
            finally:player.close()
            row['times'][name]=total;row['decisions'][name]=decisions
        rows.append(row)
        if (i+1)%10==0:print(json.dumps(dict(boards=i+1,seconds={k:sum(r['times'][k] for r in rows) for k in rows[0]['times']})),flush=True)
    totals={k:sum(r['times'][k] for r in rows) for k in rows[0]['times']}
    atomic_json(a.out,dict(boards=len(rows),cpu_seconds=totals,speedup={k:totals['control']/v for k,v in totals.items()},rows=rows,method='Same 50 predetermined families; replay exact completed traces, recompute focal decisions, assert every move matches; process CPU time, caches disabled.'))
if __name__=='__main__':main()
