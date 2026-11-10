"""Run one collect/play/update stage with no shared TensorFlow/DDS residency."""
import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import resource
import sys
import time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_refresh import auction_pairs,expected_imps,sha
from bridge_harness.bidding_env import pack_inputs
from bridge_harness.bidding_loop import atomic_json
from bridge_harness.core import Board


def main():
    p=argparse.ArgumentParser()
    for name in ['data','parent','anchor','out','play-root','dds-library','config','variant','stage']:
        p.add_argument('--'+name,required=True)
    a=p.parse_args();root=Path(a.out);dest=root/a.variant;dest.mkdir(parents=True,exist_ok=True)
    lock=(root/'writer.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cfg=json.load(open(a.config));manifest=json.load(open(root/'manifest.json'))
    if manifest['config']!=cfg or any(manifest[k+'_sha256']!=sha(v) for k,v in
           [('dataset',a.data),('parent',a.parent),('anchor',a.anchor)]):raise ValueError('Frozen input changed')
    for path,expected in manifest['source_sha256'].items():
        if sha(path)!=expected:raise ValueError('Frozen source changed: '+path)
    pin=root/'staged-source.json';identity={str(Path(__file__).relative_to(Path.cwd())):sha(__file__)}
    if pin.exists() and json.load(open(pin))!=identity:raise ValueError('Staged runner changed')
    if not pin.exists():atomic_json(pin,identity)
    state=json.load(open(dest/'state.json')) if (dest/'state.json').exists() else dict(offset=0)
    offset=state['offset'];pending=dest/f'pending-{offset:05d}'
    if offset>=cfg['pairs_per_candidate']:return
    variant=next(v for v in cfg['variants'] if v['name']==a.variant)
    def event(**row):
        row.update(variant=a.variant,stage=a.stage,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                   peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
        atomic_json(root/'status.json',row);print(json.dumps(row),flush=True)
    start=time.monotonic()

    if a.stage=='play':
        meta=json.load(open(pending.with_suffix('.json')))
        if meta.get('scored'):return
        from bridge_harness.bidding_play_cache import MissingPlayCache
        spec=json.load(open(Path(a.play_root)/'manifest.json'))['bots']['3']
        cache=MissingPlayCache(root/'play-cache',a.play_root,spec,dds_library=a.dds_library,event=event)
        for reward,row in zip(meta['batch'],meta['rows']):
            b=Board.from_dict(reward['board'])
            for room in row['tables']:
                if room['ns_scores'] is None:
                    room['ns_scores'],room['reward_source']=cache.score(b,room['calls'])
            row['imps']=expected_imps(*[r['ns_scores'] for r in row['tables']])
        cache.close();meta.update(scored=True,play_seconds=time.monotonic()-start,new_plays=cache.plays)
        atomic_json(pending.with_suffix('.json'),meta)
        event(phase='batch_play_complete',completed_pairs=offset,new_plays=cache.plays,seconds=time.monotonic()-start)
        return

    if a.stage=='collect' and pending.with_suffix('.json').exists():return
    import tensorflow as tf
    from bridge_harness.bidding_ppo import Policy,PPO
    tf.config.threading.set_intra_op_parallelism_threads(cfg['tf_threads'])
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(cfg['seed'])
    candidate=Policy.load(a.parent,critic=True)
    if a.stage=='collect':
        if state.get('checkpoint'):
            tf.train.Checkpoint(model=candidate.model).restore(state['checkpoint']).expect_partial()
        parent=Policy.load(a.parent)
        data=json.load(open(a.data))
        pools={s:[r for r in data if r['source']==s and r['split']=='train'] for s in ['play','dds']}
        rng=np.random.default_rng(np.random.SeedSequence([cfg['seed'],offset]))
        n=min(cfg['batch_pairs'],cfg['pairs_per_candidate']-offset);nplay=int(round(n*variant['play_fraction']))
        batch=[pools['play'][i] for i in rng.choice(len(pools['play']),nplay,replace=False)]
        batch+=[pools['dds'][i] for i in rng.choice(len(pools['dds']),n-nplay,replace=False)]
        rng.shuffle(batch)
        rows,decisions=auction_pairs(batch,candidate,parent,rng,explore=True,epsilon=cfg['exploration'],keep_unscored=True)
        x,lengths=pack_inputs([d['x'] for d in decisions])
        np.savez_compressed(pending.with_suffix('.npz'),x=x,lengths=lengths,
            masks=np.array([d['mask'] for d in decisions]),actions=np.array([d['action'] for d in decisions],np.int32),
            old_logp=np.array([d['old_logp'] for d in decisions],np.float32),
            old_value=np.array([d['old_value'] for d in decisions],np.float32),
            pairs=np.array([d['pair'] for d in decisions],np.int32))
        meta=dict(offset=offset,batch=batch,rows=rows,rng_state=rng.bit_generator.state,
                  collect_seconds=time.monotonic()-start,npz_sha256=sha(pending.with_suffix('.npz')))
        atomic_json(pending.with_suffix('.json'),meta)
        event(phase='batch_collected',completed_pairs=offset,decisions=len(decisions),
              missing_rooms=sum(r['ns_scores'] is None for row in rows for r in row['tables']),seconds=time.monotonic()-start)
        return
    if a.stage!='update':raise ValueError('Unknown stage')
    meta=json.load(open(pending.with_suffix('.json')))
    if not meta.get('scored') or sha(pending.with_suffix('.npz'))!=meta['npz_sha256']:
        raise ValueError('Unscored or changed pending batch')
    anchor=Policy.load(a.anchor)
    trainer=PPO(candidate,anchor,learning_rate=cfg['learning_rate'],epsilon=cfg['exploration'],anchor_weight=variant['anchor_weight'])
    if state.get('checkpoint'):trainer.restore(state['checkpoint'])
    with np.load(pending.with_suffix('.npz')) as z:
        arrays={k:z[k] for k in z.files}
    decisions=[dict(x=arrays['x'][i,:arrays['lengths'][i]],mask=arrays['masks'][i],action=int(arrays['actions'][i]),
        old_logp=float(arrays['old_logp'][i]),old_value=float(arrays['old_value'][i]),
        reward=meta['rows'][int(arrays['pairs'][i])]['imps']) for i in range(len(arrays['lengths']))]
    rng=np.random.default_rng();rng.bit_generator.state=meta['rng_state']
    metrics=trainer.train(decisions,rng,cfg['ppo_epochs'],cfg['minibatch'])
    n=len(meta['batch']);coverage={s:dict(attempted=sum(r['source']==s for r in meta['batch']),
              scored=sum(r['source']==s for r in meta['batch'])) for s in ['play','dds']}
    atomic_json(dest/f'batch-{offset:05d}.json',dict(offset=offset,rows=meta['rows'],coverage=coverage,metrics=metrics,
        seconds=meta['collect_seconds']+meta['play_seconds']+time.monotonic()-start))
    new_state=dict(offset=offset+n,checkpoint=trainer.save(dest/'optimizer/ckpt'))
    atomic_json(dest/'state.json',new_state)
    if new_state['offset']>=cfg['pairs_per_candidate']:
        tf.keras.Model(candidate.model.inputs,candidate.model.outputs[0]).save(dest/'bidder.keras')
        atomic_json(dest/'complete.json',dict(variant=variant,pairs=cfg['pairs_per_candidate'],sha256=sha(dest/'bidder.keras')))
    event(phase='training',completed_pairs=offset+n,target_pairs=cfg['pairs_per_candidate'],coverage=coverage,
          metrics=metrics,seconds=time.monotonic()-start)


if __name__=='__main__':main()
