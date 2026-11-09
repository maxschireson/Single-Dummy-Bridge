"""Independent full-information screen and validation-calibrated CPU reinvestment.

No test outcome or test timing chooses a fallback threshold. Reinvestment timing
is replay accounting: base method plus measured full solve on selected positions.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['BRIDGE_DDS_CACHE']=''
import argparse,json,time,sys,hashlib,gzip,sqlite3
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.dds_value import Weights,unpack,encode
from bridge_harness.dds import DDS
from bridge_harness.approx_dds import ApproxDDS
from bridge_harness.selfplay import atomic_json

def regret(y,estimate):
    legal=y>=0;best=np.max(estimate[legal]);ix=legal & np.isclose(estimate,best,atol=1e-8,rtol=0)
    return float(y.max()-y[ix].mean())

def groups(hands,trick,legal):
    live=sorted(set(c for h in hands for c in h)|set(c for _,c in trick));out=[];prev=None
    for c in live:
        if c in legal:
            if prev is None or prev not in legal or prev//13!=c//13:out.append([])
            out[-1].append(c)
        prev=c
    return out

def risk(estimate,variance,reps):
    if len(reps)<2:return 0.
    order=sorted(reps,key=lambda c:estimate[c],reverse=True);a,b=order[:2]
    return float(np.sqrt(max(variance[a]+variance[b],0))/(.25+max(estimate[a]-estimate[b],0)))

def inference_timing(net,raw,batch):
    # Warm BLAS and report process CPU, including encoding and softmax.
    net.predict(raw[:batch]);times=[]
    for _ in range(3):
        start=time.process_time()
        for i in range(0,len(raw),batch):net.predict(raw[i:i+batch])
        times.append(time.process_time()-start)
    return float(np.median(times)/len(raw))

def collect(path,net,out):
    with np.load(path) as z:data={k:z[k] for k in z.files}
    raw=data['raw'];y=data['scores'].astype(int)-1;mu,var,_=net.predict(raw)
    per=inference_timing(net,raw,32);single=inference_timing(net,raw[:min(200,len(raw))],1)
    exact=DDS(cache_path='');approx=ApproxDDS();rows=[];start=time.time()
    try:
        for done,i in enumerate(np.random.default_rng(2026110914).permutation(len(raw)),1):
            hands,trump,lead,trick=unpack(raw[i]);legal=set(np.flatnonzero(y[i]>=0).tolist());pool_start=time.process_time();classes=groups(hands,trick,legal);reps=[g[0] for g in classes]
            # Enforce exact legal-card equivalence, retaining mixture uncertainty.
            for group in classes:
                value=float(mu[i,group].mean());variance=float((var[i,group]+mu[i,group]**2).mean()-value**2)
                mu[i,group]=value;var[i,group]=max(variance,0)
            pooling_seconds=time.process_time()-pool_start
            t=time.process_time();truth,nodes=exact.solve(hands,trump,lead,trick);exact_seconds=time.process_time()-t
            if truth!={c:int(y[i,c]) for c in legal}:raise ValueError('Fresh DDS label changed')
            rem=(sum(map(len,hands))+len(trick))//4
            methods={'net0':dict(seconds=per+pooling_seconds,regret=regret(y[i],mu[i]),mae=float(np.abs(mu[i,list(legal)]-y[i,list(legal)]).mean()),risk=risk(mu[i],var[i],reps))}
            for name,budget,seeded in [('rollout100',100,False),('rollout1000',1000,False),('net100',100,True),('net1000',1000,True)]:
                guesses={c:float(mu[i,c]) for c in legal} if seeded else None
                t=time.process_time();result=approx.all_moves(hands,trump,lead,trick,budget,guesses=guesses);seconds=time.process_time()-t+(per+pooling_seconds if seeded else 0)
                estimate=np.full(52,-1e9);variance=var[i].copy()
                for c,z in result.items():
                    if not z['lower']<=truth[c]<=z['upper']:raise ValueError('False proof bound')
                    if z['nodes']>budget:raise ValueError('Exceeded node budget')
                    estimate[c]=z['estimate']
                    if z['exact']:variance[c]=0
                methods[name]=dict(seconds=seconds,regret=regret(y[i],estimate),mae=float(np.abs(estimate[list(legal)]-y[i,list(legal)]).mean()),
                    risk=risk(estimate,variance,reps),certified_fraction=float(np.mean([z['exact'] for z in result.values()])))
            rows.append(dict(index=int(i),family=str(data['group'][i]),remaining=rem,legal=len(legal),distinct_moves=len(reps),exact_seconds=exact_seconds,nodes=nodes,methods=methods))
            if done%400==0:print(json.dumps(dict(split=path.stem,positions=done,seconds=time.time()-start)),flush=True)
    finally:exact.close();approx.close()
    rows.sort(key=lambda r:r['index'])
    with gzip.open(out/(path.stem+'-positions.json.gz'),'wt') as f:json.dump(rows,f,separators=(',',':'))
    return rows,dict(batch32_per_position=per,batch1_per_position=single)

def metrics(rows,method,threshold=None):
    rows=[r for r in rows if r['legal']>1]
    non=[r for r in rows if r['distinct_moves']>1]
    fallback=lambda r:threshold is not None and r['methods'][method]['risk']>=threshold and r['distinct_moves']>1
    cpu=sum(r['methods'][method]['seconds']+(r['exact_seconds'] if fallback(r) else 0) for r in rows)
    values=np.array([0 if fallback(r) else r['methods'][method]['regret'] for r in non])
    fam={}
    for r,v in zip(non,values):fam.setdefault(r['family'],[]).append(v)
    f=np.array([np.mean(v) for v in fam.values()]);se=float(f.std(ddof=1)/np.sqrt(len(f))) if len(f)>1 else 0
    return dict(positions=len(rows),nontrivial_positions=len(non),families=len(fam),mean_regret=float(values.mean()) if len(values) else 0.,
        family_mean_regret=float(f.mean()) if len(f) else 0.,family_se=se,
        optimal_fraction=float(np.mean(values<1e-8)) if len(values) else 1.,cpu_seconds=cpu,
        speedup_vs_exact=sum(r['exact_seconds'] for r in rows)/cpu,
        speedup_vs_rollout1000=sum(r['methods']['rollout1000']['seconds'] for r in rows)/cpu,
        full_solves=sum(fallback(r) for r in rows),mae=float(np.mean([0 if fallback(r) else r['methods'][method]['mae'] for r in rows])))

def calibrate(rows):
    rows=[r for r in rows if r['legal']>1]
    target=.90*sum(r['methods']['rollout1000']['seconds'] for r in rows);policies=[]
    for method in ('net0','net100','net1000'):
        used=sum(r['methods'][method]['seconds'] for r in rows)
        ranked=sorted([r for r in rows if r['distinct_moves']>1 and r['methods'][method]['risk']>0],key=lambda r:r['methods'][method]['risk'],reverse=True)
        k=0
        while k<len(ranked) and used+ranked[k]['exact_seconds']<=target:
            used+=ranked[k]['exact_seconds'];k+=1
        if not k:threshold=1e30
        elif k==len(ranked):threshold=1e-20
        else:threshold=(ranked[k-1]['methods'][method]['risk']+ranked[k]['methods'][method]['risk'])/2
        m=metrics(rows,method,threshold);policies.append(dict(method=method,threshold=threshold,validation=m,within_budget=m['cpu_seconds']<=target))
    eligible=[p for p in policies if p['within_budget']]
    chosen=min(eligible,key=lambda p:(p['validation']['mean_regret'],p['validation']['cpu_seconds'])) if eligible else None
    return dict(target_fraction_of_baseline=.9,candidates=policies,chosen=chosen,
        rule='Rank uncertainty = sqrt(top-two value variances)/(0.25+value gap), excluding DD-equivalent cards; choose cutoff and method on validation only.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--fit',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    while not (a.fit/'result.json').exists():time.sleep(2)
    net=Weights(a.fit/'best.npz');validation,vt=collect(a.data/'validation.npz',net,a.out)
    policy=calibrate(validation);atomic_json(a.out/'frozen-policy.json',policy)
    test,tt=collect(a.data/'test.npz',net,a.out)
    names=('net0','rollout100','rollout1000','net100','net1000')
    result=dict(checkpoint_sha256=hashlib.sha256((a.fit/'best.npz').read_bytes()).hexdigest(),policy=policy,inference=dict(validation=vt,test=tt),
        validation={name:metrics(validation,name) for name in names},test={name:metrics(test,name) for name in names},
        stages={str(rem):{name:metrics([r for r in test if r['remaining']==rem],name) for name in names} for rem in (13,12,11,10)},
        expensive_test={name:metrics([r for r in test if r['exact_seconds']>.005],name) for name in names},
        limitations=['Full-information move regret, not single-dummy IMP playing strength.','Inference timing assumes batches of 32 sampled worlds; batch-1 timing also reported.',
            'Fresh independent deals use exact-DD-best-play trajectories, not arena sampling distributions.','Selective exact fallback is a replay cost simulation, not a production CPU scheduler.',
            'Gate and method frozen on validation; test CPU use is reported without retuning.'])
    if policy['chosen']:
        c=policy['chosen'];result['reinvest_test']=metrics(test,c['method'],c['threshold'])
        result['reinvest_stages']={str(rem):metrics([r for r in test if r['remaining']==rem],c['method'],c['threshold']) for rem in (13,12,11,10)}
    atomic_json(a.out/'result.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
