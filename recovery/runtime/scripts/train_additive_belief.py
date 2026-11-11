"""Continue belief weights and Adam, preserving replay and family-normalized recency.

Shared exports are immutable. All source splits stay intact across auction and
play views of a family; original replay validation/test families stay reserved.
"""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.belief_capacity import INPUTS, SCHEMA, Weights, batch, load, make_model, sha
from bridge_harness.selfplay import atomic_json

DOMAIN = {'play': .5, 'bidding': .25, 'ben': .25}


def entries(root, cohort):
    ds = json.loads((root / 'dataset.json').read_text())
    if ds['schema'] != SCHEMA or not ds['validated']:
        raise ValueError('Unvalidated or incompatible dataset')
    rows = []
    for e in ds['shards']:
        p = root / e['file']
        if sha(p) != e['sha256']:
            raise ValueError(f'Changed shard: {p}')
        rows.append(dict(e, path=p, cohort=cohort))
    return rows


def family_counts(rows):
    counts = Counter()
    positions = 0
    for e in rows:
        with np.load(e['path'], allow_pickle=False) as z:
            groups = z['split_group']
            cards = z['owner_loss_mask'].sum(1)
            for g, n in zip(groups, cards):
                counts[e['source'], str(g)] += int(n)
            positions += len(groups)
    return counts, positions


