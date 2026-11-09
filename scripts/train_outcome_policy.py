"""Continue Gen3's individual-outcome regression; evaluate choices only afterward."""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import sys
import time
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','TF_NUM_INTRAOP_THREADS','TF_NUM_INTEROP_THREADS'):
    os.environ[key]='1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
os.environ['TF_ENABLE_ONEDNN_OPTS']='0'
os.environ['ONEDNN_PRIMITIVE_CACHE_CAPACITY']='16'
os.environ['MALLOC_ARENA_MAX']='2'
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.auction_policy import build_model,restore_parent,export_weights,AuctionSelectorWeights
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json
from scripts.policy_choice_data import scores,weights
from scripts.train_policy_choices import family_summary,choose,metrics

INPUTS=('state','actions','calls','seats')

def shards(folder,manifest,kind,split):
    return [folder/e['file'] for e in manifest['shards'] if e['kind']==kind and e['split']==split]

def load(path):
    with np.load(path,allow_pickle=False) as z:
        return {k:z[k] for k in z.files}

def batches(data,n=256):
    for start in range(0,len(data['y']),n):
        yield {k:v[start:start+n] for k,v in data.items()}

def train(folder,out,parent,rank_candidate,previous_families,epochs=8):
    if out.exists():raise ValueError('Use a new fit directory')
    out.mkdir(parents=True)
    manifest=json.loads((folder/'dataset.json').read_text())
    if not manifest['validated'] or manifest['schema']!='arena-individual-outcomes-v1':raise ValueError('Wrong data')
    for e in manifest['shards']:
        if sha(folder/e['file'])!=e['sha256']:raise ValueError('Dataset shard changed')
    family_meta=json.loads((folder/'families.json').read_text())
    groups={s:{r['family'] for r in family_meta if r['split']==s and r['outcome_rows']} for s in ('train','validation','test')}
    if any(groups[a]&groups[b] for a,b in [('train','validation'),('train','test'),('test','validation')]):
        raise ValueError('Family overlap')
    config=dict(seed=2026110923,epochs=epochs,learning_rate=2e-4,weight_decay=1e-4,batch_size=128,
        dataset_sha256=sha(folder/'dataset.json'),parent_sha256=sha(parent),
        loss='MSE of individual remaining-partnership-trick outcomes; equal total family weight; no IMP contrasts or preference labels',
        architecture='Unchanged Gen3: fixed PIMC q + shared state-value + centered action correction; all layers trainable',
        initialization='Gen3 checkpoint, preserving values and rankings at epoch zero',
        selection='Minimum validation-family outcome MSE; epoch zero eligible. No choice/IMP metric used for selection',
        test_rule='Read test outcomes and branch labels only after epoch selection; no adaptation to test results',
        source_sha256=sha(Path(__file__)))
    atomic_json(out/'config.json',config)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(config['seed'])
    tf.config.experimental.enable_op_determinism()
    first=load(shards(folder,manifest,'outcomes','validation')[0])
    model=build_model(first['state'].shape[1],first['actions'].shape[-1])
    restore_parent(model,parent)
    old=AuctionSelectorWeights(parent)
    opt=tf.keras.optimizers.AdamW(config['learning_rate'],weight_decay=config['weight_decay'],clipnorm=1.)
    opt.build(model.trainable_variables)
    checkpoint=tf.train.Checkpoint(model=model,optimizer=opt)
    manager=tf.train.CheckpointManager(checkpoint,str(out/'resume'),max_to_keep=1)
    train_rows=sum(e['rows'] for e in manifest['shards'] if e['kind']=='outcomes' and e['split']=='train')
    weight_scale=train_rows/len(groups['train'])

    def values(d,training=False):
        raw=model({k:d[k] for k in INPUTS},training=training)
        mask=tf.cast(d['mask'],tf.float32)
        action=raw['score'][...,0]
        action-=tf.reduce_sum(action*mask,1,keepdims=True)/tf.reduce_sum(mask,1,keepdims=True)
        state=tf.cast(d['q'],tf.float32)+raw['value']
        return state+action,state

    @tf.function(reduce_retracing=True)
    def predict(d):return values(d)

    @tf.function(reduce_retracing=True)
    def step(d):
        with tf.GradientTape() as tape:
            pred,_=values(d,True)
            selected=tf.gather(pred,tf.cast(d['chosen'],tf.int32),axis=1,batch_dims=1)
            loss=tf.reduce_mean(tf.cast(d['weight'],tf.float32)*weight_scale*tf.square(selected-d['y']))
        opt.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
        return loss

    def evaluate(split,save=False):
        accum=defaultdict(lambda:np.zeros(6))
        total=changed=0
        for path in shards(folder,manifest,'outcomes',split):
            d=load(path)
            for b in batches(d):
                pred,state=[v.numpy() for v in predict({k:b[k] for k in (*INPUTS,'q','mask')})]
                prev=old.predict(b)
                ix=np.arange(len(b['y'])); chosen=b['chosen']
                errors=np.stack([(pred[ix,chosen]-b['y'])**2,(prev[ix,chosen]-b['y'])**2,
                                 (state[ix,chosen]-b['y'])**2,(b['q'][ix,chosen]-b['y'])**2],1)
                best=np.where(b['mask']>0,pred,-np.inf).argmax(1)
                oldbest=np.where(b['mask']>0,prev,-np.inf).argmax(1)
                for g in np.unique(b['group']):
                    pick=b['group']==g
                    acc=accum[str(g)]
                    acc[:4]+=errors[pick].sum(0);acc[4]+=pick.sum();acc[5]+=(best[pick]!=oldbest[pick]).sum()
                total+=len(ix);changed+=int((best!=oldbest).sum())
        names=sorted(accum)
        mat=np.array([accum[g][:4]/accum[g][4] for g in names])
        result=dict(rows=total,families=len(names),new_mse=float(mat[:,0].mean()),gen3_mse=float(mat[:,1].mean()),
            state_only_mse=float(mat[:,2].mean()),pimc_mse=float(mat[:,3].mean()),
            mse_change=family_summary(mat[:,0]-mat[:,1],names),argmax_change_fraction=changed/total)
        if save:atomic_json(out/(split+'-outcomes-by-family.json'),{g:accum[g].tolist() for g in names})
        return result

    check={k:v[:64] for k,v in first.items()}
    init_error=float(np.max(np.abs(predict({k:check[k] for k in (*INPUTS,'q','mask')})[0].numpy()-old.predict(check))))
    if init_error>1e-5:raise ValueError('Initial values differ from parent')
    del first,check
    initial=evaluate('validation')
    best=initial['new_mse'];best_epoch=0
    export_weights(model,out/'best.npz')
    history=[dict(epoch=0,validation=initial)]
    start=time.time()
    paths=shards(folder,manifest,'outcomes','train')
    for epoch in range(1,epochs+1):
        rng=np.random.default_rng(config['seed']+epoch)
        losses=[]
        for number,pi in enumerate(rng.permutation(len(paths))):
            data=load(paths[pi]);order=rng.permutation(len(data['y']))
            for off in range(0,len(order),config['batch_size']):
                ix=order[off:off+config['batch_size']]
                b={k:data[k][ix] for k in (*INPUTS,'q','mask','chosen','y','weight')}
                losses.append(float(step(b)))
            if (number+1)%100==0:
                import resource
                print(json.dumps(dict(event='training-progress',epoch=epoch,shards=number+1,total_shards=len(paths),
                    max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,seconds=time.time()-start)),flush=True)
        val=evaluate('validation')
        if val['new_mse']<best:
            best=val['new_mse'];best_epoch=epoch;export_weights(model,out/'best.npz')
        entry=dict(epoch=epoch,training_loss=float(np.mean(losses)),validation=val,seconds=time.time()-start)
        history.append(entry)
        manager.save(checkpoint_number=epoch)
        atomic_json(out/'training.json',dict(best_epoch=best_epoch,best_validation_mse=best,history=history))
        print(json.dumps(entry),flush=True)
    restore_parent(model,out/'best.npz')
    validation=evaluate('validation',True)
    test_outcomes=evaluate('test',True)
    selected=weights(out/'best.npz')
    rank=weights(rank_candidate)
    prior_groups={r['family'] for r in json.loads(previous_families.read_text())}
    # Only small vectors persist while pair features stream from disk.
    columns=defaultdict(list)
    max_error=0.
    for path in shards(folder,manifest,'pairs','test'):
        d=load(path)
        for b in batches(d):
            n=scores(selected,b,'gen3'); r=scores(rank,b,'rank')
            for k in ('group','depth','current_policy','source','pair','index','y','gen3_contrast','gen4_contrast'):
                columns[k].append(b[k])
            columns['new_contrast'].append(n[:,0]-n[:,1])
            columns['rank_contrast'].append(r[:,0]-r[:,1])
            columns['fresh_family'].append(np.array([g not in prior_groups for g in b['group']]))
    test={k:np.concatenate(v) for k,v in columns.items()}
    root=(test['depth']==0)&test['current_policy'].astype(bool)
    evidence={}
    for label,mask in [('root',root),('fresh_root',root&test['fresh_family']),
                       ('all_depths',test['current_policy'].astype(bool)),('all_pairs',np.ones(len(test['y']),bool))]:
        output={m:metrics(test,test[m+'_contrast'],mask) for m in ('gen3','gen4','rank','new')}
        for other in ('gen3','gen4','rank'):
            gain=(choose(test['new_contrast'][mask])-choose(test[other+'_contrast'][mask]))*test['y'][mask]
            output['new_minus_'+other]=family_summary(gain,test['group'][mask])
        evidence[label]=output
    # Verify the exported deployed model on a full candidate-set batch.
    check=next(batches(load(shards(folder,manifest,'outcomes','validation')[0])))
    exported=AuctionSelectorWeights(out/'best.npz').predict(check)
    error=float(np.max(np.abs(exported-predict({k:check[k] for k in (*INPUTS,'q','mask')})[0].numpy())))
    if error>1e-5:raise ValueError('Exported inference mismatch')
    result=dict(config=config,selected_epoch=best_epoch,selected_sha256=sha(out/'best.npz'),
        parameters=model.count_params(),initialization_max_error=init_error,numpy_max_error=error,
        validation=validation,test_outcomes=test_outcomes,held_out_choices=evidence,
        elapsed_seconds=time.time()-start,promoted=False,whole_game_strength_tested=False,
        limitations=['Outcome regression fits observed mixed frozen continuations, not optimal future play.',
          'Choices are scored between two recorded alternatives, not every legal move.',
          'Earlier test families were previously examined for a different ranking model; fresh_root isolates later families.',
          'Uncertainty clusters by canonical deal family; dependent branch rows are not independent boards.',
          'Remote IMP-only training tensors lack individual trick labels and were not included.'])
    atomic_json(out/'result.json',result)
    np.savez_compressed(out/'test-choice-predictions.npz',**test)
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('data','out','parent','rank-candidate','previous-families'):
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--epochs',type=int,default=8)
    a=p.parse_args()
    train(a.data,a.out,a.parent,a.rank_candidate,a.previous_families,a.epochs)
