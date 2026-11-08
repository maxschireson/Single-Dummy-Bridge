#!/usr/bin/env python3
"""Small predeclared paired auction ablation on retrofitted play observations.

Identical architecture and seeds, differing only in whether auction tokens are
visible. Contract/declarer remain visible in both arms. No suit augmentation:
real bidding conventions are not invariant under arbitrary suit permutations.
Test metrics are computed once after all validation-selected runs complete.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.training import input_tensors
from bridge_harness.belief_model import encode_inputs, capacity_prior, masked_probabilities

CALLS = ['PASS','X','XX'] + [f'{level}{suit}' for level in range(1,8) for suit in 'CDHSN']
MAX_CALLS = 64


def auction_tokens(observation):
    calls = observation['auction']
    if len(calls)>MAX_CALLS: raise ValueError('Auction exceeds supported length; never truncate')
    tokens=np.zeros(MAX_CALLS,np.int32)
    tokens[:len(calls)]=[CALLS.index(c)+1 for c in calls]
    return tokens


def load_data(root):
    groups={s:[] for s in ('train','validation','test')}
    for path in sorted((root/'episodes').glob('*.json.gz')):
        with gzip.open(path,'rt') as f:e=json.load(f)
        assert len(e['examples'])==52
        groups[e['examples'][0]['metadata']['split']].append(e['examples'])
    out={}
    seen=set()
    for split,episodes in groups.items():
        ids=[e[0]['metadata']['split_group'] for e in episodes]
        assert len(set(ids))==len(ids) and not seen.intersection(ids)
        seen.update(ids)
        rows=[r for e in episodes for r in e]
        inputs=[input_tensors(r['observation']) for r in rows]
        a={k:np.stack([r[k] for r in inputs]) for k in inputs[0]}
        x=encode_inputs(a)
        x['auction']=np.stack([auction_tokens(r['observation']) for r in rows])
        prior=capacity_prior(a['owner_support'],a['remaining_counts'])
        y=np.array([r['belief_target']['remaining_owner'] for r in rows],np.int32)
        mask=np.array([r['belief_target']['unknown_mask'] for r in rows]) & (a['owner_support'].sum(-1)>1)
        y=np.maximum(y,0)
        assert np.all(~mask | np.take_along_axis(a['owner_support'],y[...,None],-1)[...,0])
        out[split]=dict(x=x,y=y,mask=mask,support=a['owner_support'],
            logprior=np.log(np.maximum(prior,1e-12)),prior=prior,
            deal=np.repeat(np.arange(len(episodes)),52),deals=len(episodes),ids=ids,
            ply=np.array([r['metadata']['ply'] for r in rows]))
    return out


def metric_rows(p,d):
    truth=np.take_along_axis(p,d['y'][...,None],-1)[...,0]
    mask=d['mask']
    return np.stack([(-np.log(np.maximum(truth,1e-12))*mask).sum(-1),
        ((p.argmax(-1)==d['y'])*mask).sum(-1),
        ((np.square(p).sum(-1)-2*truth+1)*mask).sum(-1),mask.sum(-1)],axis=1)


def metrics(rows):
    nll,acc,brier,count=rows.sum(0)
    return dict(nll=float(nll/count),accuracy=float(acc/count),brier=float(brier/count),labels=int(count))


def build_model(state_size):
    import tensorflow as tf
    k=tf.keras
    state=k.Input((state_size,),name='state')
    cards=k.Input((52,),dtype='int32',name='cards')
    seats=k.Input((52,),dtype='int32',name='seats')
    auction=k.Input((MAX_CALLS,),dtype='int32',name='auction')
    c=k.layers.Flatten()(k.layers.Embedding(53,4)(cards))
    s=k.layers.Flatten()(k.layers.Embedding(5,4)(seats))
    a=k.layers.Flatten()(k.layers.Embedding(len(CALLS)+1,4)(auction))
    x=k.layers.Concatenate()([state,c,s,a])
    x=k.layers.Dense(16,activation='relu')(x)
    x=k.layers.Dropout(.15)(x)
    x=k.layers.Dense(16,activation='relu')(x)
    x=k.layers.Dense(208,kernel_initializer='zeros')(x)
    logits=k.layers.Reshape((52,4))(x)
    return k.Model(dict(state=state,cards=cards,seats=seats,auction=auction),logits)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise ValueError('Refuse overwrite')
    args.out.mkdir(parents=True)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.config.experimental.enable_op_determinism()
    data=load_data(args.data)
    manifest=dict(encoder='auction-play-v1',architecture='ordered embeddings; Dense16/Dense16 residual ownership logits',
        seeds=[731,732,733],epochs=60,patience=8,batch_size=512,learning_rate=.001,
        weight_decay=.001,selection='best validation NLL including untrained capacity prior',
        ablation='auction tokens versus all-zero tokens; final contract and all other observations identical',
        splits={s:dict(deals=d['deals'],rows=len(d['y'])) for s,d in data.items()},
        loss='uncertain hidden-card cross entropy',baseline='capacity-balanced approximate feasible-ownership marginals',
        test_policy='evaluated only after all six validation-selected fits finish',
        split_ids={s:d['ids'] for s,d in data.items()},suit_augmentation=False,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        data_summary_sha256=hashlib.sha256((args.data/'summary.json').read_bytes()).hexdigest(),
        limitations=['608 matched deals are a selected subset','no playing-strength evaluation','behavior ignored auction'])
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'event':'data','splits':manifest['splits']}),flush=True)
    baseline={s:metrics(metric_rows(d['prior'],d)) for s,d in data.items() if s!='test'}
    print(json.dumps({'event':'baseline',**baseline}),flush=True)
    runs=[];started=time.perf_counter()
    for seed in manifest['seeds']:
        for mode in ('no_auction','auction'):
            tf.keras.backend.clear_session();tf.keras.utils.set_random_seed(seed)
            rng=np.random.default_rng(seed)
            model=build_model(data['train']['x']['state'].shape[1]);params=model.count_params()
            optimizer=tf.keras.optimizers.AdamW(.001,weight_decay=.001,clipnorm=1.)
            path=args.out/f'{mode}-{seed}';path.mkdir()
            x={s:{**d['x'],'auction':d['x']['auction'] if mode=='auction' else np.zeros_like(d['x']['auction'])} for s,d in data.items()}

            @tf.function(reduce_retracing=True)
            def step(inp,y,mask,support,logprior):
                with tf.GradientTape() as tape:
                    logits=model(inp,training=True)+logprior
                    logits=tf.where(support,logits,tf.constant(-1e9,dtype=logits.dtype))
                    losses=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,logits=logits)
                    m=tf.cast(mask,logits.dtype)
                    loss=tf.reduce_sum(losses*m)/tf.maximum(tf.reduce_sum(m),1.)
                optimizer.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
                return loss

            def predict(split):
                d=data[split];pred=[]
                for at in range(0,len(d['y']),512):
                    sl=slice(at,at+512)
                    logits=model({k:v[sl] for k,v in x[split].items()},training=False).numpy()+d['logprior'][sl]
                    pred.append(masked_probabilities(logits,d['support'][sl]))
                return np.concatenate(pred)

            best=baseline['validation']['nll'];best_epoch=0;stale=0;history=[]
            model.save(path/'best.keras')
            d=data['train']
            for epoch in range(1,61):
                order=rng.permutation(len(d['y']));losses=[]
                for at in range(0,len(order),512):
                    ix=order[at:at+512]
                    losses.append(float(step({k:v[ix] for k,v in x['train'].items()},d['y'][ix],d['mask'][ix],d['support'][ix],d['logprior'][ix])))
                val=metrics(metric_rows(predict('validation'),data['validation']))
                history.append(dict(epoch=epoch,train_nll=float(np.mean(losses)),validation=val))
                if val['nll']<best-1e-5:
                    best=val['nll'];best_epoch=epoch;stale=0;model.save(path/'best.keras')
                else:stale+=1
                if stale>=8:break
            (path/'history.json').write_text(json.dumps(history,indent=2))
            run=dict(mode=mode,seed=seed,parameters=params,best_epoch=best_epoch,best_validation_nll=best,
                     epochs=len(history),last_train_nll=history[-1]['train_nll'])
            runs.append(run);print(json.dumps({'event':'fit',**run}),flush=True)
    # Fits and checkpoint choices are frozen before this one test evaluation.
    test=data['test'];prediction={m:[] for m in ('no_auction','auction')}
    for run in runs:
        model=tf.keras.models.load_model(args.out/f"{run['mode']}-{run['seed']}"/'best.keras')
        inp={**test['x'],'auction':test['x']['auction'] if run['mode']=='auction' else np.zeros_like(test['x']['auction'])}
        chunks=[]
        for at in range(0,len(test['y']),512):
            sl=slice(at,at+512)
            logits=model({k:v[sl] for k,v in inp.items()},training=False).numpy()+test['logprior'][sl]
            chunks.append(masked_probabilities(logits,test['support'][sl]))
        prob=np.concatenate(chunks);prediction[run['mode']].append(prob)
        run['test']=metrics(metric_rows(prob,test))
    ensembles={m:np.mean(v,axis=0) for m,v in prediction.items()}
    ensembles['capacity_prior']=test['prior']
    rows={m:metric_rows(v,test) for m,v in ensembles.items()}
    grouped={m:np.array([r[test['deal']==i].sum(0) for i in range(test['deals'])]) for m,r in rows.items()}
    rng=np.random.default_rng(20261108);boot={m:[] for m in ('no_auction','capacity_prior')}
    for _ in range(2000):
        ix=rng.integers(test['deals'],size=test['deals'])
        for m in boot:
            boot[m].append(metrics(grouped[m][ix])['nll']-metrics(grouped['auction'][ix])['nll'])
    result=dict(parameters=params,runs=runs,baseline=baseline,
        test={m:metrics(r) for m,r in rows.items()},
        test_stage={stage:{m:metrics(r[sel]) for m,r in rows.items()} for stage,sel in
            [('early',test['ply']<16),('middle',(test['ply']>=16)&(test['ply']<36)),('late',test['ply']>=36)]},
        auction_nll_improvement={m:dict(estimate=metrics(rows[m])['nll']-metrics(rows['auction'])['nll'],
             deal_bootstrap_95ci=np.quantile(v,[.025,.975]).tolist()) for m,v in boot.items()},
        seconds=time.perf_counter()-started,splits=manifest['splits'],test_evaluated=True,
        strength_evaluated=False,model_deployed=False)
    np.savez_compressed(args.out/'test_deal_metrics.npz',**grouped)
    (args.out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'event':'done',**result}),flush=True)


if __name__=='__main__':main()
