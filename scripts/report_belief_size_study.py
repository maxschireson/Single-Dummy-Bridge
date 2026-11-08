#!/usr/bin/env python3
"""Paired descriptive validation comparison of two already selected checkpoints."""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import sys
import time
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from bridge_harness.belief_capacity import INPUTS,Weights,load,batch,sha
from bridge_harness.belief_model import masked_probabilities,capacity_prior
from bridge_harness.selfplay import atomic_json


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    ds=json.loads((a.run/'data/dataset.json').read_text())
    results={s:json.loads((a.run/s/'result.json').read_text()) for s in ('small','large')}
    if not all(r['complete'] for r in results.values()):raise ValueError('Both fixed-budget pilots must complete')
    weights={s:Weights(a.run/s/'best.npz') for s in results}
    groups=defaultdict(lambda:defaultdict(lambda:np.zeros(5)))
    play_baselines={k:np.zeros(2) for k in ('uniform_support','capacity_prior')}
    sample=None
    for entry in ds['shards']:
        if entry['split']!='validation':continue
        path=a.run/'data'/entry['file']
        if sha(path)!=entry['sha256']:raise ValueError('Dataset changed')
        d=load(path)
        if entry['source']=='play' and sample is None:sample={k:d[k][:128] for k in INPUTS}
        for start in range(0,len(d['kind']),1024):
            ix=slice(start,start+1024);x,y,m,sup=batch(d,ix)
            if entry['source']!='play':m=m*(d['kind'][ix]==1)[:,None]
            else:
                priors={'uniform_support':sup/np.maximum(sup.sum(-1,keepdims=True),1),
                        'capacity_prior':capacity_prior(sup,x['play'][:,484:488]*13)}
                for name,prob in priors.items():
                    true=np.take_along_axis(prob,y[...,None],axis=-1)[...,0]
                    play_baselines[name]+=[float((-np.log(np.maximum(true,1e-30))*m).sum()),float(m.sum())]
            rows=[]
            for size in ('small','large'):
                prob=masked_probabilities(weights[size].predict(x),sup)
                true=np.take_along_axis(prob,y[...,None],axis=-1)[...,0]
                rows.append(((-np.log(np.maximum(true,1e-30))*m).sum(1),((prob.argmax(-1)==y)*m).sum(1)))
            for j,g in enumerate(d['split_group'][ix]):
                groups[entry['source']][str(g)]+=[rows[0][0][j],rows[1][0][j],m[j].sum(),rows[0][1][j],rows[1][1][j]]
    paired={}
    for source,values in groups.items():
        v=np.array(list(values.values()));v=v[v[:,2]>0]
        delta=(v[:,1]-v[:,0])/v[:,2];se=delta.std(ddof=1)/np.sqrt(len(delta))
        paired[source]=dict(deal_groups=len(delta),mean_deal_nll_difference_large_minus_small=float(delta.mean()),
            descriptive_95_ci=[float(delta.mean()-1.96*se),float(delta.mean()+1.96*se)],
            small_mean_deal_nll=float((v[:,0]/v[:,2]).mean()),large_mean_deal_nll=float((v[:,1]/v[:,2]).mean()))
    latency={}
    # Identical CPU/BLAS setting and examples. This measures neural inference,
    # not full PIMC latency and not an uncontended hardware benchmark.
    for size,w in weights.items():
        latency[size]={}
        for n,reps in ((1,300),(128,50)):
            x={k:v[:n] for k,v in sample.items()};w.predict(x)
            timings=[]
            for _ in range(3):
                start=time.perf_counter()
                for __ in range(reps):w.predict(x)
                timings.append((time.perf_counter()-start)*1000/reps)
            latency[size][f'batch_{n}_median_ms']=float(np.median(timings))
    out=dict(results=results,paired_validation=paired,numpy_inference_latency=latency,
        play_baseline_nll={k:float(v[0]/v[1]) for k,v in play_baselines.items()},
        dataset_sha256=sha(a.run/'data/dataset.json'),test_evaluated=False,playing_strength_evaluated=False,promoted=False,
        uncertainty_note='Descriptive paired normal intervals across held-out deal groups after epoch selection; not independent final-test or IMP evidence.')
    atomic_json(a.run/'comparison.json',out)
    print(json.dumps(dict(paired_validation=paired,latency=latency),indent=2))

if __name__=='__main__':main()