def coefficients(counts, recent, positions):
    """Every family's total weight is 1x or 2x, independent of its row/fork count."""
    masses = Counter()
    for source, group in counts:
        masses[source] += 2. if group in recent else 1.
    return {key: positions * DOMAIN[key[0]] * (2. if key[1] in recent else 1.) /
            (masses[key[0]] * n) for key, n in counts.items() if n}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for k in ('base', 'parent', 'parent-checkpoint', 'out'):
        p.add_argument('--' + k, type=Path, required=True)
    p.add_argument('--supplement', type=Path, action='append', required=True)
    p.add_argument('--epochs', type=int, default=3)
    p.add_argument('--threads', type=int, default=2)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError('Use a new output directory')
    a.out.mkdir(parents=True)
    base = entries(a.base, 'base')
    recent = [e for root in a.supplement for e in entries(root, 'recent')]
    train = [e for e in base + recent if e['split'] == 'train']
    validation = [e for e in base + recent if e['split'] == 'validation']
    tc, nrows = family_counts(train)
    vc, _ = family_counts(validation)
    rc, _ = family_counts([e for e in recent if e['split'] == 'train'])
    train_groups = {g for _, g in tc}
    val_groups = {g for _, g in vc}
    recent_groups = {g for _, g in rc}
    reserved = json.loads((a.base / 'bidding-reserved-families.json').read_text())
    excluded = set(reserved.get('test', [])) | set(reserved.get('validation', []))
    if train_groups & (val_groups | excluded):
        raise ValueError('Training overlaps a reserved validation/test family')
    coeff = coefficients(tc, recent_groups, nrows)
    partition = dict(train_families=sorted(train_groups), validation_families=sorted(val_groups),
                     recent_families=sorted(recent_groups), source_splits_preserved=True,
                     experiment_remapping='None. Original source train/validation/test assignments preserved.')
    atomic_json(a.out / 'partition.json', partition)
    config = dict(epochs=a.epochs, learning_rate=.0002, batch_size=2048, domain_weights=DOMAIN,
                  recency=2, family_normalization='Sum of uncertain-card observation weights per family is fixed.',
                  selection='Lowest 50/25/25 play/bidding/BEN family-mean NLL; equal old/recent cohort weights within each domain.',
                  parent_sha256=sha(a.parent), source_sha256=sha(__file__),
                  dataset_sha256={str(root): sha(root / 'dataset.json') for root in [a.base, *a.supplement]},
                  training_positions=nrows, training_card_observations=sum(tc.values()),
                  training_families=len(train_groups), recent_families=len(recent_groups),
                  validation_families=len(val_groups),
                  observations_by_domain={s: sum(n for (source, _), n in tc.items() if source == s) for s in DOMAIN})
    atomic_json(a.out / 'config.json', config)
    print(json.dumps(dict(event='data_ready', **config)), flush=True)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(a.threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(2026110914)
    tf.config.experimental.enable_op_determinism()
    model = make_model((256, 128))
    optimizer = tf.keras.optimizers.AdamW(.0002, weight_decay=.0001, clipnorm=1.)
    optimizer.build(model.trainable_variables)
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer)
    checkpoint.restore(str(a.parent_checkpoint)).assert_existing_objects_matched()
    parent = Weights(a.parent).weights
    if any(not np.array_equal(x, y) for x, y in zip(model.get_weights(), parent)):
        raise ValueError('Restored Adam checkpoint does not match the current parent weights')
    parent_iterations = int(optimizer.iterations.numpy())
    if parent_iterations <= 0:
        raise ValueError('Optimizer history missing')
    manager = tf.train.CheckpointManager(checkpoint, str(a.out / 'checkpoints'), max_to_keep=1)
    best_manager = tf.train.CheckpointManager(checkpoint, str(a.out / 'selected-checkpoint'), max_to_keep=1)

    @tf.function(reduce_retracing=True)
    def metrics(x, y, mask, support):
        logits = model(x, training=False)
        logits = tf.where(support, logits, tf.constant(-1e9))
        ce = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y, logits=logits)
        correct = tf.cast(tf.argmax(logits, -1, output_type=tf.int32) == y, tf.float32)
        return tf.reduce_sum(ce * mask, 1), tf.reduce_sum(correct * mask, 1), tf.reduce_sum(mask, 1)

    @tf.function(reduce_retracing=True)
    def step(x, y, mask, support, weight):
        with tf.GradientTape() as tape:
            logits = tf.where(support, model(x, training=True), tf.constant(-1e9))
            ce = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=y, logits=logits)
            loss = tf.reduce_mean(tf.reduce_sum(ce * mask, 1) * weight)
        optimizer.apply_gradients(zip(tape.gradient(loss, model.trainable_variables), model.trainable_variables))
        return loss

    def evaluate():
        families = defaultdict(lambda: np.zeros(3, dtype=np.float64))
        for e in validation:
            d = load(e['path'])
            for start in range(0, len(d['kind']), 2048):
                ix = slice(start, start + 2048)
                sums = np.stack([v.numpy() for v in metrics(*batch(d, ix))], axis=1)
                for group, values, kind in zip(d['split_group'][ix], sums, d['kind'][ix]):
                    families[e['cohort'], e['source'], 'all', str(group)] += values
                    if kind == 1:
                        families[e['cohort'], e['source'], 'complete_auction', str(group)] += values
        result = {}
        keys = sorted({k[:3] for k in families})
        for key in keys:
            vals = np.stack([v for k, v in families.items() if k[:3] == key and v[2]])
            pooled = vals.sum(0)
            result['/'.join(key)] = dict(nll=float(np.mean(vals[:, 0] / vals[:, 2])),
                accuracy=float(np.mean(vals[:, 1] / vals[:, 2])), families=len(vals),
                card_observations=int(pooled[2]), card_weighted_nll=float(pooled[0]/pooled[2]),
                card_weighted_accuracy=float(pooled[1]/pooled[2]))
        def aggregate(metric):
            value = 0.
            for source, weight in DOMAIN.items():
                kind = 'all' if source == 'play' else 'complete_auction'
                values = [result[f'{cohort}/{source}/{kind}'][metric] for cohort in ('base','recent')
                          if f'{cohort}/{source}/{kind}' in result]
                value += weight * sum(values) / len(values)
            return value
        return dict(score=aggregate('nll'), accuracy=aggregate('accuracy'), domains=result)

    def save_weights(path):
        np.savez_compressed(path, **{f'w{i}': w for i, w in enumerate(model.get_weights())})
        e = recent[0]; d = load(e['path']); x = {k: d[k][:128] for k in INPUTS}
        err = float(np.max(np.abs(Weights(path).predict(x) - model(x, training=False).numpy())))
        if err > 1e-5:
            raise ValueError('Deployment export mismatch')
        return err

    started = time.monotonic()
    initial = evaluate(); best = initial['score']; selected = initial; best_epoch = 0
    save_weights(a.out / 'best.npz'); best_checkpoint = best_manager.save(checkpoint_number=0)
    history = []
    print(json.dumps(dict(event='initial', parameters=model.count_params(), parent_optimizer_steps=parent_iterations, metrics=initial)), flush=True)
    for epoch in range(1, a.epochs + 1):
        epoch_start = time.monotonic(); rng = np.random.default_rng(2026110914 + epoch)
        tf.keras.utils.set_random_seed(2026110914 + epoch)
        for i, ei in enumerate(rng.permutation(len(train))):
            e = train[ei]; d = load(e['path']); order = rng.permutation(len(d['kind']))
            for at in range(0, len(order), 2048):
                ix = order[at:at+2048]
                w = np.array([coeff[e['source'], str(g)] for g in d['split_group'][ix]], np.float32)
                step(*batch(d, ix), w)
            if (i+1) % 75 == 0:
                print(json.dumps(dict(event='progress', epoch=epoch, shards=i+1, total_shards=len(train))), flush=True)
        val = evaluate()
        if val['score'] < best:
            best, best_epoch, selected = val['score'], epoch, val
            save_weights(a.out / 'best.npz'); best_checkpoint = best_manager.save(checkpoint_number=epoch)
        last_checkpoint = manager.save(checkpoint_number=epoch)
        row = dict(epoch=epoch, seconds=time.monotonic()-epoch_start, metrics=val)
        history.append(row)
        atomic_json(a.out / 'state.json', dict(epoch=epoch, best_epoch=best_epoch, selected_checkpoint=best_checkpoint,
                    latest_checkpoint=last_checkpoint, history=history))
        print(json.dumps(dict(event='epoch', **row)), flush=True)
    result = dict(complete=True, promoted=False, best_epoch=best_epoch, initial=initial, selected=selected,
        parameters=model.count_params(), parent_optimizer_steps=parent_iterations,
        optimizer_steps=int(optimizer.iterations.numpy()), training_positions=nrows,
        training_card_observations=sum(tc.values()), epochs=a.epochs,
        training_families=len(train_groups), recent_families=len(recent_groups),
        seconds=time.monotonic()-started, selected_sha256=sha(a.out/'best.npz'),
        parent_sha256=sha(a.parent), selected_checkpoint=best_checkpoint, latest_checkpoint=last_checkpoint,
        selection_data_only=True, playing_strength_evaluated=False, history=history)
    atomic_json(a.out / 'result.json', result)
    print(json.dumps(dict(event='complete', **result)), flush=True)


if __name__ == '__main__':
    main()
