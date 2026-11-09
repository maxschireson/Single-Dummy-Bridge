#!/usr/bin/env python3
"""Warm-start auction belief with bidding records and equal greedy-BEN replay.

Separate validation for both behavior distributions; epoch zero is selectable.
No test labels, policy updates, DDS, playing-strength claims, or bot promotion.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from bridge_harness.auction_belief import SCHEMA, make_model
from bridge_harness.bidding_belief_data import sha
from bridge_harness.belief_model import masked_loss, masked_probabilities
from bridge_harness.selfplay import atomic_json
from scripts.train_belief import totals, summarize

INPUTS = ('state', 'calls', 'seats')


def load(path):
    with np.load(path, allow_pickle=False) as z:
        d = {k: z[k] for k in (*INPUTS, 'owner_target', 'owner_loss_mask', 'kind')}
    y, mask = d['owner_target'], d['owner_loss_mask']
    if not np.all((y >= 0) & (y < 4)) or not np.array_equal(mask, y != 0):
        raise ValueError('Invalid ownership labels/mask')
    if not np.all(mask.sum(-1) == 39) or not np.array_equal(d['state'][:, :52] != 0, y == 0):
        raise ValueError('Own-hand inputs disagree with labels')
    return d


def batch(d, ix):
    x = {k: d[k][ix] for k in INPUTS}
    y, m = d['owner_target'][ix].astype(np.int32), d['owner_loss_mask'][ix].astype(np.float32)
    support = np.ones((*y.shape, 4), bool)
    support[:, :, 0] = False
    support[x['state'][:, :52].astype(bool)] = [True, False, False, False]
    return x, y, m, support


def selection_score(metrics):
    return sum(v['complete_auction']['nll'] for v in metrics.values()) / len(metrics)


def acceptable(metrics, parent, best, tolerance=1e-4):
    # Protect the current greedy bidder, both completed auctions and prefixes.
    protected = all(metrics['ben'][k]['nll'] <= parent['ben'][k]['nll'] + tolerance
                    for k in ('all', 'complete_auction'))
    return protected and selection_score(metrics) < best - 1e-5


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--parent-weights', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--epochs', type=int, default=8)
    p.add_argument('--patience', type=int, default=3)
    p.add_argument('--batch-size', type=int, default=1024)
    p.add_argument('--threads', type=int, default=1)
    p.add_argument('--learning-rate', type=float, default=0.0002)
    p.add_argument('--seed', type=int, default=2026110901)
    p.add_argument('--run-seconds', type=float, default=240)
    a = p.parse_args()
    if min(a.epochs, a.patience, a.batch_size, a.threads, a.run_seconds, a.learning_rate) <= 0 or a.batch_size < 2:
        raise ValueError('Positive settings and batch size >=2 required')
    ds = json.loads((a.data / 'dataset.json').read_text())
    if ds['schema'] != SCHEMA or not ds['validated'] or ds['bidding_evaluation_imported']:
        raise ValueError('Audited train-only bidding data required')
    paths = {}
    for split in ('train', 'validation'):
        paths[split] = []
        for entry in ds['shards'][split]:
            path = a.data / entry['file']
            if sha(path) != entry['sha256']:
                raise ValueError('Bidding dataset changed')
            paths[split].append(path)
        old = ds['legacy'][split]
        if sha(old['path']) != old['sha256']:
            raise ValueError('Legacy replay changed')
    config = dict(dataset_sha256=sha(a.data/'dataset.json'), parent_sha256=sha(a.parent_weights),
        epochs=a.epochs, patience=a.patience, batch_size=a.batch_size, threads=a.threads,
        learning_rate=a.learning_rate, seed=a.seed, replay_fraction=0.5,
        source_sha256={name:sha(ROOT/name) for name in ('scripts/train_bidding_belief.py',
            'bridge_harness/auction_belief.py', 'bridge_harness/belief_model.py')})
    a.out.mkdir(parents=True, exist_ok=True)
    state_path = a.out / 'state.json'
    if (a.out / 'config.json').exists():
        if json.loads((a.out/'config.json').read_text()) != config:
            raise ValueError('Training configuration changed on resume')
    else:
        atomic_json(a.out/'config.json', config)
        shutil.copyfile(a.parent_weights, a.out/'parent.npz')
    if state_path.exists() and json.loads(state_path.read_text())['complete']:
        print((a.out/'result.json').read_text())
        return
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
    os.environ.setdefault('OMP_NUM_THREADS', str(a.threads))
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(a.threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(a.seed)
    tf.config.experimental.enable_op_determinism()
    model = make_model(64)
    with np.load(a.out/'parent.npz', allow_pickle=False) as z:
        model.set_weights([z[f'w{i}'] for i in range(8)])
    optimizer = tf.keras.optimizers.AdamW(a.learning_rate, weight_decay=.0001, clipnorm=1.)
    optimizer.build(model.trainable_variables)
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer)
    manager = tf.train.CheckpointManager(checkpoint, str(a.out/'checkpoints'), max_to_keep=2)
    started = time.monotonic()

    @tf.function(reduce_retracing=True)
    def predict(x):
        return model(x, training=False)

    @tf.function(reduce_retracing=True)
    def step(x,y,m,s):
        with tf.GradientTape() as tape:
            n,d = masked_loss(model(x, training=True),y,m,s)
            loss = n/d
        optimizer.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
        return n,d

    def evaluate():
        answer = {}
        for source, files in (('bidding', paths['validation']), ('ben', [ds['legacy']['validation']['path']])):
            sums = {k:np.zeros(4) for k in ('all','prefix','complete_auction')}
            for path in files:
                d = load(path)
                for start in range(0,len(d['kind']),a.batch_size):
                    ix = slice(start,start+a.batch_size)
                    x,y,m,s = batch(d,ix)
                    prob = masked_probabilities(predict(x).numpy(),s)
                    sums['all'] += totals(prob,y,m)
                    sums['prefix'] += totals(prob,y,m*(d['kind'][ix]==0)[:,None])
                    sums['complete_auction'] += totals(prob,y,m*(d['kind'][ix]==1)[:,None])
            answer[source] = {k:summarize(v) for k,v in sums.items()}
        return answer

    if state_path.exists():
        state = json.loads(state_path.read_text())
        checkpoint.restore(state['checkpoint']).assert_existing_objects_matched()
    else:
        initial = evaluate()
        state = dict(epoch=0, best_epoch=0, best_score=selection_score(initial), stale=0,
                     parent_validation=initial, selected_validation=initial, history=[], complete=False,
                     checkpoint=manager.save(checkpoint_number=0), elapsed_seconds=0.)
        shutil.copyfile(a.out/'parent.npz',a.out/'best.npz')
        atomic_json(state_path,state)
        print(json.dumps(dict(event='parent-validation',metrics=initial)),flush=True)
    replay = load(ds['legacy']['train']['path'])
    half = max(1, a.batch_size//2)
    for epoch in range(state['epoch']+1,a.epochs+1):
        # Restarted epochs use the same sampled replay and ordering.
        tf.keras.utils.set_random_seed(a.seed+epoch)
        rng = np.random.default_rng(np.random.SeedSequence([a.seed,epoch]))
        sums = np.zeros(2)
        epoch_start = time.monotonic()
        for shard in rng.permutation(len(paths['train'])):
            d = load(paths['train'][shard])
            order = rng.permutation(len(d['kind']))
            for start in range(0,len(order),half):
                ix = order[start:start+half]
                ri = rng.integers(len(replay['kind']),size=len(ix))
                combined = {k:np.concatenate([d[k][ix],replay[k][ri]],axis=0) for k in d}
                x,y,m,s = batch(combined,slice(None))
                n,den = step(x,y,m,s)
                sums += [float(n),float(den)]
        metrics = evaluate()
        row = dict(epoch=epoch,seconds=time.monotonic()-epoch_start,
                   train_nll=float(sums[0]/sums[1]),validation=metrics)
        state['history'].append(row)
        state['stale'] += 1
        if acceptable(metrics,state['parent_validation'],state['best_score']):
            state.update(best_epoch=epoch,best_score=selection_score(metrics),stale=0,selected_validation=metrics)
            # Per-epoch files keep an interrupted checkpoint transaction recoverable.
            dest = a.out/f'best-epoch-{epoch}.npz'
            np.savez_compressed(dest,**{f'w{i}':w for i,w in enumerate(model.get_weights())})
            state['selected_file'] = dest.name
        state.update(epoch=epoch,checkpoint=manager.save(checkpoint_number=epoch),
                     complete=epoch==a.epochs or state['stale']>=a.patience)
        state['elapsed_seconds'] += time.monotonic()-epoch_start
        atomic_json(state_path,state)
        print(json.dumps(row),flush=True)
        if state['complete'] or time.monotonic()-started >= a.run_seconds:
            break
    selected = a.out/state['selected_file'] if state['best_epoch'] else a.out/'parent.npz'
    shutil.copyfile(selected,a.out/'best.npz')
    with np.load(selected,allow_pickle=False) as z:
        model.set_weights([z[f'w{i}'] for i in range(8)])
    # Verify that the NumPy player sees exactly the selected TensorFlow model.
    from bridge_harness.bidding_sampling import AuctionWeights
    sample = load(paths['validation'][0])
    x = {k:sample[k][:128] for k in INPUTS}
    error = float(np.max(np.abs(AuctionWeights(selected).predict(x)-model(x,training=False).numpy())))
    if error > 1e-5:
        raise ValueError(f'NumPy/TensorFlow export mismatch: {error}')
    result = dict(status='complete' if state['complete'] else 'paused',
        best_epoch=state['best_epoch'],epochs=state['epoch'],seconds=state['elapsed_seconds'],
        parent_validation=state['parent_validation'],selected_validation=state['selected_validation'],
        dataset_sha256=config['dataset_sha256'],parent_sha256=config['parent_sha256'],
        selected_weights=str((a.out/'best.npz').resolve()),selected_sha256=sha(a.out/'best.npz'),
        numpy_max_error=error,parameters=model.count_params(),test_evaluated=False,
        playing_strength_evaluated=False,promoted=False,additional_dds_calls=0,
        selection='Mean complete-auction validation NLL across two sources; BEN all/complete NLL protected within 0.0001.',
        caveat=ds['split_note'])
    atomic_json(a.out/'result.json',result)
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    main()
