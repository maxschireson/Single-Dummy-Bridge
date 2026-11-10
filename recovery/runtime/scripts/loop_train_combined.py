#!/usr/bin/env python3
"""Warm-start both v2 networks from audited, exploratory self-play.

Fits chosen-action returns with known propensity correction to uniform support.
No unplayed-action return is invented. Internal test/arena outcomes are unused.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha,verify_bot
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import examples_from_record,input_tensors,split_for,digest
from bridge_harness.core import Board,card


def prepare_policy(req,out):
    import numpy as np
    from bridge_harness.policy_selector import INPUT_KEYS
    if sha(req['dataset'])!=req['dataset_sha256']:raise ValueError('Dataset changed')
    dataset=read(req['dataset']);paths={'train':[],'validation':[]};seen=set();counts={s:0 for s in paths}
    for i,shard in enumerate(dataset['shards']):
        root=Path(shard['path'])
        if sha(root/'shard.json')!=shard['sha256']:raise ValueError('Shard changed')
        rows={s:[] for s in paths}
        for name,expected in read(root/'shard.json')['episodes'].items():
            path=root/'episodes'/name
            if sha(path)!=expected:raise ValueError('Episode changed')
            record=read(path);board=Board.from_dict(record['board']);did=digest(board.hands)
            if did in seen:raise ValueError('Duplicate deal')
            seen.add(did);split=split_for(board)
            if split not in rows or not board.contract:continue
            counts[split]+=1
            for e,action in zip(examples_from_record(record,did),record['tables'][0]['actions']):
                proposal=action.get('proposal_probabilities',action.get('behavior_probabilities',{}))
                support=[c for c,p in proposal.items() if p>0]
                if len(support)<2:continue
                actual=e['policy_target']['selected_probability']
                if actual<=0:raise ValueError('Nonpositive behavior propensity')
                inputs=input_tensors(e['observation']);q=np.full(52,np.nan,np.float32);policy=np.zeros(52,np.float32)
                for c in support:policy[card(c)]=1/len(support)
                for c,value in action['estimates'].items():q[card(c)]=value['utility']
                rows[split].append((inputs,policy,q,e['policy_target']['action'],
                    e['policy_target']['remaining_actor_tricks'],1/(len(support)*actual),did))
        for split,examples in rows.items():
            if not examples:continue
            arrays={k:np.stack([r[0][k] for r in examples]) for k in INPUT_KEYS}
            arrays.update(policy=np.stack([r[1] for r in examples]),utility=np.stack([r[2] for r in examples]),
                chosen=np.array([r[3] for r in examples],np.int32),y=np.array([r[4] for r in examples],np.float32),
                weight=np.array([r[5] for r in examples],np.float32),group=np.array([r[6] for r in examples]))
            path=out/f'{split}-{i}.npz';np.savez_compressed(path,**arrays);paths[split].append(path)
        print(json.dumps(dict(event='policy-data',shard=i+1,deals=len(seen))),flush=True)
    if len(seen)!=dataset['independent_deals'] or not all(paths.values()):raise ValueError('Incomplete or empty fit data')
    return paths,counts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True);p.add_argument('--epochs',type=int,default=8)
    p.add_argument('--patience',type=int,default=2);p.add_argument('--threads',type=int,default=4)
    p.add_argument('--batch-size',type=int,default=512)
    a=p.parse_args();req=read(a.request);parent=verify_bot(req['parent_manifest'])
    if parent['spec']['factory']!='bridge_harness.combined_player:CombinedPlayer':raise ValueError('Combined v2 parent required')
    output=Path(req['output']);out=output.parent/'combined-training';out.mkdir(exist_ok=True)
    for k,v in {'TF_CPP_MIN_LOG_LEVEL':'3','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':str(a.threads)}.items():os.environ.setdefault(k,v)
    started=time.monotonic()
    belief_req={**req,'output':str(out/'belief-result.json')};atomic_json(out/'belief-request.json',belief_req)
    # Separate process releases TensorFlow memory before the selector fit.
    subprocess.run([sys.executable,str(ROOT/'scripts/loop_train_auction.py'),'--request',str(out/'belief-request.json'),
                    '--epochs',str(a.epochs),'--patience',str(a.patience),'--threads',str(a.threads)],check=True)
    belief_result=read(out/'belief-result.json')
    import numpy as np
    from bridge_harness.policy_selector import INPUT_KEYS,encode,build_model,SelectorWeights
    paths,counts=prepare_policy(req,out)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(a.threads);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(req['seed']);tf.config.experimental.enable_op_determinism()
    rng=np.random.default_rng(req['seed'])
    def load(path,suits=None):
        with np.load(path,allow_pickle=False) as z:
            x,cards=encode({k:z[k] for k in INPUT_KEYS},z['policy'],z['utility'],suits)
            match=(cards==z['chosen'][:,None])&(x['mask']>0)
            if not np.all(match.sum(1)==1):raise ValueError('Chosen action outside support')
            return x,z['y'],match.argmax(1).astype(np.int32),z['weight']
    first=load(paths['validation'][0]);model=build_model(first[0]['state'].shape[-1],first[0]['actions'].shape[-1])
    key=parent['spec']['kwargs']['policy'].removeprefix('$artifact:')
    parent_weights=Path(req['parent_manifest']).parent/parent['spec']['artifacts'][key]['file']
    names=('state_hidden','state_value','action_hidden','action_hidden_2','action_score')
    def restore(path):
        with np.load(path,allow_pickle=False) as z:
            for name in names:model.get_layer(name).set_weights([z[name+'_kernel'],z[name+'_bias']])
    restore(parent_weights)
    optimizer=tf.keras.optimizers.AdamW(1e-3,weight_decay=1e-3,clipnorm=1.)
    def outputs(x,training=False):
        raw=model({k:tf.cast(x[k],tf.float32) for k in ('state','actions')},training=training)
        score=raw['score'][...,0]
        centered=score-tf.reduce_sum(score*x['mask'],axis=1,keepdims=True)/tf.reduce_sum(x['mask'],axis=1,keepdims=True)
        return x['q']+raw['value']+centered
    @tf.function(reduce_retracing=True)
    def step(x,y,chosen,weight):
        with tf.GradientTape() as tape:
            pred=tf.gather(outputs(x,True),chosen,axis=1,batch_dims=1)
            loss=tf.reduce_sum(tf.square(pred-y)*weight)/tf.reduce_sum(weight)
        optimizer.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
        return loss
    @tf.function(reduce_retracing=True)
    def predict(x):return outputs(x)
    def evaluate():
        sums=np.zeros(4)
        for path in paths['validation']:
            x,y,chosen,w=load(path)
            for at in range(0,len(y),a.batch_size):
                ix=slice(at,at+a.batch_size);xx={k:v[ix] for k,v in x.items()}
                pred=predict(xx).numpy();value=pred[np.arange(len(pred)),chosen[ix]]
                sums += [np.sum((value-y[ix])**2*w[ix]),w[ix].sum(),(w[ix]**2).sum(),len(pred)]
        return dict(mse=float(sums[0]/sums[1]),rows=int(sums[3]),propensity_row_ess=float(sums[1]**2/sums[2]))
    initial=evaluate();best=initial['mse'];best_epoch=0;stale=0;selected=parent_weights;history=[]
    print(json.dumps(dict(event='policy-parent-validation',**initial)),flush=True)
    for epoch in range(1,a.epochs+1):
        for i in rng.permutation(len(paths['train'])):
            x,y,chosen,w=load(paths['train'][i],rng.permutation(4));order=rng.permutation(len(y))
            for at in range(0,len(y),a.batch_size):
                ix=order[at:at+a.batch_size];step({k:v[ix] for k,v in x.items()},y[ix],chosen[ix],w[ix])
        val=evaluate();history.append(dict(epoch=epoch,validation=val));atomic_json(out/'policy-history.json',history)
        print(json.dumps(history[-1]),flush=True)
        if val['mse']<best-1e-5:
            best=val['mse'];best_epoch=epoch;stale=0;selected=out/'policy-best.npz';weights={}
            for name in names:weights[name+'_kernel'],weights[name+'_bias']=model.get_layer(name).get_weights()
            np.savez_compressed(selected,**weights)
        else:stale+=1
        if stale>=a.patience:break
    restore(selected)
    x={k:v[:256] for k,v in first[0].items()};err=float(np.abs(SelectorWeights(selected).predict(x)-predict(x).numpy()).max())
    if err>1e-5:raise ValueError('NumPy/TensorFlow selector inference mismatch')
    spec=belief_result['bot'];spec['artifacts'][key]=str(selected)
    provenance={k:req[k] for k in ('dataset_sha256','parent_identity','seed')}
    provenance.update(selection_split='validation',test_access=False,seconds=time.monotonic()-started,
        belief=belief_result['training'],policy=dict(best_epoch=best_epoch,parent_validation=initial,
        selected_validation=evaluate(),deals=counts,loss='chosen-return MSE weighted by uniform/behavior propensity',
        actual_behavior='epsilon exploration within fixed PIMC window',numpy_max_error=err),
        note='Improved validation does not establish improved play; arena still required')
    atomic_json(output,dict(bot=spec,training=provenance))


if __name__=='__main__':main()
