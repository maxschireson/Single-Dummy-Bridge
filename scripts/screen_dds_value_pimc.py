"""Frozen 32-world decision comparison; no policy/auction changes or match claims."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['BRIDGE_DDS_CACHE']=''
import argparse,json,time,random,sys,gzip
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.dds_value import Weights,pack
from bridge_harness.belief_capacity import Weights as Belief
from bridge_harness.bidding_sampling import WeightedSampler
from bridge_harness.core import Board,Contract,Game
from bridge_harness.bidding_env import deal_key
from bridge_harness.dds import DDS
from bridge_harness.approx_dds import ApproxDDS
from bridge_harness.selfplay import atomic_json
from scripts.screen_dds_value import groups,risk

def job(i,model,belief_path,threshold):
    rng=random.Random(202611091230000+i);cards=list(range(52));rng.shuffle(cards)
    hands=tuple(tuple(sorted(cards[13*s:13*s+13])) for s in range(4));trump=i%5;leader=(i//5)%4
    b=Board('dds-net-pimc-'+str(i),hands,Contract(3,'SHDCN'[trump],(leader-1)%4));g=Game(b)
    d=DDS(cache_path='');truth_dds=DDS(cache_path='');fallback_dds=DDS(cache_path='');a=ApproxDDS();net=Weights(model);belief=Belief(belief_path);rows=[]
    try:
        for ply in range(12):
            if ply in {i%4,8+i%4}:
                o=g.observation();legal=list(o.legal)
                if len(legal)>1:
                    sampler=WeightedSampler(o,belief.logits(o),1.);world_rng=random.Random(902611090000+i*100+ply)
                    worlds=[sampler.draw(world_rng) for _ in range(32)]
                    t=time.process_time();solved=truth_dds.solve_batch(worlds,trump,g.leader,g.trick,fixed_seats=[s for s,h in enumerate(o.known_hands) if h is not None]);exact_time=time.process_time()-t
                    exact=np.array([[v[c] for c in legal] for v,n in solved]);target=exact.mean(0)
                    t=time.process_time();mu,var,_=net.predict(np.stack([pack(w,trump,g.leader,g.trick) for w in worlds]))
                    reps=[]
                    for wi,w in enumerate(worlds):
                        classes=groups(w,g.trick,set(legal));reps.append([cl[0] for cl in classes])
                        for cl in classes:
                            value=float(mu[wi,cl].mean());variance=float((var[wi,cl]+mu[wi,cl]**2).mean()-value**2)
                            mu[wi,cl]=value;var[wi,cl]=max(variance,0)
                    net_time=time.process_time()-t
                    methods={}
                    for name,budget,seeded in [('rollout1000',1000,False),('net0',0,True),('net100',100,True),('net1000',1000,True),('net100_reinvest',100,True)]:
                        totals=np.zeros(len(legal));fallbacks=0;t=time.process_time()
                        for wi,w in enumerate(worlds):
                            if name=='net0':totals+=mu[wi,legal];continue
                            z=a.all_moves(w,trump,g.leader,g.trick,budget,guesses={c:mu[wi,c] for c in legal} if seeded else None)
                            estimate=np.full(52,-1e9);variance=var[wi].copy()
                            for c,v in z.items():
                                estimate[c]=v['estimate']
                                if v['exact']:variance[c]=0
                            if name=='net100_reinvest' and risk(estimate,variance,reps[wi])>=threshold:
                                # Execute the full fallback here, rather than replay accounting.
                                v,_=fallback_dds.solve(w,trump,g.leader,g.trick);totals+=np.array([v[c] for c in legal]);fallbacks+=1
                            else:totals+=estimate[legal]
                        seconds=time.process_time()-t+(net_time if seeded else 0)
                        totals/=32;chosen=np.flatnonzero(np.isclose(totals,totals.max(),atol=1e-8,rtol=0))
                        methods[name]=dict(regret=float(target.max()-target[chosen].mean()),seconds=seconds,full_solves=fallbacks,
                            selected_cards=[legal[j] for j in chosen],pimc_value_mae=float(np.abs(totals-target).mean()))
                    rows.append(dict(family=deal_key(hands,True),ply=ply,remaining=13-ply//4,legal=len(legal),exact_seconds=exact_time,methods=methods))
            v,_=d.solve(g.hands,trump,g.leader,g.trick);best=max(v.values());g.play(rng.choice(sorted(c for c,q in v.items() if q==best)))
    finally:d.close();truth_dds.close();fallback_dds.close();a.close()
    return rows

def summarize(rows):
    from scipy.stats import t
    out={}
    for name in ('rollout1000','net0','net100','net1000','net100_reinvest'):
        cpu=sum(r['methods'][name]['seconds'] for r in rows);baseline=sum(r['methods']['rollout1000']['seconds'] for r in rows)
        groups_={}
        for r in rows:groups_.setdefault(r['family'],[]).append(r['methods'][name]['regret']-r['methods']['rollout1000']['regret'])
        delta=np.array([np.mean(v) for v in groups_.values()]);mean=float(delta.mean());half=float(t.ppf(.975,len(delta)-1)*delta.std(ddof=1)/np.sqrt(len(delta)))
        out[name]=dict(decisions=len(rows),families=len(groups_),regret=float(np.mean([r['methods'][name]['regret'] for r in rows])),
            cpu_seconds=cpu,speedup_vs_rollout1000=baseline/cpu,speedup_vs_exact=sum(r['exact_seconds'] for r in rows)/cpu,
            full_solves=sum(r['methods'][name]['full_solves'] for r in rows),paired_family_regret_delta=mean,ci95=[mean-half,mean+half])
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--belief',type=Path,required=True);p.add_argument('--policy',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--count',type=int,default=200);p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    while not (a.policy.parent/'result.json').exists():time.sleep(2)
    policy=json.loads(a.policy.read_text());threshold=next(z['threshold'] for z in policy['candidates'] if z['method']=='net100');rows=[]
    # First 200 test families, fixed before this sampled-world evaluation.
    with ProcessPoolExecutor(a.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(job,j,str(a.model),str(a.belief),threshold) for j in range(200,200+a.count)]),1):
            rows+=f.result()
            if i%25==0:print(json.dumps(dict(families=i,decisions=len(rows))),flush=True)
    with gzip.open(a.out/'decisions.json.gz','wt') as f:json.dump(rows,f,separators=(',',':'))
    atomic_json(a.out/'result.json',dict(samples=32,families_requested=a.count,threshold=threshold,results=summarize(rows),
        stages={str(rem):summarize([r for r in rows if r['remaining']==rem]) for rem in (13,11)},
        limitations=['Expected DDS regret over 32 shared belief samples, not actual-play IMPs.','Synthetic fixed contracts on fresh random deals.',
            'All methods maximize expected tricks without Gen3 policy reranking.','Exact baseline uses the production batch API; selected full fallbacks use scalar DDS.']))
if __name__=='__main__':main()
