"""Paired deal-family uncertainty for a frozen additive belief checkpoint.

Validation was used for checkpoint selection: intervals are descriptive,
not a fresh test or a claim about IMP strength. Shared families across domains
remain a single cluster in the aggregate covariance calculation.
"""
import argparse
from collections import defaultdict
import json
import math
import os
from pathlib import Path
import sys
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.belief_capacity import Weights, make_model, batch, load
from train_additive_belief import entries, DOMAIN


def summary(values):
    values = np.asarray(values, np.float64)
    n = len(values); mean = float(values.mean())
    se = float(values.std(ddof=1)/np.sqrt(n))
    z = mean / se if se else 0.
    return dict(n=n, delta=mean, se=se, low=mean-1.96*se,
                high=mean+1.96*se, z=z, nominal_p=math.erfc(abs(z)/math.sqrt(2)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run','parent','out'): p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(); config=json.loads((a.run/'config.json').read_text())
    roots=list(config['dataset_sha256'])
    validation=[e for i,r in enumerate(roots) for e in entries(Path(r),'base' if i==0 else 'recent')
                if e['split']=='validation']
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    models=[]
    for path in (a.parent,a.run/'best.npz'):
        m=make_model((256,128)); m.set_weights(Weights(path).weights); models.append(m)
    @tf.function(reduce_retracing=True)
    def metrics(x,y,mask,support):
        result=[]
        for m in models:
            logits=tf.where(support,m(x,training=False),tf.constant(-1e9))
            loss=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,logits=logits)
            correct=tf.cast(tf.argmax(logits,-1,output_type=tf.int32)==y,tf.float32)
            result.extend([tf.reduce_sum(loss*mask,1),tf.reduce_sum(correct*mask,1)])
        result.append(tf.reduce_sum(mask,1))
        return tf.stack(result,1)
    families=defaultdict(lambda:np.zeros(5,np.float64))
    for e in validation:
        d=load(e['path'])
        for start in range(0,len(d['kind']),2048):
            ix=slice(start,start+2048); vals=metrics(*batch(d,ix)).numpy()
            for g,v,k in zip(d['split_group'][ix],vals,d['kind'][ix]):
                families[e['cohort'],e['source'],'all',str(g)]+=v
                if k==1: families[e['cohort'],e['source'],'complete_auction',str(g)]+=v
    rows=[]; domains={}; selected={}
    for key in sorted({k[:3] for k in families}):
        current={k[3]:v for k,v in families.items() if k[:3]==key and v[-1]}
        v=np.stack(list(current.values())); delta=(v[:,2:4]-v[:,:2])/v[:,4,None]
        domains['/'.join(key)]={metric:summary(delta[:,j]) for j,metric in enumerate(('nll','accuracy'))}
        if key[2]==('all' if key[1]=='play' else 'complete_auction'):
            selected[key]={g:(v[2:4]-v[:2])/v[4] for g,v in current.items()}
        for g,v in current.items(): rows.append(dict(domain='/'.join(key),family=g,values=v.tolist()))
    influence=defaultdict(lambda:np.zeros(2)); estimate=np.zeros(2)
    for key,by_family in selected.items():
        count=sum(k[1]==key[1] for k in selected)
        weight=DOMAIN[key[1]]/count
        mean=np.mean(list(by_family.values()),axis=0); estimate+=weight*mean
        for g,delta in by_family.items():
            influence[g]+=weight*(delta-mean)/len(by_family)*np.sqrt(len(by_family)/(len(by_family)-1))
    se=np.sqrt(np.square(list(influence.values())).sum(0))
    aggregate={metric:dict(delta=float(estimate[j]),se=float(se[j]),
        low=float(estimate[j]-1.96*se[j]),high=float(estimate[j]+1.96*se[j]),
        z=float(estimate[j]/se[j]),nominal_p=math.erfc(abs(estimate[j]/se[j])/math.sqrt(2)))
        for j,metric in enumerate(('nll','accuracy'))}
    result=dict(domains=domains,aggregate=aggregate,independent_clusters=len(influence),
        interpretation='Descriptive paired family-cluster intervals after selection among three epochs; no independent final test.',
        method='Family means; aggregate stratified mean with covariance retained across common families.')
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'paired.json').write_text(json.dumps(result,indent=2)+'\n')
    import gzip
    with gzip.open(a.out/'paired-families.jsonl.gz','wt') as f:
        for r in rows: f.write(json.dumps(r)+'\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__': main()
