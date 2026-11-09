"""Warm-start v4 and Adam on broad replay with public-world per-card weights."""
import argparse
from collections import Counter,defaultdict
import json,sys,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import INPUTS,Weights,load,make_model,sha
from scripts.screen_attention_belief import save_json


def read(e):
    if sha(e['file'])!=e['sha256']:raise ValueError('Frozen shard changed')
    d=load(e['file'])
    if e['cohort']=='recent':
        with np.load(e['file'],allow_pickle=False) as z:d['card_weight']=z['card_weight'].astype(np.float32)
    else:d['card_weight']=np.ones(d['owner_target'].shape,np.float32)
    if not np.isfinite(d['card_weight']).all() or np.any((d['card_weight']<1)|(d['card_weight']>4)):raise ValueError('Invalid card weights')
    return d


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--parent',type=Path,default=Path('models/belief-v4.npz'));ap.add_argument('--threads',type=int,default=2)
    ap.add_argument('--epochs',type=int,default=3);ap.add_argument('--smoke-shards',type=int,default=0)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(a.out/'writer.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cfg=json.loads((a.data/'manifest.json').read_text());ds=json.loads((a.data/'dataset.json').read_text())
    if sha(a.parent)!=cfg['parent_sha256'] or sha(a.data/'manifest.json')!=ds['manifest_sha256']:
        raise ValueError('Frozen configuration mismatch')
    entries=ds['shards']
    if a.smoke_shards:
        keep=[]
        for cohort in ('historical','recent'):
            for split in ('train','validation'):
                for source in ('play','bidding','ben'):
                    keep += [e for e in entries if e['cohort']==cohort and e['split']==split and e['source']==source][:a.smoke_shards]
        entries=keep
    train=[e for e in entries if e['split']=='train'];validation=[e for e in entries if e['split']=='validation']
    recent_groups=set();counts=Counter();domain_mass=Counter();positions=targets=0;train_groups=set();val_groups=set()
    for e in train:
        d=read(e);groups=d['split_group'].astype(str);mass=(d['owner_loss_mask']*d['card_weight']).sum(1)
        for g,n in zip(groups,mass):counts[e['source'],g]+=float(n)
        train_groups.update(groups);positions+=len(groups);targets+=int(d['owner_loss_mask'].sum())
        if e['cohort']=='recent':recent_groups.update(groups)
    for e in validation:
        with np.load(e['file'],allow_pickle=False) as z:val_groups.update(map(str,z['split_group']))
    if train_groups & val_groups:raise ValueError('Train/validation family overlap')
    for source,g in counts:domain_mass[source]+=2 if g in recent_groups else 1
    domain={'play':.5,'bidding':.25,'ben':.25}
    coeff={k:positions*domain[k[0]]*(2 if k[1] in recent_groups else 1)/(domain_mass[k[0]]*v) for k,v in counts.items()}
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(a.threads);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(cfg['seed']);tf.config.experimental.enable_op_determinism()
    model=make_model((256,128));opt=tf.keras.optimizers.AdamW(cfg['learning_rate'],weight_decay=.0001,clipnorm=1.)
    opt.build(model.trainable_variables);ckpt=tf.train.Checkpoint(model=model,optimizer=opt)
    manager=tf.train.CheckpointManager(ckpt,str(a.out/'checkpoints'),max_to_keep=2)
    best_manager=tf.train.CheckpointManager(ckpt,str(a.out/'selected-checkpoint'),max_to_keep=1)
    state_path=a.out/'state.json'
    run_config=dict(**cfg,training_positions=positions,training_card_targets=targets,training_families=len(train_groups),
        validation_families=len(val_groups),dataset_sha256=sha(a.data/'dataset.json'),smoke_shards=a.smoke_shards)
    if (a.out/'config.json').exists():
        prior=json.loads((a.out/'config.json').read_text())
        if prior!=run_config:raise ValueError('Resume configuration changed')
    else:save_json(a.out/'config.json',run_config)
    def export(path):
        tmp=path.with_suffix('.tmp')
        with tmp.open('wb') as f:np.savez_compressed(f,**{f'w{i}':w for i,w in enumerate(model.get_weights())})
        tmp.replace(path)
    @tf.function(reduce_retracing=True)
    def step(x,y,mask,support,card_weight,family_weight):
        with tf.GradientTape() as tape:
            logits=tf.where(support,model(x,training=True),tf.constant(-1e9))
            ce=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y,logits=logits)
            # A short final batch must not give its rows extra gradient mass.
            loss=tf.reduce_sum(tf.reduce_sum(ce*mask*card_weight,1)*family_weight)/float(cfg['batch_size'])
        opt.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
        return loss
    @tf.function(reduce_retracing=True)
    def predict(x):return model(x,training=False)
    def evaluate():
        families=defaultdict(lambda:np.zeros(8))
        for e in validation:
            d=read(e)
            for lo in range(0,len(d['kind']),2048):
                ix=slice(lo,lo+2048);x={k:d[k][ix] for k in INPUTS};y=d['owner_target'][ix];mask=d['owner_loss_mask'][ix]
                z=predict(x).numpy();z=np.where(d['support'][ix],z,-1e9);z-=z.max(-1,keepdims=True)
                p=np.exp(z);p/=p.sum(-1,keepdims=True);true=p[np.arange(len(y))[:,None],np.arange(52),y]
                ce=-np.log(np.maximum(true,1e-30));cw=d['card_weight'][ix]*mask
                acc=(p.argmax(-1)==y);brier=(p*p).sum(-1)-2*true+1
                sums=np.stack([(ce*cw).sum(1),cw.sum(1),(ce*mask).sum(1),mask.sum(1),
                               (acc*mask).sum(1),(brier*mask).sum(1),(mask*(d['card_weight'][ix]>1)).sum(1),
                               (ce*mask*(d['card_weight'][ix]>1)).sum(1)],1)
                for g,kind,v in zip(d['split_group'][ix],d['kind'][ix],sums):
                    if e['source']!='play' and kind!=1:continue
                    families[e['cohort'],e['source'],str(g)]+=v
        grouped=defaultdict(list)
        for key,v in families.items():
            if v[3]:grouped[key[:2]].append(v)
        metrics={}
        for key,values in grouped.items():
            v=np.stack(values)
            metrics['/'.join(key)]=dict(nll=float(np.mean(v[:,2]/v[:,3])),weighted_nll=float(np.mean(v[:,0]/v[:,1])),
                accuracy=float(np.mean(v[:,4]/v[:,3])),brier=float(np.mean(v[:,5]/v[:,3])),families=len(v),
                targets=int(v[:,3].sum()),upweighted_targets=int(v[:,6].sum()),
                upweighted_card_nll=float(np.mean(v[v[:,6]>0,7]/v[v[:,6]>0,6])) if np.any(v[:,6]>0) else None)
        score=.25*metrics['historical/play']['nll']+.25*metrics['recent/play']['weighted_nll']
        score+=.25*metrics['historical/bidding']['nll']+.25*metrics['historical/ben']['nll']
        return dict(score=score,domains=metrics,recent_family_values={k[2]:dict(weighted_nll=v[0]/v[1],nll=v[2]/v[3])
            for k,v in families.items() if k[:2]==('recent','play') and v[3]})
    if state_path.exists():
        state=json.loads(state_path.read_text());ckpt.restore(state['checkpoint']).assert_existing_objects_matched()
    else:
        ckpt.restore(cfg['parent_checkpoint']).assert_existing_objects_matched()
        if any(not np.array_equal(x,y) for x,y in zip(model.get_weights(),Weights(a.parent).weights)):
            raise ValueError('V4 optimizer checkpoint does not match frozen weights')
        opt.learning_rate.assign(cfg['learning_rate'])
        baseline=evaluate();export(a.out/'best.npz')
        state=dict(epoch=0,best_epoch=0,best_score=baseline['score'],baseline=baseline,history=[],
            selected_checkpoint=best_manager.save(checkpoint_number=0),checkpoint=manager.save(checkpoint_number=0),
            parent_optimizer_steps=int(opt.iterations.numpy()))
        save_json(state_path,state);print(json.dumps(dict(stage='baseline',score=baseline['score'],parameters=model.count_params(),positions=positions)),flush=True)
    start=time.time()
    for epoch in range(state['epoch']+1,a.epochs+1):
        epoch_start=time.time();rng=np.random.default_rng(cfg['seed']+epoch);tf.keras.utils.set_random_seed(cfg['seed']+epoch)
        total_loss=0.;seen=0
        for j in rng.permutation(len(train)):
            e=train[j];d=read(e);order=rng.permutation(len(d['kind']))
            for lo in range(0,len(order),cfg['batch_size']):
                ix=order[lo:lo+cfg['batch_size']];x={k:d[k][ix] for k in INPUTS}
                fw=np.array([coeff[e['source'],str(g)] for g in d['split_group'][ix]],np.float32)
                loss=step(x,d['owner_target'][ix].astype(np.int32),d['owner_loss_mask'][ix].astype(np.float32),
                    d['support'][ix],d['card_weight'][ix],fw)
                total_loss+=float(loss)*len(ix);seen+=len(ix)
        metrics=evaluate();base=state['baseline'];diff=[]
        for g,v in metrics['recent_family_values'].items():diff.append(v['weighted_nll']-base['recent_family_values'][g]['weighted_nll'])
        paired=dict(weighted_nll_delta_vs_v4=float(np.mean(diff)),family_cluster_se=float(np.std(diff,ddof=1)/np.sqrt(len(diff))) if len(diff)>1 else None,families=len(diff))
        row=dict(epoch=epoch,seconds=time.time()-epoch_start,training_loss=total_loss/seen,metrics=metrics,paired_recent=paired)
        state['history'].append(row);state['epoch']=epoch
        if metrics['score']<state['best_score']:
            state.update(best_epoch=epoch,best_score=metrics['score'],selected_checkpoint=best_manager.save(checkpoint_number=epoch))
            export(a.out/'best.npz')
        state['checkpoint']=manager.save(checkpoint_number=epoch);save_json(state_path,state)
        save_json(a.out/f'epoch-{epoch}.json',row)
        save_json(a.data/'status.json',dict(stage='dense_training',epoch=epoch,epochs=a.epochs,best_epoch=state['best_epoch'],updated=time.time()))
        print(json.dumps(dict(stage='epoch_complete',epoch=epoch,seconds=row['seconds'],score=metrics['score'],paired_recent=paired)),flush=True)
    ckpt.restore(state['selected_checkpoint']).assert_existing_objects_matched()
    sample=read(validation[0]);x={k:sample[k][:128] for k in INPUTS}
    err=float(np.abs(Weights(a.out/'best.npz').predict(x)-model(x,training=False).numpy()).max())
    if err>1e-5:raise ValueError('NumPy export mismatch')
    result=dict(parameters=model.count_params(),best_epoch=state['best_epoch'],epochs=state['epoch'],
        initial=state['baseline'],selected=state['baseline'] if state['best_epoch']==0 else state['history'][state['best_epoch']-1]['metrics'],
        selected_sha256=sha(a.out/'best.npz'),export_max_error=err,elapsed_this_invocation=time.time()-start,
        history=state['history'],promoted=False,test_evaluated=False)
    save_json(a.out/'result.json',result)
    save_json(a.data/'status.json',dict(stage='complete',best_epoch=state['best_epoch'],parameters=model.count_params(),updated=time.time(),promoted=False,test_evaluated=False))


if __name__=='__main__':main()
