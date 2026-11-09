"""Fit a candidate bidder on archived actual scores; never deploy or run arena.

An advantage-weighted regression experiment (Peng et al., 2019,
https://arxiv.org/abs/1910.00177), with a cross-fitted linear baseline on frozen
parent features, conservative parent distillation, and an unweighted control.
The baseline is training machinery, not a new deployed neural value network.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.bidding_env import (BidObservation, deal_key, encode, legal_mask,
                                      make_board, masked_probabilities, pack_inputs)
from bridge_harness.bidding_outcomes import (advantage_weights, arrays, crossfit_baseline,
                                           family_metrics, load_outcomes, paired_loss, sha)
from bridge_harness.bidding_ppo import Policy, PPO
from bridge_harness.bidding_loop import atomic_json


def emit(event, **values):
    print(json.dumps(dict(event=event, **values)), flush=True)


def read_replay(root, excluded, limit=512):
    """Historical private observations; labels are parent probabilities, not DD."""
    manifest = json.loads((root/'manifest.json').read_text())
    indices = manifest['training_indices']; xs=[]; masks=[]; families=[]
    for path in sorted((root/'batches').glob('*.json')):
        offset = int(path.stem)
        batch = json.loads(path.read_text())
        for j, row in enumerate(batch['rows']):
            b = make_board(manifest['train_seed'], indices[offset+j], 'train')
            family = deal_key(b.hands, True)
            if family != row['deal_id']:
                raise ValueError('Historical replay board identity mismatch')
            if family in excluded:
                continue
            families.append(family)
            for table in row['tables']:
                calls = tuple(table['calls'])
                for turn in range(len(calls)):
                    seat = (b.dealer+turn)%4
                    xs.append(encode(BidObservation(b.hands[seat], seat, b.dealer,
                                                    b.vulnerability, calls[:turn])))
                    masks.append(legal_mask(b.dealer, calls[:turn]))
            if len(families) >= limit:
                x, lengths = pack_inputs(xs)
                return dict(x=x, lengths=lengths, masks=np.array(masks)), families
    raise ValueError('Insufficient historical replay')


def model_arrays(policy, data, with_features=False):
    import tensorflow as tf
    feature_model = tf.keras.Model(policy.model.inputs, policy.model.layers[-2].output) if with_features else None
    n=len(data['x']);probs=np.zeros((n,40),np.float32);features=None
    order=np.argsort(data['lengths'],kind='stable')
    for at in range(0, n, 512):
        ix=order[at:at+512];lengths=data['lengths'][ix]
        x=data['x'][ix,:int(lengths.max())]
        raw,_=policy.predict(x,lengths)
        probs[ix]=masked_probabilities(raw,data['masks'][ix]).astype(np.float32)
        if with_features:
            h=feature_model([x],training=False).numpy()[np.arange(len(x)),lengths-1]
            # Only frozen private/public prefix features; no outcomes/future bids.
            f=np.concatenate([h,x[np.arange(len(x)),lengths-1,:33]],axis=1)
            if features is None:features=np.zeros((n,f.shape[1]),np.float32)
            features[ix]=f
    return probs,features


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('outcomes','manifest','source','replay','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--epochs',type=int,default=6)
    p.add_argument('--learning-rate',type=float,default=5e-6)
    p.add_argument('--sources',nargs='+',default=['g0001-bid40k','g0001-direct'])
    a=p.parse_args()
    if a.out.exists():raise ValueError('Use a fresh output directory')
    a.out.mkdir(parents=True)
    started=time.monotonic()
    examples,counts=load_outcomes(a.outcomes,a.manifest,set(a.sources))
    data=arrays(examples); del examples
    training=data['split']=='train'; validation=data['split']=='validation'
    if not training.any() or not validation.any():raise ValueError('Both partitions required')
    atomic_json(a.out/'partition.json',{s:sorted(set(data['family'][data['split']==s])) for s in ('train','validation')})
    emit('data_ready',**counts)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(2026110931)
    tf.config.experimental.enable_op_determinism()
    origin=a.source/'dependencies/GIB-BBO-8742_2026-10-23-E30.keras'
    checkpoint=a.source/'run/checkpoints/update-0000314/ckpt-314'
    original=Policy.load(origin)
    base=Policy.load(origin,critic=True); restore=PPO(base,original)
    restore.restore(str(checkpoint))
    actor=tf.keras.Model(base.model.inputs,base.model.outputs[0])
    actor.save(a.out/'parent.keras')
    anchor=Policy.load(a.out/'parent.keras')
    parent_probs,features=model_arrays(anchor,data,True)
    baseline,critic,fold=crossfit_baseline(features,data)
    np.savez_compressed(a.out/'linear-baseline.npz',**critic)
    np.savez_compressed(a.out/'outcome-targets.npz',family=data['family'],split=data['split'],
                        target=data['reward'],baseline=baseline,fold=fold)
    ow=advantage_weights(data['reward'],baseline)
    # Fix the scale using training only, then apply it unchanged to validation.
    ow/=np.average(ow[training],weights=data['weight'][training])
    replay,replay_families=read_replay(a.replay,set(data['family']))
    replay_probs,_=model_arrays(anchor,replay)
    baseline_summary={s:dict(families=len(set(data['family'][mask])),
        baseline_rmse_imp_units=float(np.sqrt(np.average((baseline[mask]-data['reward'][mask])**2,
                                                       weights=data['weight'][mask]))*10),
        zero_rmse_imp_units=float(np.sqrt(np.average(data['reward'][mask]**2,
                                                   weights=data['weight'][mask]))*10))
        for s,mask in [('train_crossfit',training),('validation',validation)]}
    config=dict(schema='actual-outcome-bidder-awr-v1',sources=a.sources,counts=counts,
        epochs=a.epochs,learning_rate=a.learning_rate,temperature_imp_units=6.,weight_cap=4.,
        objective='2 * actual-outcome AWR CE + 0.5 * current-parent KL + 1 * historical-parent KL',
        reward='Mean across actual root tables of signed IMP(NS score relative to zero)/10; partnership oriented',
        reward_limitation='Score utility, not an observed paired IMP gain or causal bid advantage',
        baseline='5-fold family cross-fitted ridge on frozen parent/private-prefix features; train-only fit for validation',
        baseline_summary=baseline_summary,source_sha256=sha(__file__),
        data_sha256=sha(a.outcomes),manifest_sha256=sha(a.manifest),parent_sha256=sha(a.out/'parent.keras'),
        outcome_module_sha256=sha(Path(__file__).resolve().parents[1]/'bridge_harness/bidding_outcomes.py'),
        replay_deals=len(replay_families),replay_decisions=len(replay['x']),
        replay_families=replay_families,starting_optimizer_steps=int(restore.optimizer.iterations.numpy()),
        selection='Lowest family-mean outcome-weighted validation negative log likelihood',
        control='Identical parent, optimizer, epochs, random order, and KL terms; all outcome weights equal 1',
        no_new_dd_solves=True,no_arena_changes=True,playing_strength_evaluated=False)
    atomic_json(a.out/'config.json',config)
    emit('baseline_ready',metrics=baseline_summary,replay_deals=len(replay_families))
    prior,prior_families=family_metrics(data,parent_probs,parent_probs,ow,validation)
    results={}; selected_families={}
    train_ix=np.flatnonzero(training)
    # Fixed weights averaged over random minibatches reproduce equal family mass.
    family_weight=data['weight'] / data['weight'][training].mean()
    for name,outcome_factor in [('outcome',ow),('control',np.ones(len(ow),np.float32))]:
        run=a.out/name;run.mkdir()
        policy=Policy.load(origin,critic=True); trainer=PPO(policy,original)
        trainer.restore(str(checkpoint));trainer.optimizer.learning_rate.assign(a.learning_rate)
        deploy=tf.keras.Model(policy.model.inputs,policy.model.outputs[0])
        # Unused old DD critic is preserved in the resumable checkpoint, but it
        # has no role in the actual-outcome loss or the exported actor.
        @tf.function(reduce_retracing=True)
        def step(x,lengths,masks,actions,weights,target,rx,rl,rm,rq):
            def dist(raw,mask):
                z=tf.maximum(raw,1e-12)*tf.cast(mask,tf.float32)
                return z/tf.reduce_sum(z,axis=1,keepdims=True)
            def kl(q,pp):
                return tf.reduce_sum(q*(tf.math.log(tf.maximum(q,1e-12))-
                                       tf.math.log(tf.maximum(pp,1e-12))),axis=1)
            with tf.GradientTape() as tape:
                raw,_=policy.forward(x,lengths);pp=dist(raw,masks)
                rp,_=policy.forward(rx,rl);rp=dist(rp,rm)
                ce=-tf.math.log(tf.maximum(tf.gather(pp,actions,batch_dims=1),1e-12))
                current=kl(target,pp);replay_kl=tf.reduce_mean(kl(rq,rp))
                loss=2*tf.reduce_mean(weights*ce)+.5*tf.reduce_mean(current)+replay_kl
            grads=tape.gradient(loss,policy.model.trainable_variables)
            pairs=[(g,v) for g,v in zip(grads,policy.model.trainable_variables) if g is not None]
            tf.debugging.assert_all_finite(loss,'Nonfinite actual outcome loss')
            gs,norm=tf.clip_by_global_norm([g for g,_ in pairs],.5)
            for g in gs:tf.debugging.assert_all_finite(g,'Nonfinite outcome gradient')
            trainer.optimizer.apply_gradients(zip(gs,[v for _,v in pairs]))
            return loss,replay_kl,norm
        best=prior['weighted_nll'];best_epoch=0;history=[]
        deploy.save(run/'best.keras')
        selected_families[name]=prior_families
        # Save both best and latest Adam states independently.
        trainer.save(run/'best-checkpoint/ckpt')
        latest_manager=tf.train.CheckpointManager(trainer.checkpoint,str(run/'latest-checkpoint'),max_to_keep=1)
        for epoch in range(1,a.epochs+1):
            tick=time.monotonic();rng=np.random.default_rng(2026110931+epoch)
            order=rng.permutation(train_ix)
            order=order[np.argsort(data['lengths'][order],kind='stable')]
            starts=rng.permutation(np.arange(0,len(order),256));batch_metrics=[]
            for at in starts:
                ix=order[at:at+256];ri=rng.integers(len(replay['x']),size=len(ix))
                m=step(data['x'][ix,:int(data['lengths'][ix].max())],data['lengths'][ix],data['masks'][ix],data['actions'][ix],
                    np.asarray(family_weight[ix]*outcome_factor[ix],np.float32),parent_probs[ix],
                    replay['x'][ri,:int(replay['lengths'][ri].max())],replay['lengths'][ri],replay['masks'][ri],replay_probs[ri])
                batch_metrics.append([float(v.numpy()) for v in m])
            probs,_=model_arrays(policy,data)
            val,families=family_metrics(data,probs,parent_probs,ow,validation)
            train_metrics,_=family_metrics(data,probs,parent_probs,ow,training)
            selected=val['weighted_nll'] < best
            if selected:
                best=val['weighted_nll'];best_epoch=epoch
                deploy.save(run/'best.keras');selected_families[name]=families
                # Manager removes superseded selected checkpoints.
                best_manager=tf.train.CheckpointManager(trainer.checkpoint,str(run/'best-checkpoint'),max_to_keep=1)
                best_manager.save(checkpoint_number=epoch)
            latest=latest_manager.save(checkpoint_number=epoch)
            row=dict(epoch=epoch,seconds=time.monotonic()-tick,validation=val,train=train_metrics,
                     selected=selected,mean_batch_metrics=np.mean(batch_metrics,axis=0).tolist())
            history.append(row)
            atomic_json(run/'state.json',dict(epoch=epoch,best_epoch=best_epoch,history=history,latest_checkpoint=latest))
            emit('epoch',run=name,**row)
        deploy.save(run/'last.keras')
        chosen=Policy.load(run/'best.keras');prob,_=model_arrays(chosen,data)
        val,families=family_metrics(data,prob,parent_probs,ow,validation)
        # A frozen export must reproduce the selected evaluation exactly.
        assert abs(val['weighted_nll']-best)<1e-6
        results[name]=dict(complete=True,best_epoch=best_epoch,validation=val,
            vs_parent=paired_loss(prior_families,families),history=history,
            actor_sha256=sha(run/'best.keras'),optimizer_steps=int(trainer.optimizer.iterations.numpy()))
        atomic_json(run/'result.json',results[name]);atomic_json(run/'validation-families.json',families)
    result=dict(complete=True,promoted=False,arena_deployed=False,playing_strength_evaluated=False,
        counts=counts,parent=prior,models=results,baseline=baseline_summary,
        outcome_vs_control=paired_loss(selected_families['control'],selected_families['outcome']),
        elapsed_seconds=time.monotonic()-started,
        interpretation='Descriptive outcome-weighted prediction fit on selection validation; not IMP strength.')
    atomic_json(a.out/'result.json',result);emit('complete',**{k:v for k,v in result.items() if k!='models'})


if __name__=='__main__':main()
