"""Restartable three-arm bidding representation experiment; no promotion."""
import argparse
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_env import BidObservation, CALLS, legal_mask, masked_probabilities
from bridge_harness.bidding_refresh import sha, digest, terminal_scores, expected_imps, clustered_summary
from bridge_harness.bidding_loop import atomic_json
from bridge_harness.core import Board, auction_contract

FEATURES = ('hand', 'calls', 'roles', 'context', 'base', 'hidden')


def collect(rewards, base, adapter, rng, epsilon, explore):
    boards = [Board.from_dict(r['board']) for r in rewards]
    active = [dict(pair=i, room=room, calls=[]) for i in range(len(boards)) for room in (0, 1)]
    rooms = [[None, None] for _ in boards]
    samples = {k:[] for k in FEATURES + ('masks', 'actions', 'old_logp', 'old_value', 'pairs')}
    while active:
        observations = []
        learning = []
        for a in active:
            b = boards[a['pair']]
            seat = (b.dealer + len(a['calls'])) % 4
            observations.append(BidObservation(b.hands[seat], seat, b.dealer, b.vulnerability, tuple(a['calls'])))
            learning.append(seat % 2 == a['room'])
        f = base.encode(observations)
        raw, values = adapter(f) if adapter is not None else (f['base'], np.zeros(len(active)))
        raw, values = np.asarray(raw), np.asarray(values)
        next_active = []
        for j,a in enumerate(active):
            b = boards[a['pair']]
            mask = legal_mask(b.dealer, a['calls'])
            sampled = explore and learning[j]
            p = masked_probabilities(raw[j] if learning[j] else f['base'][j], mask, epsilon if sampled else 0.)
            action = int(rng.choice(40, p=p / p.sum())) if sampled else int(p.argmax())
            if sampled:
                for k in FEATURES:
                    samples[k].append(f[k][j])
                for k,v in dict(masks=mask, actions=action, old_logp=np.log(p[action]),
                                old_value=values[j], pairs=a['pair']).items():
                    samples[k].append(v)
            a['calls'].append(CALLS[action])
            if len(a['calls']) > 320:
                raise ValueError('Illegal auction length')
            try:
                c = auction_contract(b.dealer, a['calls'])
            except ValueError as exc:
                if str(exc) != 'Incomplete auction':
                    raise
                next_active.append(a)
                continue
            scores, source = terminal_scores(b, a['calls'], rewards[a['pair']])
            rooms[a['pair']][a['room']] = dict(calls=a['calls'], contract=c.text() if c else None,
                declarer=c.declarer if c else None, ns_scores=scores, reward_source=source)
        active = next_active
    rows = [dict(family=r['family'], source=r['source'], tables=t) for r,t in zip(rewards,rooms)]
    arrays = {k:np.asarray(v) for k,v in samples.items()}
    for k in ('actions', 'pairs'):
        arrays[k] = arrays[k].astype(np.int32)
    for k in ('old_value', 'old_logp'):
        arrays[k] = arrays[k].astype(np.float32)
    return rows, arrays


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--stage', default='run', choices=['run','collect','play','update','eval_collect','eval_play','benchmark'])
    p.add_argument('--variant', default='dense_exact')
    p.add_argument('--seed', type=int, default=101)
    p.add_argument('--split', default='play')
    a = p.parse_args()
    cfg = json.loads(a.config.read_text()); root = Path(cfg['out']); root.mkdir(parents=True, exist_ok=True)
    sources = ['bridge_harness/bidding_structure.py', 'scripts/run_bidding_structure.py',
               'bridge_harness/bidding_env.py','bridge_harness/bidding_refresh.py','bridge_harness/bidding_play_cache.py',
               'bridge_harness/bidding_ppo.py','bridge_harness/core.py','bridge_harness/runner.py']
    play_spec = json.loads((Path(cfg['play_root'])/'manifest.json').read_text())['bots']['3']
    identity = dict(config=cfg, dataset_sha256=sha(cfg['data']), parent_sha256=sha(cfg['parent']),
                    play_spec_digest=digest(play_spec),dds_library_sha256=sha(cfg['dds_library']),
                    source_sha256={s:sha(s) for s in sources})
    if (root/'manifest.json').exists():
        if json.loads((root/'manifest.json').read_text()) != identity:
            raise ValueError('Frozen experiment inputs changed')
    else:
        atomic_json(root/'manifest.json', identity)
    dest = root/f'{a.variant}-s{a.seed}'; dest.mkdir(exist_ok=True)
    state = json.loads((dest/'state.json').read_text()) if (dest/'state.json').exists() else dict(offset=0)
    offset = state['offset']; pending = dest/f'pending-{offset:05d}'
    if a.stage.startswith('eval'):
        pending = dest/f'dev-{a.split}'
    def event(**row):
        row.update(stage=a.stage, variant=a.variant, seed=a.seed, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
        atomic_json(root/'status.json', row); print(json.dumps(row), flush=True)
    start = time.monotonic()

    if a.stage == 'run':
        lock = (root/'supervisor.lock').open('a+')
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        cache = root/'play-cache'; cache.mkdir(exist_ok=True)
        # Immutable completed outcome files can be reused. The SQLite cache is private.
        for seed_root in cfg.get('seed_caches', []):
            for path in Path(seed_root).glob('*.json.gz'):
                target = cache/path.name
                if not target.exists():
                    shutil.copy2(path, target)
        env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', TF_CPP_MIN_LOG_LEVEL='3', TF_ENABLE_ONEDNN_OPTS='0')
        def run(stage, variant, seed, split='play'):
            command = [sys.executable, __file__, '--config', str(a.config.resolve()), '--stage', stage,
                       '--variant', variant, '--seed', str(seed), '--split', split]
            with (root/'pipeline.log').open('a') as log:
                subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        # Finish all first-seed arms before second-seed replications.
        for seed in cfg['seeds']:
            for variant in cfg['variants']:
                directory = root/f'{variant}-s{seed}'
                while not (directory/'complete.json').exists():
                    for stage in ('collect','play','update'):
                        run(stage, variant, seed)
                for split in ('dds','play'):
                    run('eval_collect',variant,seed,split)
                    run('eval_play',variant,seed,split)
                event(phase='arm_complete',completed_variant=variant,completed_seed=seed)
        result = {}
        for seed in cfg['seeds']:
            for variant in cfg['variants']:
                result[f'{variant}-s{seed}'] = {split:json.loads((root/f'{variant}-s{seed}'/f'dev-{split}.json').read_text())['summary'] for split in ('dds','play')}
        # Paired architecture differences, one outcome per family per seed.
        paired = {}
        for split in ('dds','play'):
            for left,right in [('dense_exact','dense_compressed'),('attention_exact','dense_exact')]:
                rows = []
                for seed in cfg['seeds']:
                    l = json.loads((root/f'{left}-s{seed}'/f'dev-{split}.json').read_text())['rows']
                    r = {x['family']:x for x in json.loads((root/f'{right}-s{seed}'/f'dev-{split}.json').read_text())['rows']}
                    rows.extend(dict(family=x['family'],imps=x['imps']-r[x['family']]['imps']) for x in l)
                paired[split+'/'+left+'-minus-'+right] = clustered_summary(rows)
        atomic_json(root/'results.json', dict(arms=result,paired=paired,selection='none',
            note='Development screen only. Seeds are averaged within family for paired SE. No test data opened or model promoted.'))
        atomic_json(root/'complete.json',dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
        return

    if a.stage in ('play','eval_play'):
        meta = json.loads(pending.with_suffix('.json').read_text())
        if meta.get('scored'):
            return
        from bridge_harness.bidding_play_cache import MissingPlayCache
        spec = json.loads((Path(cfg['play_root'])/'manifest.json').read_text())['bots']['3']
        cache = MissingPlayCache(root/'play-cache',cfg['play_root'],spec,dds_library=cfg['dds_library'],event=event)
        for reward,row in zip(meta['batch'],meta['rows']):
            b = Board.from_dict(reward['board'])
            for room in row['tables']:
                if room['ns_scores'] is None:
                    room['ns_scores'],room['reward_source'] = cache.score(b,room['calls'])
            row['imps'] = expected_imps(*[r['ns_scores'] for r in row['tables']])
        cache.close()
        meta.update(scored=True,play_seconds=time.monotonic()-start,new_plays=cache.plays,cache_hits=cache.hits)
        if a.stage == 'eval_play':
            meta['summary'] = clustered_summary(meta['rows'])
        atomic_json(pending.with_suffix('.json'), meta)
        event(phase='scored', pairs=len(meta['batch']), new_plays=cache.plays, seconds=time.monotonic()-start,
              summary=meta.get('summary'))
        return

    if a.stage == 'collect' and pending.with_suffix('.json').exists():
        return
    if a.stage == 'eval_collect' and pending.with_suffix('.json').exists():
        return
    if a.stage in ('collect','update') and offset >= cfg['pairs']:
        return
    import tensorflow as tf
    from bridge_harness.bidding_structure import FrozenBidder, make_adapter, Trainer
    tf.config.threading.set_intra_op_parallelism_threads(cfg['threads'])
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(a.seed)
    model = make_adapter(a.variant)
    trainer = Trainer(model, cfg['learning_rate'], cfg['exploration'], cfg['anchor_weight'])
    if state.get('checkpoint'):
        trainer.checkpoint.restore(state['checkpoint']).assert_consumed()
    if a.stage == 'update':
        meta = json.loads(pending.with_suffix('.json').read_text())
        if not meta.get('scored') or sha(pending.with_suffix('.npz')) != meta['npz_sha256']:
            raise ValueError('Pending data incomplete or changed')
        with np.load(pending.with_suffix('.npz')) as z:
            arrays = {k:z[k] for k in z.files}
        rewards = [meta['rows'][int(i)]['imps'] for i in arrays['pairs']]
        rng = np.random.default_rng(); rng.bit_generator.state = meta['rng_state']
        metrics = trainer.train(arrays,rewards,rng,cfg['epochs'],cfg['minibatch'])
        (dest/'optimizer').mkdir(exist_ok=True)
        checkpoint = trainer.checkpoint.save(str(dest/'optimizer/ckpt'))
        newstate = dict(offset=offset+len(meta['batch']),checkpoint=checkpoint)
        atomic_json(dest/'state.json',newstate)
        atomic_json(dest/f'batch-{offset:05d}.json',dict(metrics=metrics,seconds=time.monotonic()-start,
            collection_seconds=meta['collect_seconds'],play_seconds=meta['play_seconds'],new_plays=meta['new_plays']))
        if newstate['offset'] >= cfg['pairs']:
            model.save_weights(dest/'adapter.weights.h5')
            atomic_json(dest/'complete.json',dict(pairs=cfg['pairs'],parameters=model.count_params(),variant=a.variant,seed=a.seed))
        event(phase='trained',pairs=newstate['offset'],metrics=metrics,seconds=time.monotonic()-start)
        return

    data = json.loads(Path(cfg['data']).read_text())
    pools = {s:[r for r in data if r['source']==s and r['split']=='train'] for s in ('play','dds')}
    rng = np.random.default_rng(np.random.SeedSequence([a.seed,offset]))
    if a.stage == 'eval_collect':
        batch = sorted([r for r in data if r['source']==a.split and r['split']=='dev'],key=lambda r:r['family'])
        batch = batch[:cfg.get('dev_limits',{}).get(a.split,len(batch))]
    else:
        n = cfg.get('benchmark_pairs',32) if a.stage=='benchmark' else min(cfg['batch_pairs'],cfg['pairs']-offset)
        batch = [pools[s][i] for s in ('play','dds') for i in rng.choice(len(pools[s]),n//2,replace=False)]
        rng.shuffle(batch)
    base = FrozenBidder(cfg['parent'])
    rows,arrays = collect(batch,base,model,rng,cfg['exploration'],a.stage!='eval_collect')
    seconds = time.monotonic()-start
    if a.stage == 'benchmark':
        # Exercise real gradient shapes without changing any experiment checkpoint.
        rewards = np.array([(-1 if i%2 else 1) for i in arrays['pairs']],np.float32)
        tick = time.monotonic()
        metrics = trainer.train(arrays,rewards,rng,cfg['epochs'],cfg['minibatch'])
        report = dict(variant=a.variant,parameters=model.count_params(),pairs=len(batch),decisions=len(arrays['pairs']),
            collect_seconds=seconds,update_seconds=time.monotonic()-tick,
            missing_play_rooms=sum(t['ns_scores'] is None for row in rows for t in row['tables']),
            metrics=metrics,synthetic_rewards_for_timing_only=True)
        atomic_json(root/f'benchmark-{a.variant}.json',report); print(json.dumps(report),flush=True)
        return
    np.savez_compressed(pending.with_suffix('.npz'),**arrays)
    meta = dict(offset=offset,batch=batch,rows=rows,rng_state=rng.bit_generator.state,
        collect_seconds=seconds,npz_sha256=sha(pending.with_suffix('.npz')))
    atomic_json(pending.with_suffix('.json'),meta)
    event(phase='collected',pairs=len(batch),decisions=len(arrays['pairs']),seconds=seconds,
          missing_play_rooms=sum(t['ns_scores'] is None for row in rows for t in row['tables']))


if __name__ == '__main__':
    main()
