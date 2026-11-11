#!/usr/bin/env python3
"""Add an all-uniform table to decompose the existing paired trick gain by role."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.core import Board, imps
from bridge_harness.corpus import load
from bridge_harness.players import PIMCPlayer
from bridge_harness.runner import play_table, replay
from bridge_harness.training import digest


def baseline(job):
    data,seed=job;b=Board.from_dict(data);p=PIMCPlayer(32,'tricks',True,.125)
    try:
        r=dict(schema_version=1,board=data,config=dict(mode='selfplay',samples=32,batch=True,
            objective='tricks',near_tie=.125,seed=seed),assignments=[['uniform32']*4],
            tables=[play_table(b,['uniform32']*4,{'uniform32':p},seed)])
        r['status']=r['tables'][0]['status'];replay(r)
        for action in r['tables'][0]['actions']:
            assert action.get('forced') or (action['samples']==32 and action['dds_calls']==32 and action['batch'])
        return r
    finally:p.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);args=p.parse_args();root=args.run
    protocol=json.loads((root/'protocol.json').read_text());boards=load(root/'play-corpus.jsonl')
    dest=root/'all-uniform';dest.mkdir(exist_ok=True);pending=[];done=[]
    role_protocol=dict(purpose='exploratory role decomposition after primary paired result',
        independent_deals=len(boards),model_changed=False,additional_table='uniform PIMC all seats',
        seed=protocol['decision_seed'],samples=32,objective='tricks',near_tie=.125,batch=True,
        declarer_effect='informed declarer vs uniform defenders, minus all-uniform declarer tricks',
        defensive_effect='all-uniform declarer tricks minus uniform declarer vs informed defenders',
        opening_lead='defensive effect includes informed opening-lead changes; declarer comparison has identical blind lead')
    (root/'role-protocol.json').write_text(json.dumps(role_protocol,indent=2))
    for b in boards:
        path=dest/(digest(b.hands)+'.json.gz')
        if path.exists():
            with gzip.open(path,'rt') as f:r=json.load(f)
            assert r['status']=='ok';replay(r);done.append(r)
        else:pending.append((b.to_dict(),protocol['decision_seed']))
    started=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(baseline,x) for x in pending]):
            r=future.result();path=dest/(digest(Board.from_dict(r['board']).hands)+'.json.gz')
            temp=path.with_suffix('.tmp')
            with gzip.open(temp,'wt') as f:json.dump(r,f)
            temp.replace(path);done.append(r)
            if len(done)%20==0:print(json.dumps(dict(completed=len(done),seconds=time.perf_counter()-started)),flush=True)
    rows=[]
    for urecord in done:
        assert urecord['status']=='ok';b=Board.from_dict(urecord['board']);did=digest(b.hands)
        with gzip.open(root/'episodes'/(did+'.json.gz'),'rt') as f:original=json.load(f)
        assert original['status']=='ok';replay(original)
        u=urecord['tables'][0]
        d=original['tables'][b.contract.declarer%2]  # NS candidate at table 0, EW at table 1
        f=original['tables'][1-b.contract.declarer%2]
        assert d['actions'][0]['card']==u['actions'][0]['card'],'Common blind lead differs'
        ds=d['declarer_tricks']-u['declarer_tricks'];fs=u['declarer_tricks']-f['declarer_tricks']
        orientation=1 if b.contract.declarer%2==0 else -1
        rows.append(dict(deal_id=did,declarer_tricks=ds,defensive_tricks=fs,total_tricks=ds+fs,
            declarer_imps=imps(orientation*(d['ns_score']-u['ns_score'])),
            defensive_imps=imps(orientation*(u['ns_score']-f['ns_score'])),
            defensive_lead_changed=f['actions'][0]['card']!=u['actions'][0]['card']))
    assert len(rows)==protocol['play_deals'] and len({r['deal_id'] for r in rows})==len(rows)
    primary=json.loads((root/'play-summary.json').read_text())
    assert abs(np.mean([r['total_tricks'] for r in rows])-primary['mean_tricks'])<1e-12
    rng=np.random.default_rng(20261115);result=dict(independent_deals=len(rows),complete_games=3*len(rows),failures=0,
        baseline_wall_seconds=time.perf_counter()-started,
        defensive_leads_changed=sum(r['defensive_lead_changed'] for r in rows))
    for role in ('declarer','defensive'):
        data=np.array([[r[role+'_tricks'],r[role+'_imps']] for r in rows])
        boot=np.array([data[rng.integers(len(data),size=len(data))].mean(0) for _ in range(4000)])
        result[role]=dict(mean_tricks=float(data[:,0].mean()),tricks_95_interval=np.quantile(boot[:,0],[.025,.975]).tolist(),
            mean_imps=float(data[:,1].mean()),imps_95_interval=np.quantile(boot[:,1],[.025,.975]).tolist())
    with gzip.open(root/'role-per-deal.json.gz','wt') as f:json.dump(rows,f)
    (root/'role-summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
