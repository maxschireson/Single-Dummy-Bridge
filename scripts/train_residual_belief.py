"""Bounded, exactly resumable chunks for dense versus residual-attention belief."""
import argparse,fcntl,json,math,os,sys,time
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.belief_capacity import INPUTS,Weights as DenseWeights,sha
from bridge_harness.residual_attention_belief import build,dropout_generator,export,Weights
from bridge_harness.selfplay import atomic_json
from scripts.residual_belief_common import prepare,evaluate,read

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--parent',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['dense','attention'],required=True)
    p.add_argument('--epochs',type=int,default=3);p.add_argument('--smoke-shards',type=int,default=0)
    p.add_argument('--chunk-steps',type=int,default=2000);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    lock=(a.out/'writer.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (a.out/'result.json').exists():return
    seed=2026111011;batch_size=128;started=time.time()
    train,val,coeff,counts=prepare(a.data,a.smoke_shards)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(seed);tf.config.experimental.enable_op_determinism()
    model=build(a.parent,a.mode);rng=dropout_generator(model)
    opt=tf.keras.optimizers.AdamW(1e-4,weight_decay=1e-4,clipnorm=1.);opt.build(model.trainable_variables)
    checkpoint=tf.train.Checkpoint(model=model,optimizer=opt)
    manager=tf.train.CheckpointManager(checkpoint,str(a.out/'checkpoints'),max_to_keep=2)
    selected=tf.train.CheckpointManager(checkpoint,str(a.out/'selected-checkpoint'),max_to_keep=2)
    cfg=dict(mode=a.mode,epochs=a.epochs,seed=seed,batch_size=batch_size,learning_rate=1e-4,weight_decay=1e-4,clipnorm=1.,
        parent_sha256=sha(a.parent),dataset_sha256=sha(a.data/'dataset.json'),parameters=model.count_params(),
        training='Identical family/domain/consequence weights, all layers trainable, fresh AdamW and batch 128 in both arms',
        selection='Frozen composite NLL; epoch zero eligible; fixed epoch 3 primary paired architecture comparison',
        dropout='Same explicit epoch seed; exact generator state saved at every chunk checkpoint',
        code_sha256={n:sha(n) for n in ['scripts/train_residual_belief.py','scripts/residual_belief_common.py','bridge_harness/residual_attention_belief.py']},
        smoke_shards=a.smoke_shards,**counts)
    cp=a.out/'config.json'
    if cp.exists() and json.loads(cp.read_text())!=cfg:raise ValueError('Frozen config changed')
    atomic_json(cp,cfg)
    @tf.function(reduce_retracing=True)
    def step(x,y,mask,support,cw,fw):
        with tf.GradientTape() as tape:
            z=tf.where(support,model(x,training=True),tf.constant(-1e9))
            ce=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,logits=z)
            loss=tf.reduce_sum(tf.reduce_sum(ce*mask*cw,1)*fw)/batch_size
        opt.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables));return loss
    @tf.function(reduce_retracing=True)
    def predict(x):return model(x,training=False)
    state_path=a.out/'state.json'
    if state_path.exists():
        state=json.loads(state_path.read_text());checkpoint.restore(state['checkpoint']).assert_existing_objects_matched()
        rng.state.assign(state['dropout_state'])
    else:
        errors={}
        for e in (val[0],val[-1]):
            d=read(e);x={k:d[k][:32] for k in INPUTS}
            errors[e['cohort']+'/'+e['source']]=float(np.max(np.abs(predict(x).numpy()-DenseWeights(a.parent).predict(x))))
        if max(errors.values())>1e-5:raise ValueError('Starting predictions changed')
        baseline=evaluate(lambda x:predict(x).numpy(),val,a.out,'epoch-0',batch_size)
        state=dict(completed_epochs=0,offset=0,loss_sum=0.,positions=0,epoch_seconds=0.,history=[],baseline=baseline,
            best_epoch=0,best_score=baseline['score'],selected_checkpoint=selected.save(checkpoint_number=0),
            initial_max_abs_error=errors,created_epoch=time.time())
    def save():
        state['checkpoint']=manager.save(checkpoint_number=int(opt.iterations.numpy()))
        state['dropout_state']=rng.state.numpy().tolist();state['optimizer_steps']=int(opt.iterations.numpy())
        atomic_json(state_path,state)
    def status(stage):
        atomic_json(a.out/'status.json',dict(stage=stage,completed_epochs=state['completed_epochs'],epoch=state['completed_epochs']+1,
            offset=state['offset'],best_epoch=state['best_epoch'],updated=time.time(),optimizer_steps=int(opt.iterations.numpy())))
    save();used=0;last_save=time.time()
    while state['completed_epochs']<a.epochs:
        epoch=state['completed_epochs']+1
        if state['offset']==0:rng.state.assign([seed+epoch,0])
        cursor=0
        for j in np.random.default_rng(seed+epoch).permutation(len(train)):
            entry=train[int(j)];batches=math.ceil(entry['rows']/batch_size)
            if cursor+batches<=state['offset']:cursor+=batches;continue
            d=read(entry);order=np.random.default_rng([seed,epoch,int(j),1]).permutation(len(d['kind']))
            for lo in range(0,len(order),batch_size):
                cursor+=1
                if cursor<=state['offset']:continue
                ix=order[lo:lo+batch_size];x={k:d[k][ix] for k in INPUTS}
                fw=np.array([coeff[entry['source'],str(g)] for g in d['split_group'][ix]],np.float32)
                t=time.perf_counter();loss=float(step(x,d['owner_target'][ix].astype(np.int32),d['owner_loss_mask'][ix].astype(np.float32),
                    d['support'][ix],d['card_weight'][ix],fw));state['epoch_seconds']+=time.perf_counter()-t
                if not np.isfinite(loss):raise ValueError('Nonfinite loss')
                state['loss_sum']+=loss*batch_size;state['positions']+=len(ix);state['offset']=cursor;used+=1
                if cursor%100==0:status('training')
                if cursor%250==0 or used>=a.chunk_steps:
                    save();last_save=time.time()
                if used>=a.chunk_steps:
                    status('checkpointed');print(json.dumps(dict(stage='chunk_saved',mode=a.mode,epoch=epoch,offset=cursor)),flush=True);return
        save();status('validating');t=time.perf_counter()
        metrics=evaluate(lambda x:predict(x).numpy(),val,a.out,f'epoch-{epoch}',batch_size)
        seconds=state['epoch_seconds']+time.perf_counter()-t
        row=dict(epoch=epoch,seconds=seconds,training_loss=state['loss_sum']/state['positions'],metrics=metrics)
        state['history'].append(row)
        if metrics['score']<state['best_score']:
            state.update(best_epoch=epoch,best_score=metrics['score'],selected_checkpoint=selected.save(checkpoint_number=int(opt.iterations.numpy())))
        state.update(completed_epochs=epoch,offset=0,positions=0,loss_sum=0.,epoch_seconds=0.)
        save();atomic_json(a.out/f'epoch-{epoch}.json',row);status('epoch_complete')
        print(json.dumps(dict(stage='epoch_complete',mode=a.mode,epoch=epoch,score=metrics['score'],best_epoch=state['best_epoch'],seconds=seconds)),flush=True)
        # Bound process lifetime even if the last training chunk was short.
        if epoch<a.epochs:return
    export(model,a.out/'last.npz',a.mode)
    checkpoint.restore(state['selected_checkpoint']).assert_existing_objects_matched()
    export(model,a.out/'best.npz',a.mode);portable=Weights(a.out/'best.npz');errors={}
    for e in val:
        name=e['cohort']+'/'+e['source']
        if name in errors:continue
        d=read(e);x={k:d[k][:32] for k in INPUTS}
        errors[name]=float(np.max(np.abs(portable.predict(x)-predict(x).numpy())))
    if max(errors.values())>1e-5:raise ValueError('Portable export mismatch')
    chosen=state['baseline'] if state['best_epoch']==0 else state['history'][state['best_epoch']-1]['metrics']
    result=dict(mode=a.mode,parameters=model.count_params(),epochs=a.epochs,best_epoch=state['best_epoch'],initial=state['baseline'],
        selected=chosen,history=state['history'],selected_sha256=sha(a.out/'best.npz'),config_sha256=sha(cp),export_max_abs_error=errors,
        selected_optimizer_steps=int(opt.iterations.numpy()),wall_seconds=time.time()-state['created_epoch'],
        dataset_sha256=cfg['dataset_sha256'],parent_sha256=cfg['parent_sha256'],promoted=False,reserved_test_evaluated=False)
    atomic_json(a.out/'result.json',result);status('complete')

if __name__=='__main__':main()
