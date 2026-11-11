"""One bounded warm-start, direct auctions/history, parent eligible at epochzero."""
import argparse,json,os
from pathlib import Path
import sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.auction_policy import build_model,restore_parent,export_weights,AuctionSelectorWeights
from bridge_harness.policy_selector import SelectorWeights
from bridge_harness.improvement import read,writer_lock
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--parent',type=Path,required=True);p.add_argument('--epochs',type=int,default=8)
    p.add_argument('--run-seconds',type=float,default=180);p.add_argument('--seed',type=int,default=2026110907)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(a.seed)
    tf.config.experimental.enable_op_determinism()
    with writer_lock(a.out):
        ds=read(a.data/'dataset.json');assert ds['validated']
        paths={s:[a.data/e['file'] for e in ds['shards'] if e['split']==s] for s in ('train','validation')}
        for e in ds['shards']:assert sha(a.data/e['file'])==e['sha256']
        def load(path):
            with np.load(path,allow_pickle=False) as z:return {k:z[k] for k in z.files}
        first=load(paths['validation'][0]);model=build_model(first['state'].shape[-1],first['actions'].shape[-1])
        restore_parent(model,a.parent)
        optimizer=tf.keras.optimizers.AdamW(learning_rate=2e-4,weight_decay=1e-4,clipnorm=1.)
        optimizer.build(model.trainable_variables)
        ckpt=tf.train.Checkpoint(model=model,optimizer=optimizer)
        manager=tf.train.CheckpointManager(ckpt,str(a.out/'checkpoints'),max_to_keep=2)
        config=dict(dataset_sha256=sha(a.data/'dataset.json'),parent_sha256=sha(a.parent),epochs=a.epochs,seed=a.seed,
            selection='lowest weighted chosen-return validation MSE; epoch0eligible',
            objective='LAST predictive warm-start. Next policy objective uses audited fork IMP differences only.',
            inputs='direct auction tokens with relative seats; public ordered play; visible cards; PIMC estimates',
            source_sha256={s:sha(ROOT/s) for s in ['bridge_harness/auction_policy.py','scripts/train_policy_bootstrap.py']})
        if (a.out/'config.json').exists():assert read(a.out/'config.json')==config
        else:atomic_json(a.out/'config.json',config)
        def inputs(d):return {k:tf.cast(d[k],tf.int32 if k in ('calls','seats') else tf.float32) for k in ('state','actions','calls','seats')}
        def outputs(d,training=False):
            raw=model(inputs(d),training=training);mask=tf.cast(d['mask'],tf.float32)
            scores=raw['score'][...,0];scores-=tf.reduce_sum(scores*mask,axis=1,keepdims=True)/tf.reduce_sum(mask,axis=1,keepdims=True)
            state=tf.cast(d['q'],tf.float32)+raw['value']
            return state+scores,state
        @tf.function(reduce_retracing=True)
        def step(d):
            with tf.GradientTape() as tape:
                pred,_=outputs(d,True);v=tf.gather(pred,tf.cast(d['chosen'],tf.int32),axis=1,batch_dims=1)
                w=tf.cast(d['weight'],tf.float32);loss=tf.reduce_sum(w*tf.square(v-d['y']))/tf.reduce_sum(w)
            optimizer.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables));return loss
        @tf.function(reduce_retracing=True)
        def predict(d):return outputs(d)
        old=SelectorWeights(a.parent);old_size=len(old.weights['state_hidden_kernel'])
        def evaluate(details=False):
            sums=np.zeros(5);groups={};changed=total=0
            for path in paths['validation']:
                d=load(path)
                for start in range(0,len(d['y']),512):
                    b={k:v[start:start+512] for k,v in d.items()};ix=np.arange(len(b['y']));chosen=b['chosen'];w=b['weight']
                    pred,state=[v.numpy() for v in predict({k:v for k,v in b.items() if k in ['state','actions','calls','seats','mask','q']})]
                    previous=old.predict(dict(b,state=b['state'][:,:old_size]))
                    losses=np.stack([(pred[ix,chosen]-b['y'])**2,(state[ix,chosen]-b['y'])**2,(previous[ix,chosen]-b['y'])**2],1)
                    sums[:3]+=(losses*w[:,None]).sum(0);sums[3]+=w.sum();sums[4]+=len(w)
                    newbest=np.where(b['mask']>0,pred,-np.inf).argmax(1);oldbest=np.where(b['mask']>0,previous,-np.inf).argmax(1)
                    changed+=int((newbest!=oldbest).sum());total+=len(w)
                    if details:
                        for g,loss,weight in zip(b['group'],losses,w):
                            acc=groups.setdefault(str(g),np.zeros(4));acc[:3]+=loss*weight;acc[3]+=weight
            result=dict(mse=float(sums[0]/sums[3]),state_only_mse=float(sums[1]/sums[3]),old_mse=float(sums[2]/sums[3]),
                rows=int(sums[4]),argmax_changed_fraction=changed/total)
            if details:
                values=np.array([v[:3]/v[3] for v in groups.values()]);delta=values[:,0]-values[:,2]
                half=1.96*delta.std(ddof=1)/np.sqrt(len(delta))
                result.update(deal_families=len(delta),family_mean_mse_change=float(delta.mean()),
                    descriptive95=[float(delta.mean()-half),float(delta.mean()+half)])
                atomic_json(a.out/'validation-by-family.json',{k:(v[:3]/v[3]).tolist() for k,v in groups.items()})
            return result
        if (a.out/'state.json').exists():
            state=read(a.out/'state.json');ckpt.restore(state['checkpoint']).assert_existing_objects_matched()
        else:
            initial=evaluate();export_weights(model,a.out/'best.npz')
            state=dict(epoch=0,best_epoch=0,best_mse=initial['mse'],initial=initial,history=[],active_seconds=0.,complete=False)
            state['checkpoint']=manager.save(checkpoint_number=0);atomic_json(a.out/'state.json',state)
            # Added inputs initially preserve every old action value.
            check={k:v[:32] for k,v in first.items()}
            err=np.max(np.abs(AuctionSelectorWeights(a.out/'best.npz').predict(check)-old.predict(dict(check,state=check['state'][:,:old_size]))))
            assert err<1e-5,err
            print(json.dumps(dict(event='initial',parameters=model.count_params(),function_preservation_error=float(err),**initial)),flush=True)
        started=time.monotonic();stale=state.get('stale',0)
        while state['epoch']<a.epochs and not state['complete'] and time.monotonic()-started<a.run_seconds:
            begin=time.monotonic();epoch=state['epoch']+1;rng=np.random.default_rng(a.seed+epoch)
            for pi in rng.permutation(len(paths['train'])):
                d=load(paths['train'][pi]);order=rng.permutation(len(d['y']))
                for start in range(0,len(order),512):
                    ix=order[start:start+512]
                    b={k:d[k][ix] for k in ['state','actions','calls','seats','mask','q','chosen','y','weight']};step(b)
            val=evaluate();seconds=time.monotonic()-begin
            if val['mse']<state['best_mse']-1e-5:
                state.update(best_mse=val['mse'],best_epoch=epoch);export_weights(model,a.out/'best.npz');stale=0
            else:stale+=1
            state.update(epoch=epoch,stale=stale,complete=epoch==a.epochs or stale>=2,active_seconds=state['active_seconds']+seconds)
            state['history'].append(dict(epoch=epoch,seconds=seconds,validation=val))
            state['checkpoint']=manager.save(checkpoint_number=epoch);atomic_json(a.out/'state.json',state)
            print(json.dumps(state['history'][-1]),flush=True)
        if state['complete']:
            restore_parent(model,a.out/'best.npz');selected=evaluate(True)
            check={k:v[:128] for k,v in first.items()}
            error=float(np.max(np.abs(AuctionSelectorWeights(a.out/'best.npz').predict(check)-outputs(check)[0].numpy())))
            assert error<1e-5,error
            result=dict(complete=True,parameters=model.count_params(),best_epoch=state['best_epoch'],epochs=state['epoch'],
                initial=state['initial'],validation=selected,active_seconds=state['active_seconds'],numpy_max_error=error,
                selected_weights=str((a.out/'best.npz').resolve()),selected_sha256=sha(a.out/'best.npz'),
                playing_strength_evaluated=False,promoted=False,stage='predictive-bootstrap-complete; switch to random-fork comparisons')
            atomic_json(a.out/'result.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
