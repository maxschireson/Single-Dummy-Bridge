"""Checkpointed promoted-policy continuation for the frozen effort pilot.

Uses actual observed outcomes, family weighting, and development only.
"""
import argparse,fcntl,json,os,sys,time
from pathlib import Path
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness import policy_v5
from bridge_harness.belief_capacity import sha
from bridge_harness.selfplay import atomic_json
INPUTS=('state','actions','calls','seats')

def load(path):
    with np.load(path,allow_pickle=False) as z:return {k:z[k] for k in z.files}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,required=True);a=ap.parse_args();out=a.config.parent;cfg=json.loads(a.config.read_text())
    lock=(out/'writer.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (out/'result.json').exists():return
    base=Path(cfg['base']);ds=json.loads((base/'dataset.json').read_text());entries={s:[dict(e,file=str(base/e['file'])) for e in ds['shards'] if e['kind']=='outcomes' and e['split']==s] for s in ('train','validation')}
    if cfg.get('extra'):
        p=Path(cfg['extra']);d=load(p);entries['train'].append(dict(file=str(p),sha256=sha(p),rows=len(d['y'])))
    families={s:set() for s in entries};rows=0
    for sp,es in entries.items():
        for e in es:
            p=Path(e['file']);assert sha(p)==e['sha256'];d=load(p);families[sp].update(map(str,d['group']))
            if sp=='train':rows+=len(d['y'])
    assert not families['train']&families['validation']
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(cfg['seed']);tf.config.experimental.enable_op_determinism()
    policy_v5.MODE='attention';d=load(Path(entries['validation'][0]['file']));model=policy_v5.build_model(d['state'].shape[1],d['actions'].shape[-1]);policy_v5.restore(model,cfg['parent'])
    opt=tf.keras.optimizers.AdamW(cfg['lr'],weight_decay=1e-4,clipnorm=1.);opt.build(model.trainable_variables)
    ckpt=tf.train.Checkpoint(model=model,optimizer=opt);manager=tf.train.CheckpointManager(ckpt,str(out/'checkpoints'),max_to_keep=2)
    scale=rows/len(families['train']);bs=128
    def values(d,training=False):
        raw=model({k:d[k] for k in INPUTS},training=training);mask=tf.cast(d['mask'],tf.float32);action=raw['score'][...,0]
        action-=tf.reduce_sum(action*mask,1,keepdims=True)/tf.reduce_sum(mask,1,keepdims=True)
        return tf.cast(d['q'],tf.float32)+raw['value']+action
    @tf.function(reduce_retracing=True)
    def step(d):
        with tf.GradientTape() as tape:
            pred=values(d,True);chosen=tf.gather(pred,tf.cast(d['chosen'],tf.int32),axis=1,batch_dims=1)
            loss=tf.reduce_mean(tf.cast(d['weight'],tf.float32)*scale*tf.square(chosen-tf.cast(d['y'],tf.float32)))
        opt.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables));return loss
    @tf.function(reduce_retracing=True)
    def predict(d):return values(d)
    def evaluate(label):
        groups={};total=0
        for e in entries['validation']:
            d=load(Path(e['file']))
            for lo in range(0,len(d['y']),256):
                b={k:v[lo:lo+256] for k,v in d.items()};x={k:b[k] for k in (*INPUTS,'q','mask')};p=predict(x).numpy();err=(p[np.arange(len(p)),b['chosen']]-b['y'])**2
                for g,v in zip(b['group'],err):
                    z=groups.setdefault(str(g),[0.,0]);z[0]+=float(v);z[1]+=1
                total+=len(p)
        atomic_json(out/(label+'-families.json'),groups)
        return dict(mse=float(np.mean([v[0]/v[1] for v in groups.values()])),families=len(groups),positions=total)
    statepath=out/'state.json'
    if statepath.exists():
        state=json.loads(statepath.read_text());assert state['config_sha256']==sha(a.config);ckpt.restore(state['checkpoint']).assert_consumed()
    else:
        state=dict(config_sha256=sha(a.config),completed_epochs=0,offset=0,history=[],created=time.time(),active_seconds=0.,baseline=evaluate('epoch-0'))
        policy_v5.export(model,out/'epoch-0.npz')
    def save():
        state['checkpoint']=manager.save(checkpoint_number=int(opt.iterations.numpy()));state['optimizer_steps']=int(opt.iterations.numpy());atomic_json(statepath,state)
    save();epoch=state['completed_epochs']+1;cursor=0;start=time.monotonic()
    for j in np.random.default_rng(cfg['seed']+epoch).permutation(len(entries['train'])):
        e=entries['train'][int(j)];d=load(Path(e['file']));order=np.random.default_rng([cfg['seed'],epoch,int(j)]).permutation(len(d['y']))
        for lo in range(0,len(order),bs):
            cursor+=1
            if cursor<=state['offset']:continue
            ix=order[lo:lo+bs];b={k:d[k][ix] for k in (*INPUTS,'q','mask','chosen','y','weight')};loss=float(step(b))
            if not np.isfinite(loss):raise ValueError('Nonfinite loss')
            state['offset']=cursor
            if cursor%100==0:atomic_json(out/'status.json',dict(epoch=epoch,offset=cursor,updated=time.time()))
            if cursor%250==0:
                state['active_seconds']+=time.monotonic()-start;start=time.monotonic();save()
    metrics=evaluate(f'epoch-{epoch}');policy_v5.export(model,out/f'epoch-{epoch}.npz');state['active_seconds']+=time.monotonic()-start
    state['history'].append(dict(epoch=epoch,metrics=metrics));state.update(completed_epochs=epoch,offset=0);save()
    print(json.dumps(dict(arm=out.name,epoch=epoch,metrics=metrics,active_seconds=state['active_seconds'])),flush=True)
    if epoch>=cfg['epochs']:atomic_json(out/'result.json',dict(config=cfg,history=state['history'],baseline=state['baseline'],active_seconds=state['active_seconds'],train_families=len(families['train']),test_evaluated=False,promoted=False))

if __name__=='__main__':main()
