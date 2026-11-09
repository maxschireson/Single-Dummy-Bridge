"""Sample cached exact labels and generate independent early-position holdouts."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,json,sqlite3,time,sys,random,hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.dds_value import pack
from bridge_harness.dds import DDS
from bridge_harness.core import Board,Contract,Game
from bridge_harness.bidding_env import deal_key
from bridge_harness.selfplay import atomic_json

def cache(a):
    db=sqlite3.connect('file:'+str(a.cache)+'?mode=ro',uri=True,timeout=10)
    # The large production namespace. Do not mix solver builds silently.
    namespace=bytes.fromhex('12f993aca798a9bbd24ee18a584037b53dd71728fdfb7d984ab22dc97f250817')
    rng=np.random.default_rng(20261109112); keep={};seen={i:0 for i in range(10,14)}
    lookup=np.array([i.bit_count() for i in range(256)],np.uint8);total=0;start=time.time()
    cur=db.execute('SELECT position,scores FROM positions WHERE solver=?',(namespace,))
    while rows:=cur.fetchmany(100000):
        x=np.frombuffer(b''.join(r[0] for r in rows),np.uint8).reshape(-1,37)
        y=np.frombuffer(b''.join(r[1] for r in rows),np.uint8).reshape(-1,52)
        remaining=(lookup[x[:,5:]].sum(1)+(x[:,2:5]!=255).sum(1))//4
        for rem in range(10,14):
            ix=np.flatnonzero(remaining==rem);seen[rem]+=len(ix)
            if not len(ix):continue
            xx,yy,priority=x[ix],y[ix],rng.random(len(ix))
            if rem in keep:
                xx=np.concatenate([keep[rem][0],xx]);yy=np.concatenate([keep[rem][1],yy]);priority=np.r_[keep[rem][2],priority]
            if len(priority)>a.per_stage:
                k=np.argpartition(priority,a.per_stage-1)[:a.per_stage];xx,yy,priority=xx[k],yy[k],priority[k]
            keep[rem]=(xx.copy(),yy.copy(),priority.copy())
        total+=len(rows)
        if total%5000000==0:print(json.dumps(dict(scanned=total,seconds=time.time()-start)),flush=True)
    db.close()
    x=np.concatenate([keep[i][0] for i in range(10,14)]);y=np.concatenate([keep[i][1] for i in range(10,14)])
    order=rng.permutation(len(x));np.savez_compressed(a.out/'train.npz',raw=x[order],scores=y[order])
    atomic_json(a.out/'cache-manifest.json',dict(source=str(a.cache),namespace=namespace.hex(),available_by_remaining=seen,
        rows=len(x),per_stage=a.per_stage,seed=20261109112,seconds=time.time()-start,
        sha256=hashlib.sha256((a.out/'train.npz').read_bytes()).hexdigest(),
        limitation='Cache lacks parent-deal provenance. Validation and test are independently generated deals, not random cache rows.'))

def fresh_one(i):
    seed=202611091230000+i;rng=random.Random(seed);cards=list(range(52));rng.shuffle(cards)
    hands=tuple(tuple(sorted(cards[13*s:13*s+13])) for s in range(4));trump=i%5;leader=(i//5)%4
    b=Board('dds-net-fresh-'+str(i),hands,Contract(3,'SHDCN'[trump],(leader-1)%4))
    family=deal_key(hands,True);g=Game(b);dds=DDS(cache_path='');rows=[];offset=i%4
    try:
        for ply in range(16):
            start=time.process_time();v,nodes=dds.solve(g.hands,trump,g.leader,g.trick);seconds=time.process_time()-start
            if ply in {offset,4+offset,8+offset,12+offset}:
                scores=np.zeros(52,np.uint8)
                for c,q in v.items():scores[c]=q+1
                rows.append((pack(g.hands,trump,g.leader,g.trick),scores,seconds,nodes,ply))
            # Perfect-information best play creates legal coherent early trajectories.
            best=max(v.values());g.play(rng.choice(sorted(c for c,q in v.items() if q==best)))
    finally:dds.close()
    return i,family,rows

def fresh(a):
    results=[];start=time.time()
    with ProcessPoolExecutor(a.workers) as pool:
        for f in as_completed([pool.submit(fresh_one,i) for i in range(a.families)]):
            results.append(f.result())
            if len(results)%100==0:print(json.dumps(dict(families=len(results),seconds=time.time()-start)),flush=True)
    results.sort();assert len({f for i,f,r in results})==a.families
    for split,subset in [('validation',[r for r in results if r[0]<a.validation]),('test',[r for r in results if r[0]>=a.validation])]:
        flat=[(i,f,*z) for i,f,rows in subset for z in rows]
        np.savez_compressed(a.out/(split+'.npz'),group=np.array([z[1] for z in flat]),raw=np.stack([z[2] for z in flat]),
            scores=np.stack([z[3] for z in flat]),seconds=np.array([z[4] for z in flat]),nodes=np.array([z[5] for z in flat]),ply=np.array([z[6] for z in flat]))
    atomic_json(a.out/'fresh-manifest.json',dict(families=a.families,validation_families=a.validation,test_families=a.families-a.validation,
        seed_start=202611091230000,positions_per_family=4,remaining=[13,12,11,10],partial_tricks='all four offsets, balanced by family',
        trajectory='exact DDS best moves, random tie breaks',seconds=time.time()-start,cache_used=False,
        files={s:hashlib.sha256((a.out/(s+'.npz')).read_bytes()).hexdigest() for s in ['validation','test']}))

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['cache','fresh']);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--cache',type=Path,default=Path('/home/agent/.cache/single-dummy-bridge/dds-positions.sqlite'))
    p.add_argument('--per-stage',type=int,default=150000);p.add_argument('--families',type=int,default=1000);p.add_argument('--validation',type=int,default=200);p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    (cache if a.mode=='cache' else fresh)(a)
if __name__=='__main__':main()
