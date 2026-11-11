#!/usr/bin/env python3
"""Train a tiny near-tie selector from randomized logged self-play outcomes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.policy_selector import INPUT_KEYS, encode, build_model, SelectorWeights
from train_belief import inspect_dataset, sha


def load_data(path, suits=None):
    with np.load(path,allow_pickle=False) as z:
        take=z['selector_mask']
        a={k:z[k][take] for k in INPUT_KEYS}
        policy=z['behavior_policy'][take];utility=z['pimc_utility'][take]
        x,cards=encode(a,policy,utility,suits)
        chosen=z['action_target'][take]
        match=(cards==chosen[:,None]) & (x['mask']>0)
        assert np.all(match.sum(1)==1)
        y=z['return_target'][take]
        return x,y,match.argmax(1).astype(np.int32),z['split_group'][take]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=12);p.add_argument('--patience',type=int,default=3)
    p.add_argument('--seed',type=int,default=20261120);p.add_argument('--batch-size',type=int,default=512)
    args=p.parse_args();assert not args.out.exists();args.out.mkdir(parents=True)
    audit=json.loads((args.data/'audit-10000.json').read_text())
    dirs,provenance=inspect_dataset(args.data,audit)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(args.seed);tf.config.experimental.enable_op_determinism()
    rng=np.random.default_rng(args.seed)
    first=load_data(dirs[0]/'validation.npz')
    model=build_model(first[0]['state'].shape[-1],first[0]['actions'].shape[-1])
    optimizer=tf.keras.optimizers.AdamW(learning_rate=1e-3,weight_decay=1e-3,clipnorm=1.)
    manifest=dict(parameters=model.count_params(),train_deals=7993,validation_deals=1008,
        train_selector_rows=259299,validation_selector_rows=32554,
        datasets=provenance,seed=args.seed,selection='lowest validation chosen-action MSE',
        targets='remaining acting-partnership tricks on chosen action only',
        action_centering='uniform mean over the recorded eligible candidates',
        augmentation='one random suit permutation per training shard per epoch; seats relative to actor',
        test_labels_used=False,tensorflow=tf.__version__,numpy=np.__version__,
        source_hashes={s:sha(Path(__file__).resolve().parents[1]/s) for s in
            ['bridge_harness/policy_selector.py','scripts/train_policy_selector.py']})
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(dict(event='start',parameters=model.count_params())),flush=True)

    def outputs(x,training):
        raw=model({k:tf.cast(x[k],tf.float32) for k in ('state','actions')},training=training)
        scores=raw['score'][...,0]
        centered=scores-tf.reduce_sum(scores*x['mask'],axis=1,keepdims=True)/tf.reduce_sum(x['mask'],axis=1,keepdims=True)
        value=raw['value']
        return x['q']+value+centered, x['q']+value

    @tf.function(reduce_retracing=True)
    def train_step(x,y,chosen):
        with tf.GradientTape() as tape:
            pred,_=outputs(x,True)
            logged=tf.gather(pred,chosen,axis=1,batch_dims=1)
            loss=tf.reduce_mean(tf.square(logged-y))
        optimizer.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
        return loss

    @tf.function(reduce_retracing=True)
    def predict(x):return outputs(x,False)

    validation=[load_data(d/'validation.npz') for d in dirs]
    def evaluate(save_rows=False):
        totals=np.zeros(4); all_rows=[]
        for x,y,chosen,groups in validation:
            for start in range(0,len(y),args.batch_size):
                sl=slice(start,start+args.batch_size);xx={k:v[sl] for k,v in x.items()}
                pred,baseline=[v.numpy() for v in predict(xx)];rr=np.arange(len(pred));a=chosen[sl]
                log=pred[rr,a];base=baseline[rr,a];q=xx['q'][rr,a]
                totals += [np.square(log-y[sl]).sum(),np.square(base-y[sl]).sum(),np.square(q-y[sl]).sum(),len(pred)]
                if save_rows:
                    best=np.where(xx['mask']>0,pred,-np.inf).argmax(1)
                    count=xx['mask'].sum(1);w=(best==a)*count
                    # Contextual-bandit DR diagnostic: improve this one choice,
                    # then follow the old behavior. Not a full-game estimate.
                    dr=pred[rr,best]-(pred*xx['mask']).sum(1)/count+(w-1)*(y[sl]-log)
                    all_rows.extend(zip(groups[sl].tolist(),dr.tolist()))
        result=dict(mse=float(totals[0]/totals[3]),without_action_head_mse=float(totals[1]/totals[3]),
            pimc_mse=float(totals[2]/totals[3]),rows=int(totals[3]))
        if save_rows:
            grouped={}
            for group,value in all_rows:grouped.setdefault(group,[]).append(value)
            means=np.array([np.mean(v) for v in grouped.values()]);brng=np.random.default_rng(20261121)
            boot=[means[brng.integers(len(means),size=len(means))].mean() for _ in range(3000)]
            result['exploratory_validation_dr']=dict(mean_single_decision_tricks=float(means.mean()),
                deal_bootstrap_95=np.quantile(boot,[.025,.975]).tolist(),deals=len(means),
                note='validation is used for model selection; diagnostic only, not independent full-game evidence')
        return result

    before=evaluate();best=before['mse'];stale=0;best_epoch=0
    model.save(args.out/'best.keras');history=[];started=time.perf_counter()
    print(json.dumps(dict(event='initial',**before)),flush=True)
    for epoch in range(1,args.epochs+1):
        begin=time.perf_counter();sums=np.zeros(2)
        for di in rng.permutation(len(dirs)):
            x,y,chosen,_=load_data(dirs[di]/'train.npz',rng.permutation(4))
            order=rng.permutation(len(y))
            for start in range(0,len(y),args.batch_size):
                idx=order[start:start+args.batch_size]
                loss=train_step({k:v[idx] for k,v in x.items()},y[idx],chosen[idx])
                sums += [float(loss)*len(idx),len(idx)]
        metrics=evaluate();row=dict(epoch=epoch,seconds=time.perf_counter()-begin,train_mse=sums[0]/sums[1],validation=metrics)
        history.append(row)
        with (args.out/'history.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
        if metrics['mse'] < best-1e-5:
            best=metrics['mse'];best_epoch=epoch;stale=0;model.save(args.out/'best.keras')
        else:stale+=1
        if stale>=args.patience:break
    model=tf.keras.models.load_model(args.out/'best.keras',compile=False)
    weights={}
    for name in ('state_hidden','state_value','action_hidden','action_hidden_2','action_score'):
        weights[name+'_kernel'],weights[name+'_bias']=model.get_layer(name).get_weights()
    np.savez_compressed(args.out/'weights.npz',**weights)
    # Rebuild the traced closure for the restored model, then check NumPy.
    predict=tf.function(lambda x:outputs(x,False),reduce_retracing=True)
    x={k:v[:2048] for k,v in first[0].items()}
    diff=float(np.abs(SelectorWeights(args.out/'weights.npz').predict(x)-predict(x)[0].numpy()).max())
    assert diff<1e-5
    result=dict(status='complete',parameters=model.count_params(),best_epoch=best_epoch,
        epochs=len(history),seconds=time.perf_counter()-started,validation=evaluate(True),
        test_labels_used=False,numpy_max_absolute_error=diff,
        weights_sha256=sha(args.out/'weights.npz'),checkpoint_sha256=sha(args.out/'best.keras'))
    (args.out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':main()
