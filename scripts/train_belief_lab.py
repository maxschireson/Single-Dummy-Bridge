"""Chunk-resumable training with matched data and public-only constraint losses."""
import argparse, fcntl, json, math, os, sys, time
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.belief_capacity import INPUTS, sha
from bridge_harness.belief_lab import initialize, Weights
from bridge_harness.residual_attention_belief import dropout_generator, export
from bridge_harness.selfplay import atomic_json
from scripts.residual_belief_common import prepare,evaluate,read

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,required=True);ap.add_argument('--chunk-steps',type=int,default=1000)
    a=ap.parse_args();cfg=json.loads(a.config.read_text());out=a.config.parent
    lock=(out/'writer.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (out/'result.json').exists():return
    data=Path(cfg['data'])
    if json.loads((data/'dataset.json').read_text()).get('evaluation_only'):raise ValueError('Reserved evaluation data cannot be trained')
    train,val,coeff,counts=prepare(data,cfg.get('smoke_shards',0))
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(cfg.get('threads',4));tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(cfg['seed']);tf.config.experimental.enable_op_determinism()
    model=initialize(cfg,out);rng=dropout_generator(model);bs=cfg['batch_size']
    opt=tf.keras.optimizers.AdamW(cfg['lr'],weight_decay=cfg.get('weight_decay',1e-4),clipnorm=1.)
    opt.build(model.trainable_variables);ckpt=tf.train.Checkpoint(model=model,optimizer=opt)
    manager=tf.train.CheckpointManager(ckpt,str(out/'checkpoints'),max_to_keep=2)
    @tf.function(reduce_retracing=True)
    def step(x,y,mask,support,cw,fw):
        with tf.GradientTape() as tape:
            logits=model(x,training=True);z=tf.where(support,logits,tf.constant(-1e9))
            p=tf.nn.softmax(z,-1)*tf.cast(support,tf.float32)
            ce=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,logits=z)
            if cfg.get('brier',0):
                true=tf.reduce_sum(p*tf.one_hot(y,4),-1);ce+=cfg['brier']*(tf.reduce_sum(p*p,-1)-2*true+1)
            weights=cw if cfg.get('consequence',True) else tf.ones_like(cw)
            per=tf.reduce_sum(ce*mask*weights,1)
            if cfg.get('swap_weight',0):
                true=tf.reduce_sum(logits*tf.one_hot(y,4),-1)
                other=tf.einsum('bcs,bds->bcd',logits,tf.one_hot(y,4))
                allowed=tf.einsum('bcs,bds->bcd',tf.cast(support,tf.float32),tf.one_hot(y,4))>0
                valid=(mask[:,:,None]>0)&(mask[:,None,:]>0)&(y[:,:,None]!=y[:,None,:])&allowed&tf.transpose(allowed,[0,2,1])
                margin=other+tf.transpose(other,[0,2,1])-true[:,:,None]-true[:,None,:]
                pair=tf.reduce_sum(tf.nn.softplus(margin)*tf.cast(valid,tf.float32),[1,2])/tf.maximum(tf.reduce_sum(tf.cast(valid,tf.float32),[1,2]),1.)*tf.reduce_sum(mask*weights,1)
                per=(1-cfg['swap_weight'])*per+cfg['swap_weight']*pair
            if cfg.get('count_loss',0):
                uncertain=tf.cast(mask[:,:,None],tf.float32)
                pred=tf.reduce_sum(p*uncertain,1)
                remaining=tf.where(x['play'][:,-1,None]>0,x['play'][:,484:488]*13,tf.ones_like(pred)*13)
                forced=tf.reduce_sum(tf.cast(support,tf.float32)*tf.cast(tf.reduce_sum(tf.cast(support,tf.int32),-1)==1,tf.float32)[:,:,None],1)
                cap=tf.maximum(remaining-forced,0.)
                per+=cfg['count_loss']*tf.reduce_sum(tf.square(pred-cap),-1)
            loss=tf.reduce_sum(per*fw)/float(bs)
        gradients=tape.gradient(loss,model.trainable_variables)
        opt.apply_gradients(zip(gradients,model.trainable_variables));return loss
    @tf.function(reduce_retracing=True)
    def predict(x):return model(x,training=False)
    statepath=out/'state.json'
    if statepath.exists():
        state=json.loads(statepath.read_text())
        if state['config_sha256']!=sha(a.config):raise ValueError('Frozen configuration changed')
        ckpt.restore(state['checkpoint']).assert_existing_objects_matched();rng.state.assign(state['dropout_state'])
    else:
        baseline=evaluate(lambda x:predict(x).numpy(),val,out,'epoch-0',bs)
        export(model,out/'best.npz',cfg['mode'])
        state=dict(config_sha256=sha(a.config),completed_epochs=0,offset=0,history=[],best_epoch=0,best_score=baseline['score'],baseline=baseline,seconds=0.,loss_sum=0.,positions=0,created=time.time(),counts=counts)
    def save():
        state['checkpoint']=manager.save(checkpoint_number=int(opt.iterations.numpy()))
        state['dropout_state']=rng.state.numpy().tolist();state['optimizer_steps']=int(opt.iterations.numpy())
        atomic_json(statepath,state)
    def status(stage):
        atomic_json(out/'status.json',dict(stage=stage,completed_epochs=state['completed_epochs'],epoch=state['completed_epochs']+1,offset=state['offset'],best_epoch=state['best_epoch'],best_score=state['best_score'],updated=time.time()))
    save();used=0
    while state['completed_epochs']<cfg['epochs']:
        epoch=state['completed_epochs']+1
        if state['offset']==0:rng.state.assign([cfg['seed']+epoch,0])
        # Cosine decay has the same epoch schedule for paired recipe controls.
        lr=cfg['lr']*(.1+.9*.5*(1+math.cos(math.pi*(epoch-1)/cfg['epochs']))) if cfg.get('cosine',True) else cfg['lr']
        opt.learning_rate.assign(lr);cursor=0
        for j in np.random.default_rng(cfg['seed']+epoch).permutation(len(train)):
            e=train[int(j)];batches=math.ceil(e['rows']/bs)
            if cursor+batches<=state['offset']:cursor+=batches;continue
            d=read(e);order=np.random.default_rng([cfg['seed'],epoch,int(j),1]).permutation(len(d['kind']))
            for lo in range(0,len(order),bs):
                cursor+=1
                if cursor<=state['offset']:continue
                ix=order[lo:lo+bs];x={k:d[k][ix] for k in INPUTS};fw=np.array([coeff[e['source'],str(g)] for g in d['split_group'][ix]],np.float32)
                t=time.perf_counter();loss=float(step(x,d['owner_target'][ix].astype(np.int32),d['owner_loss_mask'][ix].astype(np.float32),d['support'][ix],d['card_weight'][ix],fw))
                if not np.isfinite(loss):raise ValueError('Nonfinite loss')
                state['seconds']+=time.perf_counter()-t;state['loss_sum']+=loss*bs;state['positions']+=len(ix);state['offset']=cursor;used+=1
                if cursor%100==0:status('training')
                if cursor%250==0 or used>=a.chunk_steps:save()
                if used>=a.chunk_steps:status('checkpointed');return
        save();status('validating');t=time.perf_counter()
        m=evaluate(lambda x:predict(x).numpy(),val,out,f'epoch-{epoch}',bs)
        row=dict(epoch=epoch,seconds=state['seconds']+time.perf_counter()-t,training_loss=state['loss_sum']/state['positions'],metrics=m,lr=lr)
        state['history'].append(row)
        export(model,out/f'epoch-{epoch}.npz',cfg['mode'])
        if m['score']<state['best_score']:
            state.update(best_epoch=epoch,best_score=m['score']);export(model,out/'best.npz',cfg['mode'])
        state.update(completed_epochs=epoch,offset=0,seconds=0.,loss_sum=0.,positions=0.);save();atomic_json(out/f'epoch-{epoch}.json',row);status('epoch_complete')
        print(json.dumps(dict(arm=out.name,epoch=epoch,score=m['score'],best=state['best_epoch'],seconds=row['seconds'])),flush=True)
        if epoch<cfg['epochs']:return
    export(model,out/'last.npz',cfg['mode']);portable=Weights(out/'last.npz');errors=[]
    for e in [val[0],val[-1]]:
        d=read(e);x={k:d[k][:16] for k in INPUTS};errors.append(float(np.max(np.abs(portable.predict(x)-predict(x).numpy()))))
    if max(errors)>2e-5:raise ValueError('Export mismatch')
    atomic_json(out/'recipe.json',dict(model='best.npz',temperature=1.,projection=False))
    atomic_json(out/'result.json',dict(config=cfg,config_sha256=sha(a.config),counts=counts,parameters=model.count_params(),best_epoch=state['best_epoch'],best_score=state['best_score'],baseline=state['baseline'],history=state['history'],best_sha256=sha(out/'best.npz'),export_error=max(errors),wall_seconds=time.time()-state['created'],test_evaluated=False,promoted=False))
    status('complete')

if __name__=='__main__':main()
