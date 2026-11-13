#!/usr/bin/env python3
"""Fit a small bidding-aware belief model; hold test metrics out of selection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.auction_belief import make_model, SCHEMA
from bridge_harness.belief_model import masked_loss, masked_probabilities
from scripts.train_belief import totals, summarize


def load(path):
    with np.load(path) as z:
        x={k:z[k] for k in ('state','calls','seats')}
        y=z['owner_target'].astype(np.int32);mask=z['owner_loss_mask'].astype(np.float32)
        support=np.ones((len(y),52,4),bool);support[:,:,0]=False
        own=x['state'][:,:52].astype(bool)
        support[own]=[True,False,False,False]
        assert np.all(mask.sum(-1)==39) and np.all(mask==(y!=0))
        assert np.take_along_axis(support,y[...,None],-1).all()
        return x,y,mask,support,z['kind']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=20);p.add_argument('--patience',type=int,default=4)
    p.add_argument('--seed',type=int,default=20261109);p.add_argument('--threads',type=int,default=4)
    args=p.parse_args()
    if args.out.exists():raise ValueError('Refusing overwrite')
    audit=json.loads((args.data/'audit.json').read_text())
    assert audit['validated'] and audit['independent_auctions']>=50000 and audit['schema']==SCHEMA
    for split in ('train','validation','test'):
        assert hashlib.sha256((args.data/f'{split}.npz').read_bytes()).hexdigest()==audit['exports'][split]
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(args.threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(args.seed);tf.config.experimental.enable_op_determinism()
    train=load(args.data/'train.npz');valid=load(args.data/'validation.npz')
    model=make_model(train[0]['state'].shape[1])
    optimizer=tf.keras.optimizers.AdamW(learning_rate=.001,weight_decay=.0001,clipnorm=1.)
    args.out.mkdir(parents=True)
    manifest=dict(schema=SCHEMA,parameters=model.count_params(),dataset=audit,
        args={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},
        task='hidden ownership from own hand and public auction prefix; no card play',
        source='BEN neural-only greedy legal calls; single bidding style',
        selection='lowest validation NLL; test metrics not evaluated',tensorflow=tf.__version__)
    root=Path(__file__).resolve().parents[1]
    for name in ('bridge_harness/auction_belief.py','bridge_harness/belief_model.py',
                 'scripts/train_auction_belief.py','scripts/train_belief.py','scripts/prepare_auction_belief.py'):
        dst=args.out/'source'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,dst)
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(dict(event='start',parameters=model.count_params(),splits=audit['splits'])),flush=True)
    @tf.function(reduce_retracing=True)
    def step(x,y,m,s):
        with tf.GradientTape() as tape:
            n,d=masked_loss(model(x,training=True),y,m,s);loss=n/d
        optimizer.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
        return n,d
    @tf.function(reduce_retracing=True)
    def predict(x):return model(x,training=False)
    def evaluate(ablate=False):
        x,y,m,s,kind=valid;total=np.zeros(4);prefix=np.zeros(4);complete=np.zeros(4)
        for start in range(0,len(y),1024):
            sl=slice(start,start+1024);inputs={k:v[sl] for k,v in x.items()}
            if ablate:
                inputs['calls']=np.zeros_like(inputs['calls']);inputs['seats']=np.full_like(inputs['seats'],4)
                inputs['state']=inputs['state'].copy();inputs['state'][:,-1]=0
            prob=masked_probabilities(predict(inputs).numpy(),s[sl])
            total+=totals(prob,y[sl],m[sl])
            prefix+=totals(prob,y[sl],m[sl]*(kind[sl]==0)[:,None])
            complete+=totals(prob,y[sl],m[sl]*(kind[sl]==1)[:,None])
        return dict(all=summarize(total),prefix=summarize(prefix),complete_auction=summarize(complete))
    baseline=evaluate();best=baseline['all']['nll'];stale=0;history=[]
    (args.out/'baseline.json').write_text(json.dumps(baseline,indent=2))
    model.save(args.out/'best.keras');best_row=dict(epoch=0,validation=baseline)
    rng=np.random.default_rng(args.seed);started=time.perf_counter()
    for epoch in range(1,args.epochs+1):
        t=time.perf_counter();x,y,m,s,_=train;order=rng.permutation(len(y));acc=np.zeros(2)
        for start in range(0,len(order),1024):
            ix=order[start:start+1024];n,d=step({k:v[ix] for k,v in x.items()},y[ix],m[ix],s[ix]);acc+=[float(n),float(d)]
        val=evaluate();row=dict(epoch=epoch,seconds=time.perf_counter()-t,train_nll=float(acc[0]/acc[1]),validation=val)
        history.append(row)
        with (args.out/'history.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        if val['all']['nll']<best-1e-5:
            best=val['all']['nll'];stale=0;best_row=row;model.save(args.out/'best.keras')
        else:stale+=1
        print(json.dumps(row),flush=True)
        if stale>=args.patience:break
    model.save(args.out/'last.keras')
    model=tf.keras.models.load_model(args.out/'best.keras')
    # Rebuild a traced evaluator for the selected checkpoint, not stale captured variables.
    @tf.function(reduce_retracing=True)
    def predict(x):return model(x,training=False)
    ablation=evaluate(ablate=True)
    result=dict(status='complete',seconds=time.perf_counter()-started,epochs=len(history),
        best=best_row,baseline=baseline,validation_auction_removed=ablation,
        test_evaluated=False,playing_strength_evaluated=False,parameters=model.count_params())
    (args.out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':main()
