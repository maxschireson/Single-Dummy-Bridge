#!/usr/bin/env python3
"""Held-out outcome prediction and contextual-bandit policy diagnostics.

DR estimates concern one changed choice followed by the old policy. They are
not estimates of full-game play with the selector active at every decision.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import sys
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.policy_selector import SelectorWeights
from train_policy_selector import load_data


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True);args=p.parse_args()
    model=SelectorWeights(args.run/'training/weights.npz');totals=np.zeros(4);bydeal=defaultdict(list)
    changed=below=decisions=0
    for di in range(10):
        x,y,a,groups=load_data(args.data/f'chunk-{di}'/'test.npz')
        for start in range(0,len(y),512):
            sl=slice(start,start+512);xx={k:v[sl] for k,v in x.items()};yy=y[sl];aa=a[sl];rr=np.arange(len(yy))
            pred=model.predict(xx);valid=xx['mask'];count=valid.sum(1)
            best=np.where(valid>0,pred,-np.inf).max(1,keepdims=True)
            ties=(valid>0)&np.isclose(pred,best,rtol=0,atol=1e-7);pi=ties/ties.sum(1,keepdims=True)
            top=np.where(valid>0,xx['q'],-np.inf).max(1,keepdims=True)
            qties=(valid>0)&np.isclose(xx['q'],top,rtol=0,atol=1e-7);pibest=qties/qties.sum(1,keepdims=True)
            p0=valid/count[:,None]
            value=((pred-xx['q'])*valid).sum(1)/count
            state_only=xx['q']+value[:,None]
            logged=pred[rr,aa];residual=yy-logged
            totals += [np.square(logged-yy).sum(),np.square(state_only[rr,aa]-yy).sum(),np.square(xx['q'][rr,aa]-yy).sum(),len(yy)]
            dr_random=((pi-p0)*pred).sum(1)+(pi[rr,aa]*count-1)*residual
            dr_best=((pi-pibest)*pred).sum(1)+(pi[rr,aa]-pibest[rr,aa])*count*residual
            for group,v in zip(groups[sl],np.stack([dr_random,dr_best],1)):bydeal[str(group)].append(v)
            changed+=np.any(np.abs(pi-pibest)>1e-7,axis=1).sum();below+=(pi*(xx['q']<top-1e-7)).sum();decisions+=len(yy)
    means=np.stack([np.mean(v,axis=0) for v in bydeal.values()]);rng=np.random.default_rng(20261122)
    boot=np.array([means[rng.integers(len(means),size=len(means))].mean(0) for _ in range(3000)])
    result=dict(independent_test_deals=len(means),selector_decisions=int(totals[3]),
        mse=dict(model=totals[0]/totals[3],without_action_head=totals[1]/totals[3],pimc=totals[2]/totals[3]),
        policy_differs_from_pimc_best_fraction=float(changed/decisions),
        probability_of_selecting_below_top_pimc=float(below/decisions),
        single_choice_dr={name:dict(mean_acting_partnership_tricks=float(means[:,i].mean()),
            deal_bootstrap_95=np.quantile(boot[:,i],[.025,.975]).tolist()) for i,name in enumerate(('versus_random','versus_pimc_best'))},
        scope='one changed decision, then old behavior; diagnostic, not full-game performance; same test pool as play experiment')
    assert len(means)==999 and totals[3]==32214
    (args.run/'offline-test.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
