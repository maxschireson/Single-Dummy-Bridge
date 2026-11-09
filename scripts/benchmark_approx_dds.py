"""Predeclared node-budget sweep, on held-out families, stratified by game stage."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,gzip,json,sys,time
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.core import Board,Game,card
from bridge_harness.dds import DDS
from bridge_harness.approx_dds import ApproxDDS
from bridge_harness.selfplay import atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--families',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--count',type=int,default=200)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    families=sorted([f for f in json.loads(a.families.read_text()) if f['split']=='test'],key=lambda f:f['family'])[:a.count]
    exact=DDS(cache_path='');approx=ApproxDDS();rows=[];budgets=(0,100,1000,10000)
    with (a.out/'positions.jsonl').open('w') as out:
        for fi,f in enumerate(families):
            r=json.loads(gzip.decompress(Path(f['source']).read_bytes()));episodes=[e for e in r['unique_tables'].values() if e.get('tables') and e.get('board',{}).get('contract')]
            if not episodes:continue
            e=episodes[0];g=Game(Board.from_dict(e['board']))
            # Alternate complete and partial tricks between families.
            plies={0+(fi%2),12+(fi%2),24+(fi%2),36+(fi%2)}
            for act in e['tables'][0]['actions']:
                if len(g.history) in plies:
                    o=g.observation();t=time.perf_counter();truth,nodes=exact.solve(g.hands,o.contract.trump,g.leader,g.trick);elapsed=time.perf_counter()-t
                    if len(truth)>1:
                        for budget in budgets:
                            t=time.perf_counter();v=approx.all_moves(g.hands,o.contract.trump,g.leader,g.trick,budget);seconds=time.perf_counter()-t
                            if any(not z['lower']<=truth[c]<=z['upper'] for c,z in v.items()):raise AssertionError('Invalid certified interval')
                            best=max(z['estimate'] for z in v.values());selected=[c for c,z in v.items() if abs(z['estimate']-best)<1e-8]
                            row=dict(family=f['family'],ply=len(g.history),remaining=13-len(g.history)//4,budget_per_move=budget,exact_seconds=elapsed,approx_seconds=seconds,exact_nodes=nodes,
                                approx_nodes=sum(z['nodes'] for z in v.values()),mae=float(np.mean([abs(z['estimate']-truth[c]) for c,z in v.items()])),
                                move_regret=float(max(truth.values())-np.mean([truth[c] for c in selected])),optimal_fraction=float(np.mean([truth[c]==max(truth.values()) for c in selected])),
                                certified_fraction=float(np.mean([z['exact'] for z in v.values()])),interval_width=float(np.mean([z['upper']-z['lower'] for z in v.values()])))
                            out.write(json.dumps(row)+'\n');out.flush();rows.append(row)
                g.play(card(act['card']))
            if (fi+1)%20==0:print(json.dumps(dict(families=fi+1,rows=len(rows))),flush=True)
    result=[]
    for remaining in (13,10,7,4):
        for budget in budgets:
            rr=[r for r in rows if r['remaining']==remaining and r['budget_per_move']==budget]
            if not rr:continue
            result.append(dict(remaining=remaining,budget_per_move=budget,positions=len(rr),speedup=sum(r['exact_seconds'] for r in rr)/sum(r['approx_seconds'] for r in rr),
                exact_ms=1000*np.mean([r['exact_seconds'] for r in rr]),approx_ms=1000*np.mean([r['approx_seconds'] for r in rr]),
                **{k:float(np.mean([r[k] for r in rr])) for k in ('mae','move_regret','optimal_fraction','certified_fraction','interval_width')}))
    atomic_json(a.out/'summary.json',dict(families=len(families),results=result,interpretation='Full-information DD approximation; not single-dummy playing strength. Equal weight per decision, total-time speedup. Node budget per legal move; Python rollout overhead included.'))
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
