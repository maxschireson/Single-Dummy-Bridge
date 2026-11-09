"""Quick compact DD-value fit; independent families select the checkpoint."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['TF_ENABLE_ONEDNN_OPTS']='0';os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
import argparse,json,time,sys,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.dds_value import encode,build_model,export,Weights
from bridge_harness.selfplay import atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=6);p.add_argument('--batch',type=int,default=256);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    while not all((a.data/f).exists() for f in ['cache-manifest.json','fresh-manifest.json']):time.sleep(2)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2);tf.config.threading.set_inter_op_parallelism_threads(1);tf.keras.utils.set_random_seed(2026110913)
    with np.load(a.data/'train.npz') as z:raw=z['raw'];scores=z['scores']
    with np.load(a.data/'validation.npz') as z:vr=z['raw'];vs=z['scores']
    model=build_model();opt=tf.keras.optimizers.Adam(5e-4,clipnorm=1.);start=time.time()
    config=dict(parameters=model.count_params(),train_positions=len(raw),epochs=a.epochs,batch=a.batch,seed=2026110913,
        architecture='373 input; 512/256 ReLU; 52 x 14 trick logits',stage='10-13 remaining, equal sample per stage',
        augmentation='actor-relative seats and random suit permutation per batch',
        loss='legal-action CE + 0.2 MSE + 0.5 centered action MSE + 0.2 best-move probability loss',
        selection='validation nonforced mean selected-move regret, then NLL',
        train_sha256=hashlib.sha256((a.data/'train.npz').read_bytes()).hexdigest())
    atomic_json(a.out/'config.json',config)
    @tf.function(reduce_retracing=True)
    def step(x,y,remaining):
        mask=y>=0;target=tf.maximum(y,0);mf=tf.cast(mask,tf.float32);den=tf.maximum(tf.reduce_sum(mf,1),1.)
        with tf.GradientTape() as tape:
            logits=tf.where(tf.range(14)[None,None,:]<=remaining[:,None,None],model(x,training=True),-1e9)
            prob=tf.nn.softmax(logits);mean=tf.reduce_sum(prob*tf.cast(tf.range(14),tf.float32),-1)
            ce=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=target,logits=logits)
            diff=mean-tf.cast(target,tf.float32);center=diff-tf.reduce_sum(diff*mf,1,keepdims=True)/den[:,None]
            best=(y==tf.reduce_max(y,1,keepdims=True)) & mask
            rank=tf.reduce_logsumexp(tf.where(mask,mean/.25,-1e9),1)-tf.reduce_logsumexp(tf.where(best,mean/.25,-1e9),1)
            loss=tf.reduce_mean(tf.reduce_sum(mf*(ce+.2*diff**2+.5*center**2),1)/den+.2*rank)
        opt.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables));return loss
    def evaluate():
        vals=[]
        for i in range(0,len(vr),512):
            x,rem,_=encode(vr[i:i+512]);y=vs[i:i+512].astype(int)-1;mask=y>=0
            logits=model(x,training=False).numpy();logits=np.where(np.arange(14)[None,None,:]<=rem[:,None,None],logits,-1e9)
            pr=np.exp(logits-logits.max(-1,keepdims=True));pr/=pr.sum(-1,keepdims=True);mu=pr@np.arange(14)
            selected=np.argmax(np.where(mask,mu,-1e9),1);regret=y.max(1)-y[np.arange(len(y)),selected]
            ce=-np.log(np.maximum(np.take_along_axis(pr,np.maximum(y,0)[:,:,None],-1)[:,:,0],1e-12))
            vals.extend(zip(regret,(np.abs(mu-y)*mask).sum(1)/mask.sum(1),(ce*mask).sum(1)/mask.sum(1),mask.sum(1)>1))
        v=np.array(vals);ix=v[:,3]>0
        return dict(regret=float(v[ix,0].mean()),mae=float(v[:,1].mean()),nll=float(v[:,2].mean()),nonforced=int(ix.sum()))
    history=[];best=(float('inf'),float('inf'));best_epoch=0
    for epoch in range(1,a.epochs+1):
        rng=np.random.default_rng(2026110913+epoch);order=rng.permutation(len(raw));loss=[]
        for i in range(0,len(raw),a.batch):
            ix=order[i:i+a.batch];x,rem,cards=encode(raw[ix],rng.permutation(4));y=scores[ix][:,cards].astype(np.int32)-1
            loss.append(float(step(x,y,rem)))
        val=evaluate();metric=(val['regret'],val['nll'])
        if metric<best:best=metric;best_epoch=epoch;export(model,a.out/'best.npz')
        export(model,a.out/'last.npz');row=dict(epoch=epoch,loss=float(np.mean(loss)),validation=val,seconds=time.time()-start)
        history.append(row);atomic_json(a.out/'training.json',dict(config=config,best_epoch=best_epoch,history=history));print(json.dumps(row),flush=True)
    net=Weights(a.out/'best.npz');model.set_weights(net.w);x,_,_=encode(vr[:32]);error=float(np.max(np.abs(model(x).numpy()-net.logits(x))))
    assert error<1e-4
    atomic_json(a.out/'result.json',dict(config=config,best_epoch=best_epoch,history=history,export_max_error=error,seconds=time.time()-start))
if __name__=='__main__':main()
