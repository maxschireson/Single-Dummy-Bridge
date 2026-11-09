"""Small cost frontier screen with an independent 128-world reference.

The multifidelity estimator is mean(net on 128 worlds) + mean(exact - net on
the first 16 or 32 iid worlds). Audits are random, not confidence-selected.
No coefficient, cutoff or model is fitted on this test.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['BRIDGE_DDS_CACHE']=''
import argparse,json,time,random,sys,gzip
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.dds_value import Weights,pack,corrected_mean
from bridge_harness.belief_capacity import Weights as Belief
from bridge_harness.bidding_sampling import WeightedSampler
from bridge_harness.core import Board,Contract,Game
from bridge_harness.bidding_env import deal_key
from bridge_harness.dds import DDS
from bridge_harness.approx_dds import ApproxDDS
from bridge_harness.selfplay import atomic_json
from scripts.screen_dds_value import groups

def job(i,model,belief_path):
    rng=random.Random(202611091230000+i);cards=list(range(52));rng.shuffle(cards)
    hands=tuple(tuple(sorted(cards[13*s:13*s+13])) for s in range(4));trump=i%5;leader=(i//5)%4
    b=Board('dds-frontier-'+str(i),hands,Contract(3,'SHDCN'[trump],(leader-1)%4));g=Game(b)
    path_dds=DDS(cache_path='');approx=ApproxDDS();net=Weights(model);belief=Belief(belief_path);rows=[]
    try:
        for ply in range(12):
            if ply in {i%4,8+i%4}:
                o=g.observation();legal=list(o.legal)
                if len(legal)>1:
                    t=time.process_time();sampler=WeightedSampler(o,belief.logits(o),1.);setup=time.process_time()-t
                    wr=random.Random(7711090000+i*100+ply);worlds=[];sampling={};t=time.process_time()
                    for n in range(1,129):
                        worlds.append(sampler.draw(wr))
                        if n in (16,32,64,128):sampling[n]=setup+time.process_time()-t
                    rr=random.Random(8811090000+i*100+ply);reference=[sampler.draw(rr) for _ in range(128)]
                    fixed=[s for s,h in enumerate(o.known_hands) if h is not None]
                    def solve(ws):
                        d=DDS(cache_path='')
                        try:
                            start=time.process_time();v=d.solve_batch(ws,trump,g.leader,g.trick,fixed_seats=fixed);seconds=time.process_time()-start
                            return np.array([[q[c] for c in legal] for q,nodes in v]),seconds
                        finally:d.close()
                    ref,ref_cpu=solve(reference);target=ref.mean(0);pred={};cost={};exact={};exact_cost={}
                    for n in (16,32,64):
                        q,seconds=solve(worlds[:n]);exact[n]=q;exact_cost[n]=seconds
                        pred['exact'+str(n)]=q.mean(0);cost['exact'+str(n)]=seconds+sampling[n]
                    np.testing.assert_array_equal(exact[16],exact[64][:16]);np.testing.assert_array_equal(exact[32],exact[64][:32])
                    mus={};net_cpu={}
                    for n in (32,64,128):
                        start=time.process_time();mu,_,_=net.predict(np.stack([pack(w,trump,g.leader,g.trick) for w in worlds[:n]]))
                        for wi,w in enumerate(worlds[:n]):
                            for cl in groups(w,g.trick,set(legal)):mu[wi,cl]=mu[wi,cl].mean()
                        net_cpu[n]=time.process_time()-start;mus[n]=mu
                    totals=np.zeros(len(legal));start=time.process_time()
                    for wi,w in enumerate(worlds):
                        z=approx.all_moves(w,trump,g.leader,g.trick,100,guesses={c:float(mus[128][wi,c]) for c in legal})
                        totals+=np.array([z[c]['estimate'] for c in legal]);n=wi+1
                        if n in (32,64,128):
                            pred['net100_'+str(n)]=totals/n;cost['net100_'+str(n)]=time.process_time()-start+sampling[n]+net_cpu[n]
                    for n in (16,32):
                        name='corrected'+str(n)+'_128'
                        pred[name]=corrected_mean(mus[128][:,legal],exact[n])
                        cost[name]=sampling[128]+net_cpu[128]+exact_cost[n]
                    methods={}
                    for name,q in pred.items():
                        choice=np.flatnonzero(np.isclose(q,q.max(),atol=1e-8,rtol=0));methods[name]=dict(regret=float(target.max()-target[choice].mean()),seconds=cost[name],cards=[legal[j] for j in choice])
                    rows.append(dict(family=deal_key(hands,True),remaining=13-ply//4,ply=ply,reference_samples=128,reference_cpu=ref_cpu,sampling_cpu=sampling,methods=methods))
            v,_=path_dds.solve(g.hands,trump,g.leader,g.trick);best=max(v.values());g.play(rng.choice(sorted(c for c,q in v.items() if q==best)))
    finally:path_dds.close();approx.close()
    return rows

def summary(rows):
    from scipy.stats import t
    baseline=sum(r['methods']['exact32']['seconds'] for r in rows);out={}
    for name in rows[0]['methods']:
        fam={}
        for r in rows:fam.setdefault(r['family'],[]).append(r['methods'][name]['regret']-r['methods']['exact32']['regret'])
        delta=np.array([np.mean(v) for v in fam.values()]);mean=float(delta.mean());half=float(t.ppf(.975,len(delta)-1)*delta.std(ddof=1)/np.sqrt(len(delta)))
        cpu=sum(r['methods'][name]['seconds'] for r in rows)
        out[name]=dict(decisions=len(rows),families=len(fam),mean_regret=float(np.mean([r['methods'][name]['regret'] for r in rows])),cpu_seconds=cpu,cpu_vs_exact32=cpu/baseline,
            paired_family_regret_delta=mean,ci95=[mean-half,mean+half])
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--belief',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--count',type=int,default=100);p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);rows=[];start=time.time()
    with ProcessPoolExecutor(a.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(job,j,str(a.model),str(a.belief)) for j in range(400,400+a.count)]),1):
            rows+=f.result()
            if i%20==0:print(json.dumps(dict(families=i,decisions=len(rows),seconds=time.time()-start)),flush=True)
    with gzip.open(a.out/'decisions.json.gz','wt') as f:json.dump(rows,f,separators=(',',':'))
    atomic_json(a.out/'result.json',dict(config=dict(seed_families=[400,400+a.count-1],reference_samples=128,independent_reference=True,
        corrected_estimator='mean net over 128 + mean exact-minus-net over first 16/32 iid worlds; coefficient fixed to one',tuned_on_test=False),
        results=summary(rows),stages={str(rem):summary([r for r in rows if r['remaining']==rem]) for rem in (13,11)},seconds=time.time()-start,
        limitations=['Small proxy screen, not paired actual-play IMPs.','Independent reference also has finite-sample noise.',
            'CPU includes shared belief inference and sampling, neural preprocessing and search; excludes model/context construction.',
            'Synthetic contracts and DD-best-play trajectories; no arena promotion.']))
if __name__=='__main__':main()
