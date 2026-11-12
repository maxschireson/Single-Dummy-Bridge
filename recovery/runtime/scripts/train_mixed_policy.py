"""Fine-tune the auction/history action network ONLY on audited IMP contrasts."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.auction_policy import build_model,restore_parent,export_weights
from bridge_harness.improvement import read,writer_lock
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import IMPSelector
from bridge_harness.selfplay import atomic_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('data','out','parent'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--epochs',type=int,default=8);p.add_argument('--seconds',type=float,default=240)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(202611093);tf.config.experimental.enable_op_determinism()
    with writer_lock(a.out):
        ds=read(a.data/'dataset.json')
        if ds['schema']!='audited-neural-imp-v1' or not ds['validated']:raise ValueError('Audited IMP data required')
        paths={s:[a.data/e['file'] for e in ds['shards'] if e['split']==s] for s in ('train','validation')}
        if not all(paths.values()):raise ValueError('Need train and held-out audit families')
        for e in ds['shards']:
            if sha(a.data/e['file'])!=e['sha256']:raise ValueError('Training shard changed')
        def load(path):
            with np.load(path,allow_pickle=False) as z:return {k:z[k] for k in z.files}
        first=load(paths['validation'][0]);model=build_model(first['state'].shape[-1],first['actions'].shape[-1]);restore_parent(model,a.parent)
        with np.load(a.parent,allow_pickle=False) as z:
            is_imp='imp_neural' in z;q_initial=float(z['imp_q_scale']) if is_imp else 0.
        if not is_imp:
            model.get_layer('action_score').set_weights([np.zeros_like(w) for w in model.get_layer('action_score').get_weights()])
        q_scale=tf.Variable(q_initial,dtype=tf.float32,trainable=True,name='imp_q_scale')
        variables=[v for v in model.trainable_variables if 'state_value' not in v.path]+[q_scale]
        optimizer=tf.keras.optimizers.AdamW(2e-4,weight_decay=1e-4,clipnorm=1.);optimizer.build(variables)
        checkpoint=tf.train.Checkpoint(model=model,optimizer=optimizer,q_scale=q_scale)
        manager=tf.train.CheckpointManager(checkpoint,str(a.out/'checkpoints'),max_to_keep=2)
        selected=tf.train.CheckpointManager(checkpoint,str(a.out/'selected-checkpoint'),max_to_keep=2)
        config=dict(dataset_sha256=sha(a.data/'dataset.json'),parent_sha256=sha(a.parent),epochs=a.epochs,
            objective='Family-weighted MSE of audited action-minus-reference IMPs; public inputs only',
            source_sha256=sha(__file__),representation='All auction/action hidden layers trainable; no ordinary outcome labels')
        if (a.out/'config.json').exists() and read(a.out/'config.json')!=config:raise ValueError('Fit configuration changed')
        atomic_json(a.out/'config.json',config)
        def predict(d,training=False):
            x={k:tf.cast(d[k],tf.int32 if k in ('calls','seats') else tf.float32) for k in ('state','actions','calls','seats')}
            values=model(x,training=training)['score'][...,0]+q_scale*tf.cast(d['q'],tf.float32)
            return tf.gather(values,tf.cast(d['chosen'],tf.int32),axis=1,batch_dims=1)-tf.gather(values,tf.cast(d['reference'],tf.int32),axis=1,batch_dims=1)
        @tf.function(reduce_retracing=True)
        def step(d):
            with tf.GradientTape() as tape:
                loss=tf.reduce_sum(d['weight']*tf.square(predict(d,True)-d['y']))/tf.reduce_sum(d['weight'])
            grads=tape.gradient(loss,variables);optimizer.apply_gradients([(g,v) for g,v in zip(grads,variables) if g is not None]);return loss
        @tf.function(reduce_retracing=True)
        def prediction(d):return predict(d)
        def evaluate():
            sums=np.zeros(3)
            for path in paths['validation']:
                d=load(path)
                for start in range(0,len(d['y']),512):
                    b={k:v[start:start+512] for k,v in d.items() if k!='group'};v=prediction(b).numpy();w=b['weight']
                    sums += [np.sum(w*(v-b['y'])**2),np.sum(w*b['y']**2),w.sum()]
            return dict(mse=float(sums[0]/sums[2]),zero_mse=float(sums[1]/sums[2]))
        def export(path):
            export_weights(model,path)
            with np.load(path,allow_pickle=False) as z:w={k:z[k] for k in z.files}
            np.savez_compressed(path,**w,imp_neural=np.int8(1),imp_q_scale=np.float32(q_scale.numpy()))
        if (a.out/'state.json').exists():
            state=read(a.out/'state.json');checkpoint.restore(state['checkpoint']).assert_existing_objects_matched()
        else:
            initial=evaluate();export(a.out/'best.npz')
            state=dict(epoch=0,best_epoch=0,best_mse=initial['mse'],initial=initial,complete=False,history=[],
                checkpoint=manager.save(checkpoint_number=0),selected_checkpoint=selected.save(checkpoint_number=0))
            atomic_json(a.out/'state.json',state)
        started=time.monotonic()
        while state['epoch']<a.epochs and time.monotonic()-started<a.seconds:
            epoch=state['epoch']+1;rng=np.random.default_rng(202611093+epoch)
            for pi in rng.permutation(len(paths['train'])):
                d=load(paths['train'][pi]);order=rng.permutation(len(d['y']))
                for i in range(0,len(order),512):step({k:v[order[i:i+512]] for k,v in d.items() if k!='group'})
            val=evaluate()
            if val['mse']<state['best_mse']:
                export(a.out/'best.npz');state.update(best_epoch=epoch,best_mse=val['mse'],selected_checkpoint=selected.save(checkpoint_number=epoch))
            state.update(epoch=epoch,complete=epoch==a.epochs,checkpoint=manager.save(checkpoint_number=epoch))
            state['history'].append(dict(epoch=epoch,validation=val));atomic_json(a.out/'state.json',state)
            print(json.dumps(state['history'][-1]),flush=True)
        if state['complete']:
            checkpoint.restore(state['selected_checkpoint']).assert_existing_objects_matched()
            check={k:v[:128] for k,v in first.items() if k!='group'}
            deployed=IMPSelector(a.out/'best.npz');values=deployed.predict(check)
            indices=np.arange(len(check['y']));contrasts=values[indices,check['chosen']]-values[indices,check['reference']]
            err=float(np.max(np.abs(contrasts-prediction(check).numpy())))
            if err>1e-4:raise ValueError('IMP export differs from training')
            eligible=state['best_epoch']>0 and state['best_mse']<state['initial']['mse']
            chosen=a.out/'best.npz' if eligible else a.parent
            atomic_json(a.out/'result.json',dict(complete=True,eligible=eligible,selected_weights=str(chosen.resolve()),
                selected_sha256=sha(chosen),best_epoch=state['best_epoch'],initial=state['initial'],selected_mse=state['best_mse'],
                numpy_max_error=err,parameters=model.count_params()+1,selected_checkpoint=state['selected_checkpoint'],
                playing_strength_evaluated=False,training='audited-IMP-contrasts-only'))


if __name__=='__main__':main()
