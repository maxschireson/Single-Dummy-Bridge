"""Joint public-information belief and distributional action-value training."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
os.environ['TF_ENABLE_ONEDNN_OPTS']='0';os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
import argparse,json,sys,time,hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.belief_plus import build_model,export,restore,Weights,INPUTS
from bridge_harness.selfplay import atomic_json

def load(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--parent',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=8);p.add_argument('--batch',type=int,default=128);p.add_argument('--teacher-weight',type=float,default=.5)
    p.add_argument('--resume',action='store_true')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=a.resume)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(2026110947)
    ds=json.loads((a.data/'dataset.json').read_text());paths={s:[a.data/e['file'] for e in ds['shards'] if e['split']==s] for s in ('train','validation','test')}
    for e in ds['shards']:
        if hashlib.sha256((a.data/e['file']).read_bytes()).hexdigest()!=e['sha256']:raise ValueError('Data changed')
    model=build_model(a.parent);opt=tf.keras.optimizers.Adam(3e-4,clipnorm=1.)
    opt.build(model.trainable_variables)
    config=dict(parameters=model.count_params(),widths=[768,384],epochs=a.epochs,batch=a.batch,parent=str(a.parent),teacher_weight=a.teacher_weight,
        loss='actual trick CE + 0.2 outcome mean MSE + 0.3 ownership CE + teacher_weight centered PIMC action-value MSE',
        warmup='one epoch trains action heads only; later epochs jointly train encoder and both heads',selection='minimum validation-family early outcome cross entropy',
        inputs='visible observation only; NO DDS/PIMC values, proposal masks, true hidden cards, future actions or deal identifiers',
        targets='actual continuation trick outcomes, true unseen owners, and logged PIMC differences for legal alternatives',dataset_sha256=hashlib.sha256((a.data/'dataset.json').read_bytes()).hexdigest())
    old=json.loads((a.out/'training.json').read_text()) if a.resume else None
    if old:
        if old['config']['dataset_sha256']!=config['dataset_sha256']:raise ValueError('Resume data changed')
        restore(model,a.out/'last.npz')
        config['resume']=dict(after_epoch=old['history'][-1]['epoch'],batch_before=old['config']['batch'],optimizer_reset=True,reason='Process SIGKILL; resume completed epoch checkpoint with reduced batch')
    atomic_json(a.out/'config.json',config)
    action_vars=[v for v in model.trainable_variables if any(n in v.path for n in ('action0','action1','tricks'))]
    def losses(d,training=False):
        out=model({k:d[k] for k in INPUTS},training=training)
        logits=tf.where(tf.range(14)[None,None,:]<=tf.cast(d['remaining'][:,None,None],tf.int32),out['tricks'],-1e9)
        prob=tf.nn.softmax(logits);mean=tf.reduce_sum(prob*tf.cast(tf.range(14),tf.float32),-1)
        chosen=tf.cast(d['chosen'],tf.int32);selected=tf.gather(logits,chosen,axis=1,batch_dims=1)
        ce=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=tf.cast(d['y'],tf.int32),logits=selected)
        error=tf.square(tf.gather(mean,chosen,axis=1,batch_dims=1)-tf.cast(d['y'],tf.float32))
        ol=tf.where(d['support'],out['ownership'],-1e9)
        oc=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=tf.cast(d['owner'],tf.int32),logits=ol)
        om=tf.cast(d['owner_mask'],tf.float32);bc=tf.reduce_sum(oc*om,1)/tf.maximum(tf.reduce_sum(om,1),1.)
        qm=tf.cast(d['q_mask'],tf.float32);den=tf.maximum(tf.reduce_sum(qm,1,keepdims=True),1.)
        diff=mean-tf.cast(d['q'],tf.float32);center=diff-tf.reduce_sum(diff*qm,1,keepdims=True)/den
        teacher=tf.reduce_sum(tf.square(center)*qm,1)/den[:,0]
        correct=tf.reduce_sum(tf.cast(tf.argmax(ol,-1,output_type=tf.int32)==tf.cast(d['owner'],tf.int32),tf.float32)*om,1)/tf.maximum(tf.reduce_sum(om,1),1.)
        best=tf.argmax(tf.where(d['cards']>=0,mean,-1e9),1,output_type=tf.int32)
        tq=tf.where(d['q_mask'],tf.cast(d['q'],tf.float32),-1e9)
        regret=tf.reduce_max(tq,1)-tf.gather(tq,best,axis=1,batch_dims=1)
        regret=tf.where(tf.reduce_all(d['q_mask'] | (d['cards']<0),1),regret,0.)
        return ce,error,bc,teacher,correct,regret,prob
    @tf.function(reduce_retracing=True)
    def step(d,warm):
        with tf.GradientTape() as tape:
            ce,err,bc,teach,_,_,_=losses(d,True)
            weight=tf.cast(d['weight'],tf.float32)
            loss=tf.reduce_sum(weight*(ce+.2*err+.3*bc+a.teacher_weight*teach))/tf.reduce_sum(weight)
        variables=action_vars if warm else model.trainable_variables
        opt.apply_gradients(zip(tape.gradient(loss,variables),variables));return loss
    @tf.function(reduce_retracing=True)
    def predict(d):return losses(d)
    def batches(d,order=None):
        order=np.arange(len(d['y'])) if order is None else order
        for i in range(0,len(order),a.batch):yield {k:v[order[i:i+a.batch]] for k,v in d.items() if k!='group'}
    def evaluate(split):
        sums=defaultdict(lambda:np.zeros(8));stages=defaultdict(lambda:np.zeros(8))
        for path in paths[split]:
            d=load(path)
            for start,b in zip(range(0,len(d['y']),a.batch),batches(d)):
                v=predict(b);mat=np.stack([z.numpy() for z in v[:6]],1);groups=d['group'][start:start+len(mat)];early=b['ply']<28
                for g in np.unique(groups):
                    ix=groups==g;sums[str(g)][:6]+=mat[ix].sum(0);sums[str(g)][6]+=ix.sum();sums[str(g)][7]+=mat[ix&early,0].sum()
                for name,mask in [('early',early),('late',~early),('all',np.ones(len(mat),bool))]:
                    w=b['weight'][mask];stages[name][:6]+=(mat[mask]*w[:,None]).sum(0);stages[name][6]+=w.sum();stages[name][7]+=mask.sum()
        names=['outcome_nll','outcome_mse','belief_nll','teacher_center_mse','belief_accuracy','pimc_regret']
        return {k:dict(zip(names,(v[:6]/max(v[6],1e-9)).tolist()),rows=int(v[7])) for k,v in stages.items()}
    history=old['history'] if old else [];best=min(e['validation']['early']['outcome_nll'] for e in history) if history else float('inf');best_epoch=old['best_epoch'] if old else 0;start=time.time()
    for epoch in range(len(history)+1,a.epochs+1):
        rng=np.random.default_rng(2026110947+epoch);losses_epoch=[]
        for pi,ix in enumerate(rng.permutation(len(paths['train']))):
            d=load(paths['train'][ix]);order=rng.permutation(len(d['y']))
            for b in batches(d,order):losses_epoch.append(float(step(b,epoch==1)))
            if (pi+1)%10==0:print(json.dumps(dict(event='progress',epoch=epoch,shards=pi+1,total=len(paths['train']),seconds=time.time()-start)),flush=True)
        val=evaluate('validation');metric=val['early']['outcome_nll']
        if metric<best:best=metric;best_epoch=epoch;export(model,a.out/'best.npz')
        export(model,a.out/'last.npz');entry=dict(epoch=epoch,loss=float(np.mean(losses_epoch)),validation=val,seconds=time.time()-start)
        history.append(entry);atomic_json(a.out/'training.json',dict(config=config,best_epoch=best_epoch,history=history));print(json.dumps(entry),flush=True)
    restore(model,a.out/'best.npz');test=evaluate('test')
    check=next(batches(load(paths['validation'][0])));n=Weights(a.out/'best.npz').forward(check);t=model({k:check[k] for k in INPUTS},training=False)
    err=max(float(np.max(np.abs(n[k]-t[k].numpy()))) for k in n)
    if err>1e-4:raise ValueError('NumPy export mismatch')
    result=dict(config=config,best_epoch=best_epoch,validation=history[best_epoch-1]['validation'],test=test,export_max_error=err,seconds=time.time()-start,promoted=False)
    atomic_json(a.out/'result.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
