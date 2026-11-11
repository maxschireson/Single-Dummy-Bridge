#!/usr/bin/env python3
"""Train one of two frozen-data auction+public-play belief candidates; no promotion."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from bridge_harness.belief_capacity import SCHEMA,INPUTS,load,batch,sha,widen,make_model,Weights,score
from bridge_harness.belief_model import masked_loss,masked_probabilities
from bridge_harness.selfplay import atomic_json
from scripts.train_belief import totals,summarize


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--size',choices=['small','large'],required=True)
    p.add_argument('--epochs',type=int,default=8);p.add_argument('--threads',type=int,default=1)
    p.add_argument('--run-seconds',type=float,default=240)
    a=p.parse_args()
    if min(a.epochs,a.threads,a.run_seconds)<=0:raise ValueError('Positive settings required')
    a.out.mkdir(parents=True,exist_ok=True)
    lock=(a.out/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ds=json.loads((a.data/'dataset.json').read_text())
    if ds['schema']!=SCHEMA or not ds['validated']:raise ValueError('Wrong dataset')
    widths=(64,64) if a.size=='small' else (256,128)
    config=dict(schema=SCHEMA,widths=widths,dataset_sha256=sha(a.data/'dataset.json'),
        parent_sha256=sha(a.data/'parent.npz'),epochs=a.epochs,threads=a.threads,seed=2026110902,
        learning_rate=.0002,batch_size=1024,source_sha256={s:sha(ROOT/s) for s in (
        'bridge_harness/belief_capacity.py','bridge_harness/belief_model.py','scripts/train_belief_size_study.py')},
        selection='0.5 play NLL + 0.25 complete-auction bidding NLL + 0.25 complete-auction BEN NLL',
        stopping='Fixed 8-epoch pilot by default; retain selected and last model/Adam states for additional data.')
    config=json.loads(json.dumps(config))
    cp=a.out/'config.json'
    if cp.exists() and json.loads(cp.read_text())!=config:raise ValueError('Config/provenance changed on resume')
    if not cp.exists():atomic_json(cp,config)
    paths={s:[] for s in ('train','validation')}
    for e in ds['shards']:
        f=a.data/e['file']
        if sha(f)!=e['sha256']:raise ValueError('Frozen data changed')
        paths[e['split']].append((f,e['source']))
    for k,v in {'TF_CPP_MIN_LOG_LEVEL':'3','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':str(a.threads)}.items():os.environ.setdefault(k,v)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(a.threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(config['seed']);tf.config.experimental.enable_op_determinism()
    model=make_model(widths)
    with np.load(a.data/'parent.npz',allow_pickle=False) as z:parent=[z[f'w{i}'] for i in range(8)]
    model.set_weights(widen(parent,widths))
    optimizer=tf.keras.optimizers.AdamW(config['learning_rate'],weight_decay=.0001,clipnorm=1.)
    optimizer.build(model.trainable_variables)
    checkpoint=tf.train.Checkpoint(model=model,optimizer=optimizer)
    manager=tf.train.CheckpointManager(checkpoint,str(a.out/'checkpoints'),max_to_keep=2)
    selected_manager=tf.train.CheckpointManager(checkpoint,str(a.out/'selected-checkpoint'),max_to_keep=2)
    @tf.function(reduce_retracing=True)
    def predict(x):return model(x,training=False)
    @tf.function(reduce_retracing=True)
    def step(x,y,m,s):
        with tf.GradientTape() as tape:
            n,d=masked_loss(model(x,training=True),y,m,s);loss=n/tf.maximum(d,1.)
        optimizer.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
        return n,d
    def evaluate():
        sums={s:{k:np.zeros(4) for k in ('all','prefix','complete_auction')} for s in ('ben','bidding','play')}
        for path,source in paths['validation']:
            d=load(path)
            for start in range(0,len(d['kind']),1024):
                ix=slice(start,start+1024);x,y,m,s=batch(d,ix)
                prob=masked_probabilities(predict(x).numpy(),s)
                sums[source]['all']+=totals(prob,y,m)
                if source!='play':
                    for kind,label in [(0,'prefix'),(1,'complete_auction')]:
                        sums[source][label]+=totals(prob,y,m*(d['kind'][ix]==kind)[:,None])
        return {source:{k:summarize(v) for k,v in rows.items() if v[3]>0} for source,rows in sums.items()}
    def save_weights(path):np.savez_compressed(path,**{f'w{i}':w for i,w in enumerate(model.get_weights())})
    started=time.monotonic();state_path=a.out/'state.json'
    if state_path.exists():
        state=json.loads(state_path.read_text());checkpoint.restore(state['checkpoint']).assert_existing_objects_matched()
    else:
        initial=evaluate();save_weights(a.out/'initial.npz')
        from bridge_harness.bidding_sampling import AuctionWeights
        sample=load(paths['validation'][0][0]);x={k:sample[k][:128] for k in INPUTS}
        equivalence=float(np.max(np.abs(AuctionWeights(a.data/'parent.npz').predict(x)-model(x,training=False).numpy())))
        if equivalence>1e-5:raise ValueError('Initial predictions changed')
        state=dict(epoch=0,best_epoch=0,best_score=score(initial),initial_validation=initial,
            selected_validation=initial,history=[],complete=False,seconds=0.,initial_max_error=equivalence,
            checkpoint=manager.save(checkpoint_number=0),selected_checkpoint=selected_manager.save(checkpoint_number=0))
        save_weights(a.out/'best-epoch-0.npz');atomic_json(state_path,state)
        print(json.dumps(dict(event='initial',parameters=model.count_params(),metrics=initial)),flush=True)
    for epoch in range(state['epoch']+1,a.epochs+1):
        rng=np.random.default_rng(np.random.SeedSequence([config['seed'],epoch]));tf.keras.utils.set_random_seed(config['seed']+epoch)
        epoch_start=time.monotonic();sums=np.zeros(2);seen=0
        for i in rng.permutation(len(paths['train'])):
            d=load(paths['train'][i][0]);order=rng.permutation(len(d['kind']))
            for at in range(0,len(order),1024):
                ix=order[at:at+1024];x,y,m,s=batch(d,ix);n,den=step(x,y,m,s)
                sums+=[float(n),float(den)];seen+=len(y)
        val=evaluate();row=dict(epoch=epoch,seconds=time.monotonic()-epoch_start,rows=seen,
            train_nll=float(sums[0]/sums[1]),validation=val,selection_score=score(val))
        state['history'].append(row)
        if score(val)<state['best_score']-1e-5:
            state.update(best_epoch=epoch,best_score=score(val),selected_validation=val,
                selected_checkpoint=selected_manager.save(checkpoint_number=epoch))
            save_weights(a.out/f'best-epoch-{epoch}.npz')
        state.update(epoch=epoch,checkpoint=manager.save(checkpoint_number=epoch),complete=epoch==a.epochs)
        state['seconds']+=row['seconds'];atomic_json(state_path,state)
        print(json.dumps(row),flush=True)
        if time.monotonic()-started>=a.run_seconds:break
    chosen=a.out/f'best-epoch-{state["best_epoch"]}.npz';shutil.copyfile(chosen,a.out/'best.npz')
    with np.load(chosen,allow_pickle=False) as z:model.set_weights([z[f'w{i}'] for i in range(8)])
    sample=load(next(p for p,s in paths['validation'] if s=='play'));x={k:sample[k][:128] for k in INPUTS}
    err=float(np.max(np.abs(Weights(chosen).predict(x)-model(x,training=False).numpy())))
    if err>1e-5:raise ValueError(f'NumPy export differs: {err}')
    result=dict(size=a.size,parameters=model.count_params(),epoch=state['epoch'],best_epoch=state['best_epoch'],
        complete=state['complete'],active_seconds=state['seconds'],initial_validation=state['initial_validation'],
        selected_validation=state['selected_validation'],numpy_max_error=err,
        selected_weights=str(chosen.resolve()),selected_sha256=sha(chosen),test_evaluated=False,promoted=False,
        playing_strength_evaluated=False,selected_checkpoint=state['selected_checkpoint'],latest_checkpoint=state['checkpoint'])
    atomic_json(a.out/'result.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
