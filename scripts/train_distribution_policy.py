"""Fit trick probabilities on individual outcomes; read out expected contract IMPs."""
import argparse
from collections import defaultdict
import gzip
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
from bridge_harness.auction_policy import restore_parent,AuctionSelectorWeights,encode_decision
from bridge_harness.outcome_distribution import (build_distribution_model,export_distribution,
    restore_distribution,DistributionWeights,public_context,imp_payoffs,BINS)
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json
from bridge_harness.core import Board,Game,card
from scripts.train_outcome_policy import shards,load,batches,INPUTS
from scripts.train_policy_choices import family_summary,metrics,choose
from scripts.policy_choice_data import scores,weights,validate_event


def evaluate_choices(folder,manifest,model_path,scalar_path,rank_path,old_families,parent3,parent4):
    """Full proposal sets preserve the scalar mean's action-centering exactly."""
    dist=DistributionWeights(model_path)
    scalar=AuctionSelectorWeights(scalar_path)
    rank=weights(rank_path)
    snapshot=json.loads((folder/'snapshot.json').read_text())
    metadata=json.loads((folder/'families.json').read_text())
    chosen={(f['source'],f['index']):f for f in metadata if f['split']=='test'}
    prior={r['family'] for r in json.loads(old_families.read_text())}
    sources=json.loads((folder/'sources.json').read_text())
    models={}
    # Caller-supplied model checkpoints are pinned in the source manifests.
    for key,path in [('gen3',parent3),('gen4',parent4)]:
        models[key]=weights(path)
    if sha(parent3)!=manifest['parent_sha256'] or sha(parent4)!=manifest['comparator_sha256']:
        raise ValueError('Comparator checkpoints differ from frozen snapshot')
    columns=defaultdict(list)
    for src in sources:
        index=int(Path(src['path']).name.split('.')[0])
        meta=chosen.get((src['source'],index))
        if meta is None:continue
        if sha(src['path'])!=src['sha256']:raise ValueError('Frozen test episode changed')
        record=json.loads(gzip.decompress(Path(src['path']).read_bytes()))
        source_manifest=snapshot['manifests'][src['source']]
        is4=source_manifest['bots'][record['candidate']]['artifact_sha256'].get('policy')==manifest['comparator_sha256']
        observations=[];events=[]
        for ep in record['unique_tables'].values():
            if not ep.get('tables'):continue
            bytable=defaultdict(lambda:defaultdict(list))
            for event in ep['audits']:
                if event['identical_action']:continue
                validate_event(ep,event)
                bytable[event['candidate_table']][event['ply']].append(event)
            for table_id,by_ply in bytable.items():
                game=Game(Board.from_dict(ep['board']))
                for ply,a in enumerate(ep['tables'][table_id]['actions']):
                    if ply in by_ply:
                        x,cards=encode_decision(game.observation(),a)
                        valid=x['mask'][0]>0
                        for event in by_ply[ply]:
                            indices=[int(np.flatnonzero(valid&(cards[0]==card(event[k])))[0])
                                     for k in ('candidate_card','reference_card')]
                            observations.append({k:v[0] for k,v in x.items()})
                            events.append((event,indices))
                    game.play(card(a['card']))
        for off in range(0,len(observations),128):
            rows=observations[off:off+128]
            x={k:np.stack([r[k] for r in rows]) for k in rows[0]}
            values=dist.values(x)
            values.update(scalar=scalar.predict(x),rank=scores(rank,x,'rank'))
            values.update({k:scores(w,x,k) for k,w in models.items()})
            for j,(event,indices) in enumerate(events[off:off+128]):
                for k,v in values.items():columns[k+'_contrast'].append(float(v[j,indices[0]]-v[j,indices[1]]))
                for k,v in dict(group=record['family'],depth=event['depth'],current_policy=is4,
                    source=src['source'],index=record['index'],pair=record['pair'],y=event['gain_imps'],
                    fresh_family=record['family'] not in prior).items():columns[k].append(v)
    data={k:np.asarray(v) for k,v in columns.items()}
    root=(data['depth']==0)&data['current_policy'].astype(bool)
    evidence={}
    labels=('gen3','gen4','rank','scalar','expected_tricks','expected_imps','contract_imps')
    for name,mask in [('root',root),('fresh_root',root&data['fresh_family']),
                       ('all_depths',data['current_policy'].astype(bool)),('all_pairs',np.ones(len(data['y']),bool))]:
        result={k:metrics(data,data[k+'_contrast'],mask) for k in labels}
        for candidate in ('expected_tricks','expected_imps'):
            for base in ('gen3','gen4','rank','scalar'):
                gain=(choose(data[candidate+'_contrast'][mask])-choose(data[base+'_contrast'][mask]))*data['y'][mask]
                result[candidate+'_minus_'+base]=family_summary(gain,data['group'][mask])
        gain=(choose(data['expected_imps_contrast'][mask])-choose(data['expected_tricks_contrast'][mask]))*data['y'][mask]
        result['imps_minus_tricks']=family_summary(gain,data['group'][mask])
        evidence[name]=result
    return evidence,data


