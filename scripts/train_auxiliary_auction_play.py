#!/usr/bin/env python3
"""Pair each original deal's genuine auction with its synthetic-contract play.

The original played contract, dummy, actor and history are never relabelled.
The auction is an auxiliary same-deal information signal, not a claimed legal
auction/play transcript. This experiment trains ownership only, not a policy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import Board
from bridge_harness.training import digest
from bridge_harness.belief_model import INPUT_KEYS, encode_inputs, capacity_prior, masked_probabilities
from scripts.train_reauction_belief import auction_tokens, build_model, metric_rows, metrics


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--auctions',type=Path,required=True)
    p.add_argument('--matched',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise ValueError('Refuse overwrite')
    args.out.mkdir(parents=True)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.config.experimental.enable_op_determinism()
    audit=json.loads((args.data/'audit-10000.json').read_text())
    if not audit['validated'] or audit['independent_deals']!=10000:raise ValueError('10k audit required')
    bids={};bid_context={}
    for line in (args.auctions/'frozen.jsonl').read_text().splitlines():
        b=Board.from_dict(json.loads(line));h=digest(b.hands)
        if h in bids:raise ValueError('Duplicate auction')
        bids[h]=auction_tokens({'auction':list(b.auction)})
        bid_context[h]=(b.dealer,('None','NS','EW','Both').index(b.vulnerability))
    assert len(bids)==10000
    matched={r['deal_id'] for r in json.loads((args.matched/'matches.json').read_text())}
    directories={s:[] for s in ('train','validation','test')};groups={s:set() for s in directories}
    start=time.perf_counter()
    # Memory-bounded preprocessing. Cache only observation-derived arrays, prior,
    # separate labels and group IDs; never pass deal IDs/full hands to the network.
    for i in range(10):
        for split in directories:
            path=args.data/f'chunk-{i}'/f'{split}.npz'
            with np.load(path,allow_pickle=False) as z:
                a={k:z[k] for k in INPUT_KEYS};ids=z['split_group']
                unique,counts=np.unique(ids,return_counts=True)
                if np.any(counts!=52) or groups[split].intersection(unique):raise ValueError('Bad source groups')
                groups[split].update(unique)
                context=np.array([bid_context[h] for h in ids])
                if not np.array_equal(context,a['context'][:,7:9]):raise ValueError('Auction dealer/vulnerability differs')
                x=encode_inputs(a)
                x['auction']=np.stack([bids[h] for h in ids])
                support=a['owner_support'];y=np.maximum(z['owner_target'].astype(np.int32),0)
                mask=z['owner_loss_mask']
                if np.any(mask & ~np.take_along_axis(support,y[...,None],-1)[...,0]):raise ValueError('Impossible label')
                if np.any(mask & (support.sum(-1)<=1)):raise ValueError('Known cards in loss')
                prior=capacity_prior(support,a['remaining_counts'])
                data={**x,'y':y,'mask':mask,'support':support,'logprior':np.log(np.maximum(prior,1e-12)),
                      'group':ids,'matched':np.isin(ids,list(matched)),'ply':a['context'][:,-1]}
            d=args.out/'cache'/split/f'chunk-{i}';d.mkdir(parents=True)
            for k,v in data.items():np.save(d/(k+'.npy'),v)
            directories[split].append(d)
        print(json.dumps({'event':'prepared','chunk':i,'seconds':time.perf_counter()-start}),flush=True)
    for s in groups:
        for t in groups:
            if s!=t:assert not groups[s].intersection(groups[t])
        assert len(groups[s])==audit['splits'][s]['games']
    assert set.union(*groups.values())==set(bids)
    manifest=dict(schema='auxiliary-auction-play-v1',deals=10000,
        splits={s:len(g) for s,g in groups.items()},seeds=[731,732,733],epochs=40,patience=6,
        batch_size=1024,architecture='same 22676-parameter model as matched608 experiment',
        auction_semantics='genuine BEN auction for same cards, auxiliary to original played contract',
        preserved='original played contract/declarer/dummy/actor/vulnerability/history/labels',
        selection='minimum all-deal validation NLL; epoch-zero prior eligible',
        test_policy='one evaluation after all six fits; old test split reused, exploratory not fresh',
        baseline='capacity-balanced approximate ownership marginals',
        strength_evaluated=False,suit_augmentation=False,
        audit_sha256=hashlib.sha256((args.data/'audit-10000.json').read_bytes()).hexdigest(),
        auction_sha256=hashlib.sha256((args.auctions/'frozen.jsonl').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    keys=['state','cards','seats','auction','y','mask','support','logprior','group','matched','ply']
    def load(d):return {k:np.load(d/(k+'.npy'),mmap_mode='r',allow_pickle=False) for k in keys}
    xkeys=['state','cards','seats','auction']
    def inp(d,ix,mode):
        x={k:np.asarray(d[k][ix]) for k in xkeys}
        if mode=='no_auction':x['auction']=np.zeros_like(x['auction'])
        return x
    def evaluate(model,mode,split,collect=False):
        sums={k:np.zeros(4,np.float64) for k in ['all','matched','early','middle','late']};bydeal={}
        for path in directories[split]:
            d=load(path)
            for at in range(0,len(d['y']),1024):
                ix=slice(at,at+1024)
                logits=np.array(d['logprior'][ix],copy=True)
                if model is not None:logits+=model(inp(d,ix,mode),training=False).numpy()
                prob=masked_probabilities(logits,d['support'][ix])
                r=metric_rows(prob,{k:d[k][ix] for k in ['y','mask']})
                sums['all']+=r.sum(0);sums['matched']+=r[d['matched'][ix]].sum(0)
                ply=d['ply'][ix]
                for name,mask in [('early',ply<16),('middle',(ply>=16)&(ply<36)),('late',ply>=36)]:sums[name]+=r[mask].sum(0)
                if collect:
                    ids=d['group'][ix]
                    for h in np.unique(ids):bydeal.setdefault(str(h),np.zeros(4,np.float64));bydeal[str(h)]+=r[ids==h].sum(0)
        return {k:metrics(v[None,:]) for k,v in sums.items()},bydeal
    baseline,_=evaluate(None,'no_auction','validation')
    print(json.dumps({'event':'baseline','validation':baseline}),flush=True)
    (args.out/'baseline.json').write_text(json.dumps(baseline,indent=2))
    runs=[];train_start=time.perf_counter()
    state_size=load(directories['train'][0])['state'].shape[1]
    for seed in manifest['seeds']:
        for mode in ('no_auction','auction'):
            tf.keras.backend.clear_session();tf.keras.utils.set_random_seed(seed);rng=np.random.default_rng(seed)
            model=build_model(state_size);optimizer=tf.keras.optimizers.AdamW(.001,weight_decay=.001,clipnorm=1.)
            path=args.out/f'{mode}-{seed}';path.mkdir();model.save(path/'best.keras')
            best=baseline['all']['nll'];best_epoch=0;stale=0;history=[]
            @tf.function(reduce_retracing=True)
            def step(x,y,mask,support,prior):
                with tf.GradientTape() as tape:
                    logits=model(x,training=True)+prior
                    logits=tf.where(support,logits,tf.constant(-1e9,dtype=logits.dtype))
                    losses=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,logits=logits)
                    m=tf.cast(mask,logits.dtype);num=tf.reduce_sum(losses*m);den=tf.reduce_sum(m)
                    loss=num/tf.maximum(den,1.)
                optimizer.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
                return num,den
            for epoch in range(1,41):
                begin=time.perf_counter();tot=np.zeros(2,np.float64)
                for j in rng.permutation(10):
                    d=load(directories['train'][j]);order=rng.permutation(len(d['y']))
                    for at in range(0,len(order),1024):
                        ix=order[at:at+1024]
                        num,den=step(inp(d,ix,mode),d['y'][ix],d['mask'][ix],d['support'][ix],d['logprior'][ix])
                        tot += [float(num),float(den)]
                val,_=evaluate(model,mode,'validation')
                row=dict(epoch=epoch,train_nll=float(tot[0]/tot[1]),validation=val,seconds=time.perf_counter()-begin)
                history.append(row)
                with (path/'history.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
                if val['all']['nll']<best-1e-5:
                    best=val['all']['nll'];best_epoch=epoch;stale=0;model.save(path/'best.keras')
                else:stale+=1
                print(json.dumps({'event':'epoch','mode':mode,'seed':seed,**row}),flush=True)
                if stale>=6:break
            model.save(path/'last.keras')
            runs.append(dict(mode=mode,seed=seed,best_epoch=best_epoch,best_validation_nll=best,epochs=len(history)))
    # Do not tune after viewing these reused test results.
    base_test,base_deals=evaluate(None,'no_auction','test',collect=True)
    deal_metrics={};test_ids=sorted(base_deals)
    for run in runs:
        model=tf.keras.models.load_model(args.out/f"{run['mode']}-{run['seed']}"/'best.keras')
        val,_=evaluate(model,run['mode'],'validation')
        test,deals=evaluate(model,run['mode'],'test',collect=True)
        run.update(validation=val,test=test)
        deal_metrics[f"{run['mode']}_{run['seed']}"]=np.array([deals[h] for h in test_ids])
    deal_metrics['prior']=np.array([base_deals[h] for h in test_ids])
    # Average per-seed loss differences; this is not an ensemble predictor.
    means={m:np.mean([deal_metrics[f'{m}_{s}'] for s in manifest['seeds']],axis=0) for m in ('auction','no_auction')}
    means['prior']=deal_metrics['prior'];rng=np.random.default_rng(20261108)
    boot={m:[] for m in ('no_auction','prior')}
    for _ in range(2000):
        ix=rng.integers(len(test_ids),size=len(test_ids))
        for m in boot:boot[m].append(metrics(means[m][ix])['nll']-metrics(means['auction'][ix])['nll'])
    result=dict(status='complete',parameters=model.count_params(),runs=runs,baseline_validation=baseline,
        baseline_test=base_test,mean_seed_test={m:metrics(v) for m,v in means.items()},
        auction_nll_improvement={m:dict(estimate=metrics(means[m])['nll']-metrics(means['auction'])['nll'],
            deal_bootstrap_95ci=np.quantile(v,[.025,.975]).tolist()) for m,v in boot.items()},
        training_seconds=time.perf_counter()-train_start,total_seconds=time.perf_counter()-start,
        splits=manifest['splits'],test_reused=True,strength_evaluated=False,deployed=False)
    np.savez_compressed(args.out/'test_deal_metrics.npz',**deal_metrics)
    (args.out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'event':'done','mean_seed_test':result['mean_seed_test'],'auction_nll_improvement':result['auction_nll_improvement']}),flush=True)


if __name__=='__main__':main()
