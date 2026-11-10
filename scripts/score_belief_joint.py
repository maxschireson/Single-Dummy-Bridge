"""Exact two-hidden-seat likelihood on development positions, by deal family."""
import argparse,gzip,json,os,sys,time
from collections import defaultdict
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.belief_lab import Weights,swap_loss_numpy
from bridge_harness.belief_capacity import INPUTS,sha
from bridge_harness.selfplay import atomic_json
from scripts.residual_belief_common import read

def exact_two_seat(z,y,mask,support,play):
    cards=np.flatnonzero(mask);seats=np.flatnonzero(support[cards].any(0))
    if len(seats)!=2 or not len(cards):return None
    s0,s1=seats;forced=(support&(support.sum(-1)==1)[:,None]).sum(0)
    remaining=play[484:488]*13 if play[-1]>0 else np.full(4,13.)
    cap=np.rint(remaining-forced).astype(int);k=cap[s1];n=len(cards)
    if k<0 or k>n or cap[s0]+k!=n:raise ValueError('Public capacity mismatch')
    # Every uncertain card has both these owners available; one-owner cards were removed.
    d=(z[cards,s1]-z[cards,s0]).astype(np.float64)
    dp=np.full(k+1,-np.inf);dp[0]=0
    for value in d:dp[1:]=np.logaddexp(dp[1:],dp[:-1]+value)
    if np.sum(y[cards]==s1)!=k:raise ValueError('Target violates public capacity')
    return float((dp[k]-d[y[cards]==s1].sum())/n)

def score(modelpath,data,out):
    if out.exists():return json.loads(out.read_text())
    model=Weights(modelpath);entries=[e for e in json.loads((data/'dataset.json').read_text())['shards'] if e['split']=='validation' and e['cohort']=='recent']
    groups=defaultdict(lambda:[0.,0,0.,0]);start=time.time()
    for e in entries:
        d=read(e)
        for lo in range(0,len(d['kind']),256):
            ix=slice(lo,lo+256);x={k:d[k][ix] for k in INPUTS};z=model.predict(x)
            sw=swap_loss_numpy(z,d['owner_target'][ix],d['owner_loss_mask'][ix],d['support'][ix])/np.maximum(d['owner_loss_mask'][ix].sum(1),1)
            for j,g in enumerate(d['split_group'][ix]):
                row=lo+j;v=exact_two_seat(z[j],d['owner_target'][row],d['owner_loss_mask'][row],d['support'][row],d['play'][row])
                stat=groups[str(g)];stat[2]+=float(sw[j]);stat[3]+=1
                if v is not None:stat[0]+=v;stat[1]+=1
    vals=[v[0]/v[1] for v in groups.values() if v[1]]
    result=dict(exact_two_seat_nll=float(np.mean(vals)),families=len(vals),positions=sum(v[1] for v in groups.values()),
        swap_nll=float(np.mean([v[2]/v[3] for v in groups.values()])),all_families=len(groups),all_positions=sum(v[3] for v in groups.values()),
        seconds=time.time()-start,model=str(modelpath),model_sha256=sha(modelpath),data_sha256=sha(data/'dataset.json'),groups=groups,
        interpretation='Exact log probability under the same capacity-conditioned product as play, divided by uncertain cards, averaged within then across families. Two-hidden-seat positions only; no test use.')
    atomic_json(out,result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps({k:v for k,v in score(a.model,a.data,a.out).items() if k!='groups'}))