def train(folder,out,parent,parent4,scalar,ranking,old_families,epochs=8):
    if out.exists():raise ValueError('Use a fresh fit directory')
    out.mkdir(parents=True)
    ds=json.loads((folder/'dataset.json').read_text())
    if ds['schema']!='arena-individual-outcomes-v1' or not ds['validated']:raise ValueError('Wrong data')
    for entry in ds['shards']:
        if sha(folder/entry['file'])!=entry['sha256']:raise ValueError('Dataset changed')
    fm=json.loads((folder/'families.json').read_text())
    families={s:{r['family'] for r in fm if r['split']==s and r['outcome_rows']} for s in ('train','validation','test')}
    if any(families[a]&families[b] for a,b in [('train','test'),('train','validation'),('validation','test')]):raise ValueError('Family leakage')
    config=dict(seed=2026110924,epochs=epochs,learning_rate=2e-4,weight_decay=1e-4,batch_size=128,
        dataset_sha256=sha(folder/'dataset.json'),parent_sha256=sha(parent),
        loss='Equal-family categorical cross entropy of observed remaining partnership tricks; no IMP supervision',
        selection='Lowest validation-family negative log likelihood; initial checkpoint eligible',
        readout='Expected IMPs against the frozen distribution of the same network expected-trick choice; product probabilities; vulnerability and doubles included',
        secondary_readout='Expected IMPs relative to current contract making exactly, retained as a prespecified diagnostic',
        architecture='Gen3 encoder and scalar mean warm start + zero-initialized state/action categorical residual heads + learned global spread',
        support='14 remaining-partnership-trick outcomes, masked above number of unfinished tricks',
        test_rule='No test outcome or choice labels read until checkpoint selected',source_sha256=sha(Path(__file__)))
    atomic_json(out/'config.json',config)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(config['seed']);tf.config.experimental.enable_op_determinism()
    first=load(shards(folder,ds,'outcomes','validation')[0])
    model=build_distribution_model(first['state'].shape[-1],first['actions'].shape[-1]);restore_parent(model,parent)
    log_sd=tf.Variable(0.,dtype=tf.float32,trainable=True)
    variables=model.trainable_variables+[log_sd]
    optimizer=tf.keras.optimizers.AdamW(config['learning_rate'],weight_decay=config['weight_decay'],clipnorm=1.)
    optimizer.build(variables)
    manager=tf.train.CheckpointManager(tf.train.Checkpoint(model=model,optimizer=optimizer,log_sd=log_sd),str(out/'resume'),max_to_keep=1)
    nrows=sum(e['rows'] for e in ds['shards'] if e['kind']=='outcomes' and e['split']=='train')
    scale=nrows/len(families['train'])

    def logits(b,training=False):
        raw=model({k:b[k] for k in INPUTS},training=training)
        mask=tf.cast(b['mask'],tf.float32);action=raw['score'][...,0]
        action-=tf.reduce_sum(action*mask,1,keepdims=True)/tf.reduce_sum(mask,1,keepdims=True)
        mean=tf.cast(b['q'],tf.float32)+raw['value']+action
        sd=tf.exp(tf.clip_by_value(log_sd,-3.,3.))
        k=tf.range(BINS,dtype=tf.float32)[None,None,:]
        result=-.5*tf.square((k-mean[...,None])/sd)+raw['state_logits'][:,None,:]+raw['action_logits']
        remaining=13-tf.cast(tf.round(b['state'][:,674]*52),tf.int32)//4
        return tf.where(k<=tf.cast(remaining[:,None,None],tf.float32),result,-1e9)

    @tf.function(reduce_retracing=True)
    def step(b):
        with tf.GradientTape() as tape:
            l=tf.gather(logits(b,True),tf.cast(b['chosen'],tf.int32),axis=1,batch_dims=1)
            losses=tf.nn.sparse_softmax_cross_entropy_with_logits(labels=tf.cast(b['y'],tf.int32),logits=l)
            loss=tf.reduce_mean(b['weight']*scale*losses)
        optimizer.apply_gradients(zip(tape.gradient(loss,variables),variables))
        return loss

    @tf.function(reduce_retracing=True)
    def predict(b):return tf.nn.softmax(logits(b),axis=-1)

    export_distribution(model,out/'initial.npz',float(log_sd.numpy()))
    initial_predictor=DistributionWeights(out/'initial.npz')
    old=AuctionSelectorWeights(parent)

    def evaluate(split):
        accum=defaultdict(lambda:np.zeros(7))
        for path in shards(folder,ds,'outcomes',split):
            for b in batches(load(path)):
                p=predict({k:b[k] for k in (*INPUTS,'q','mask')}).numpy()
                ix=np.arange(len(b['y']));chosen=b['chosen'];y=b['y'].astype(int)
                p=p[ix,chosen];p0=initial_predictor.probabilities(b)[ix,chosen]
                mean=(p*np.arange(BINS)).sum(-1);prev=old.predict(b)[ix,chosen]
                c=public_context(b['state'])
                final=np.where(c['declaring'][:,None],c['already'][:,None]+np.arange(BINS),13-c['already'][:,None]-np.arange(BINS))
                make=final>=c['level'][:,None]+6
                true=make[ix,y];prob=(p*make).sum(-1)
                losses=np.stack([-np.log(np.maximum(p[ix,y],1e-30)),-np.log(np.maximum(p0[ix,y],1e-30)),
                    (mean-y)**2,(prev-y)**2,(prob-true)**2,np.sum((p-np.eye(BINS)[y])**2,axis=1)],axis=1)
                for g in np.unique(b['group']):
                    mask=b['group']==g;accum[str(g)][:6]+=losses[mask].sum(0);accum[str(g)][6]+=mask.sum()
        keys=sorted(accum);means=np.array([accum[g][:6]/accum[g][6] for g in keys])
        return dict(rows=int(sum(a[6] for a in accum.values())),families=len(keys),
            nll=float(means[:,0].mean()),initial_gaussian_nll=float(means[:,1].mean()),
            mean_mse=float(means[:,2].mean()),gen3_mean_mse=float(means[:,3].mean()),
            contract_make_brier=float(means[:,4].mean()),categorical_brier=float(means[:,5].mean()),
            nll_change=family_summary(means[:,0]-means[:,1],keys),mse_change=family_summary(means[:,2]-means[:,3],keys))

    initial=evaluate('validation');best=initial['nll'];best_epoch=0
    export_distribution(model,out/'best.npz',float(log_sd.numpy()))
    history=[dict(epoch=0,validation=initial)];start=time.time()
    paths=shards(folder,ds,'outcomes','train')
    for epoch in range(1,epochs+1):
        rng=np.random.default_rng(config['seed']+epoch);losses=[]
        for number,pi in enumerate(rng.permutation(len(paths))):
            d=load(paths[pi]);order=rng.permutation(len(d['y']))
            for off in range(0,len(order),config['batch_size']):
                ix=order[off:off+config['batch_size']]
                losses.append(float(step({k:d[k][ix] for k in (*INPUTS,'q','mask','chosen','y','weight')})))
            if (number+1)%100==0:
                import resource
                print(json.dumps(dict(event='training-progress',epoch=epoch,shards=number+1,total_shards=len(paths),
                    max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,seconds=time.time()-start)),flush=True)
        val=evaluate('validation')
        if val['nll']<best:
            best=val['nll'];best_epoch=epoch;export_distribution(model,out/'best.npz',float(log_sd.numpy()))
        entry=dict(epoch=epoch,training_loss=float(np.mean(losses)),validation=val,seconds=time.time()-start)
        history.append(entry);manager.save(checkpoint_number=epoch)
        atomic_json(out/'training.json',dict(best_epoch=best_epoch,best_validation_nll=best,history=history))
        print(json.dumps(entry),flush=True)
    log_sd.assign(restore_distribution(model,out/'best.npz'))
    validation=evaluate('validation');test=evaluate('test')
    check=next(batches(first));del first
    error=float(np.max(np.abs(DistributionWeights(out/'best.npz').probabilities(check)-predict({k:check[k] for k in (*INPUTS,'q','mask')}).numpy())))
    if error>1e-5:raise ValueError('Distribution deployment mismatch')
    evidence,predictions=evaluate_choices(folder,ds,out/'best.npz',scalar,ranking,old_families,parent,parent4)
    result=dict(config=config,parameters=model.count_params()+1,selected_epoch=best_epoch,
        selected_sha256=sha(out/'best.npz'),numpy_max_error=error,validation=validation,test_outcomes=test,
        held_out_choices=evidence,elapsed_seconds=time.time()-start,promoted=False,whole_game_strength_tested=False,
        limitations=['Outcome distribution reflects the observed frozen continuation policies.',
            'IMP readout uses a frozen self-predicted reference distribution and independent product probabilities; no same-deal coupling or other-table model.',
            'Offline two-action choices do not establish full-game strength.',
            'Fresh-root subset excludes families previously reported in the ranking experiment.'])
    atomic_json(out/'result.json',result);np.savez_compressed(out/'test-choice-predictions.npz',**predictions)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('data','out','parent','gen4','scalar','ranking','previous-families'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--epochs',type=int,default=8)
    a=p.parse_args();train(a.data,a.out,a.parent,a.gen4,a.scalar,a.ranking,a.previous_families,a.epochs)
