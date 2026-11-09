"""Matched whole-game screening with frozen Gen3 opponents and auctions."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['BRIDGE_DDS_CACHE']=''
import argparse,json,sys,time,random,hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,imps,symbol
from bridge_harness.mixed_arena import ArenaPlayer
from bridge_harness.belief_capacity import Weights as BeliefWeights
from bridge_harness.belief_plus import BeliefPlusPlayer
from bridge_harness.approx_dds import ApproximatePIMCPlayer
from bridge_harness.selfplay import atomic_json

def baseline(models):
    spec=dict(id='gen3',policy='auction-policy.npz',belief='public-belief.npz',belief_kind='public',samples=32,near_tie=.125)
    return ArenaPlayer(spec,models)

def play(board,side,candidate,opponent,seed):
    game=Game(board);timing=[0.,0.];actions=[];start=time.perf_counter()
    while not game.done:
        o=game.observation();focal=o.actor%2==side;player=candidate if focal else opponent
        # Per-position random streams prevent neural decisions shifting later DDS samples.
        rng=random.Random(seed+104729*len(game.history)+1009*o.actor)
        t=time.perf_counter();d=player.choose(o,rng);timing[int(not focal)]+=time.perf_counter()-t
        actions.append(dict(ply=len(game.history),seat=o.actor,card=symbol(d.card),engine=d.details.get('selector','gen3-dds')))
        if d.card not in o.legal:raise ValueError('Illegal model move')
        game.play(d.card)
    return dict(ns_score=game.ns_score(),declarer_tricks=game.declarer_tricks,seconds=time.perf_counter()-start,focal_seconds=timing[0],opponent_seconds=timing[1],actions=actions)

def job(item,models,weights,variants,controls=None):
    family,bd=item;board=Board.from_dict(bd);seed=int(family[:12],16);side=int(family[-2:],16)%2
    opponent=baseline(models);control=baseline(models)
    result=dict(family=family,board=bd,focal_side=side,variants={})
    try:
        cached=Path(controls)/(family+'.json') if controls else None
        if cached and cached.exists():
            prior=json.loads(cached.read_text())
            if prior['board']!=bd or prior['focal_side']!=side:raise ValueError('Control mismatch')
            result['control']=prior['control']
        else:result['control']=play(board,side,control,opponent,seed)
        for variant in variants:
            if variant=='neural':candidate=BeliefPlusPlayer(weights,objective='tricks')
            elif variant=='hybrid7':candidate=BeliefPlusPlayer(weights,baseline(models),7,objective='tricks')
            elif variant=='hybrid10':candidate=BeliefPlusPlayer(weights,baseline(models),10,objective='tricks')
            elif variant=='approx1000':candidate=ApproximatePIMCPlayer(BeliefWeights(Path(models)/'public-belief.npz'),budget=1000,exact_remaining=7)
            else:raise ValueError(variant)
            try:
                r=play(board,side,candidate,opponent,seed);sign=1 if side==0 else -1
                r['imps']=imps(sign*(r['ns_score']-result['control']['ns_score']))
                r['tricks']=(1 if board.contract.declarer%2==side else -1)*(r['declarer_tricks']-result['control']['declarer_tricks'])
                result['variants'][variant]=r
            finally:candidate.close()
    finally:control.close();opponent.close()
    return result

def summary(rows):
    from scipy.stats import t
    out={}
    for variant in rows[0]['variants'] if rows else []:
        v=np.array([r['variants'][variant]['imps'] for r in rows]);n=len(v);half=float(t.ppf(.975,n-1)*v.std(ddof=1)/np.sqrt(n)) if n>1 else None
        out[variant]=dict(boards=n,total_imps=int(v.sum()),mean_imps=float(v.mean()),ci95=[float(v.mean()-half),float(v.mean()+half)] if half is not None else None,
            mean_tricks=float(np.mean([r['variants'][variant]['tricks'] for r in rows])),wins=int((v>0).sum()),losses=int((v<0).sum()),ties=int((v==0).sum()),
            focal_speedup=sum(r['control']['focal_seconds'] for r in rows)/sum(r['variants'][variant]['focal_seconds'] for r in rows),
            focal_seconds=sum(r['variants'][variant]['focal_seconds'] for r in rows),control_focal_seconds=sum(r['control']['focal_seconds'] for r in rows))
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--families',type=Path,required=True);p.add_argument('--models',type=Path,required=True);p.add_argument('--weights',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--count',type=int,default=200);p.add_argument('--workers',type=int,default=4);p.add_argument('--variants',nargs='+',default=['neural','hybrid7','approx1000']);p.add_argument('--controls',type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    allf=json.loads(a.families.read_text());fs=sorted([f for f in allf if f['split']=='test' and f['boards']],key=lambda f:f['family'])[:a.count]
    # One original contract per independent family; no filtering by outcome.
    items=[(f['family'],f['boards'][0]) for f in fs]
    config=dict(count=len(items),variants=a.variants,baseline='Gen3 both partnerships,32 samples,.125 near tie',objective='expected tricks for every tested player',seed_rule='family plus ply plus actor',weights_sha256=hashlib.sha256(a.weights.read_bytes()).hexdigest(),families=[f for f,_ in items],promoted=False)
    atomic_json(a.out/'config.json',config);rows=[]
    with ProcessPoolExecutor(a.workers) as pool:
        futures=[pool.submit(job,it,str(a.models),str(a.weights),a.variants,str(a.controls) if a.controls else None) for it in items]
        for future in as_completed(futures):
            r=future.result();atomic_json(a.out/(r['family']+'.json'),r);rows.append(r)
            if len(rows)%10==0:
                s=summary(rows);atomic_json(a.out/'progress.json',s);print(json.dumps(s),flush=True)
    result=dict(config=config,results=summary(rows),complete=True,limitations=['Exploratory held-out screen; intervals are descriptive.','Expected-trick objective isolates architecture; no IMP-utility reranking.','Logged continuations are off-policy for the neural player.'])
    atomic_json(a.out/'summary.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
