"""Disposable training-step timing; no candidate selection or test evaluation."""
import argparse,json,math,os,sys,time
from pathlib import Path
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.belief_capacity import INPUTS,Weights,sha
from bridge_harness.residual_attention_belief import make_model
from scripts.train_belief_factorial import read
from bridge_harness.selfplay import atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--parent',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--batch-size',type=int,default=128)
    p.add_argument('--steps',type=int,default=100);p.add_argument('--threads',type=int,default=2);a=p.parse_args()
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(a.threads);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(2026111009);tf.config.experimental.enable_op_determinism()
    ds=json.loads((a.data/'dataset.json').read_text());samples={}
    for e in ds['shards']:
        domain=e['cohort']+'/'+e['source']
        if e['split']=='train' and domain not in samples:samples[domain]=read(e)
    m=make_model(a.parent);base=Weights(a.parent)
    errors={}
    for name,d in samples.items():
        x={k:d[k][:min(128,len(d['kind']))] for k in INPUTS}
        errors[name]=float(np.max(np.abs(m(x,training=False).numpy()-base.predict(x))))
    if max(errors.values())>1e-5:raise ValueError('Zero correction changed parent')
    opt=tf.keras.optimizers.AdamW(1e-4,weight_decay=1e-4,clipnorm=1.)
    @tf.function(reduce_retracing=True)
    def train(x,y,mask,support,cw):
        with tf.GradientTape() as tape:
            z=tf.where(support,m(x,training=True),tf.constant(-1e9))
            ce=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,logits=z)
            loss=tf.reduce_mean(tf.reduce_sum(ce*mask*cw,axis=1)/tf.maximum(tf.reduce_sum(mask*cw,axis=1),1.))
        grads=tape.gradient(loss,m.trainable_variables)
        opt.apply_gradients(zip(grads,m.trainable_variables));return loss
    @tf.function(reduce_retracing=True)
    def predict(x):return m(x,training=False)
    batches=[]
    for d in samples.values():
        ix=np.arange(a.batch_size)%len(d['kind'])
        batches.append(({k:tf.convert_to_tensor(d[k][ix]) for k in INPUTS},tf.convert_to_tensor(d['owner_target'][ix],tf.int32),
            tf.convert_to_tensor(d['owner_loss_mask'][ix],tf.float32),tf.convert_to_tensor(d['support'][ix],tf.bool),
            tf.convert_to_tensor(d['card_weight'][ix],tf.float32)))
    for i in range(8):train(*batches[i%len(batches)]).numpy()
    times=[]
    for i in range(a.steps):
        t=time.perf_counter();loss=float(train(*batches[i%len(batches)]).numpy());times.append(time.perf_counter()-t)
        if (i+1)%25==0:print(json.dumps(dict(steps=i+1,mean_ms=1000*np.mean(times))),flush=True)
    for b in batches:predict(b[0]).numpy()
    pred=[]
    for i in range(40):
        t=time.perf_counter();predict(batches[i%len(batches)][0]).numpy();pred.append(time.perf_counter()-t)
    steps={s:sum(math.ceil(e['rows']/a.batch_size) for e in ds['shards'] if e['split']==s) for s in ('train','validation')}
    epoch=steps['train']*float(np.mean(times))+steps['validation']*float(np.mean(pred))
    if not np.isfinite(loss):raise ValueError('Nonfinite benchmark fit')
    if not np.any(m.get_layer('att_readout').get_weights()[0]):raise ValueError('Correction did not learn')
    result=dict(purpose='Timing only; benchmark updates discarded',parameters=m.count_params(),added_parameters=m.count_params()-308726,
        architecture=dict(width=64,heads=2,blocks=1,queries=52,memory_tokens=117),batch_size=a.batch_size,threads=a.threads,
        warmup_steps=8,measured_steps=a.steps,training_ms_mean=float(np.mean(times)*1000),training_ms_median=float(np.median(times)*1000),
        prediction_ms_mean=float(np.mean(pred)*1000),steps_per_epoch=steps,estimated_epoch_compute_seconds=epoch,
        estimated_three_epoch_compute_seconds=3*epoch,initial_max_abs_error=errors,parent_sha256=sha(a.parent),dataset_sha256=sha(a.data/'dataset.json'),
        caveat='Cached tensors, no shard I/O, family aggregation, startup, checkpoint writes or competing-load allowance. Benchmarked scalar weights differ from the full family-normalized objective but execute the same forward/backward graph. No training result retained; no reserved test access.')
    atomic_json(a.out,result);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
