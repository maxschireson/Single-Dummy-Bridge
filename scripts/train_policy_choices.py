"""Reward correctly ranked audited moves; select on validation, test once."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
            'TF_NUM_INTRAOP_THREADS', 'TF_NUM_INTEROP_THREADS'):
    os.environ[key] = '1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import numpy as np
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.policy_choice_data import scores, weights
from bridge_harness.auction_policy import restore_parent, export_weights
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json

INPUTS = ('state', 'actions', 'calls', 'seats')


def family_summary(values, groups):
    values = np.asarray(values, float)
    if not len(values):
        return dict(rows=0, families=0, mean=None, se=None, ci95=None)
    _, ids = np.unique(groups, return_inverse=True)
    means = np.bincount(ids, weights=values) / np.bincount(ids)
    n = len(means)
    mean = float(means.mean())
    se = float(means.std(ddof=1) / np.sqrt(n)) if n > 1 else None
    half = float(t.ppf(.975, n-1)) * se if se is not None else None
    return dict(rows=len(values), families=n, mean=mean, se=se,
                ci95=[mean-half, mean+half] if half is not None else None)


def choose(contrast):
    contrast = np.asarray(contrast)
    return np.where(contrast > 1e-7, 1., np.where(contrast < -1e-7, 0., .5))


def metrics(data, contrast, mask):
    y = data['y'][mask]
    groups = data['group'][mask]
    p = choose(contrast[mask])
    decisive = y != 0
    correct = np.where(y > 0, p, 1-p)
    return dict(
        gain_over_recorded_reference=family_summary(p*y, groups),
        regret_to_better_recorded_move=family_summary(np.maximum(y, 0)-p*y, groups),
        decisive_accuracy=family_summary(correct[decisive], groups[decisive]),
        fraction_selecting_logged_candidate=float(p.mean()) if len(p) else None,
        decisive_rows=int(decisive.sum()), tied_outcome_rows=int((~decisive).sum()))


def load_split(folder, manifest, split):
    arrays = []
    for entry in manifest['shards']:
        if entry['split'] != split:
            continue
        path = folder / entry['file']
        if sha(path) != entry['sha256']:
            raise ValueError('Training shard changed')
        with np.load(path, allow_pickle=False) as z:
            arrays.append({key: z[key] for key in z.files})
    if not arrays:
        raise ValueError('Missing split: ' + split)
    return {key: np.concatenate([a[key] for a in arrays]) for key in arrays[0]}


def pair_model(tf, data):
    from bridge_harness.auction_belief import CALLS, MAX_CALLS
    k = tf.keras
    state = k.Input((data['state'].shape[1],), name='state')
    actions = k.Input((2, data['actions'].shape[-1]), name='actions')
    calls = k.Input((MAX_CALLS,), dtype='int32', name='calls')
    seats = k.Input((MAX_CALLS,), dtype='int32', name='seats')
    c = k.layers.Flatten()(k.layers.Embedding(len(CALLS)+1, 4, name='call_embedding')(calls))
    s = k.layers.Flatten()(k.layers.Embedding(5, 2, name='seat_embedding')(seats))
    h = k.layers.Dense(32, activation='relu', name='state_hidden')(k.layers.Concatenate()([state, c, s]))
    value = k.layers.Dense(1, name='state_value')(h)
    x = k.layers.Concatenate()([actions, k.layers.RepeatVector(2)(h)])
    x = k.layers.Dense(16, activation='relu', name='action_hidden')(x)
    x = k.layers.Dense(8, activation='relu', name='action_hidden_2')(x)
    score = k.layers.Dense(1, name='action_score')(x)
    return k.Model(dict(state=state, actions=actions, calls=calls, seats=seats), dict(value=value, score=score))


def train(data_dir, out, parent, epochs=12):
    if out.exists():
        raise ValueError('Use a new fit directory')
    out.mkdir(parents=True)
    ds = json.loads((data_dir / 'dataset.json').read_text())
    if ds['schema'] != 'paired-policy-choices-v1' or not ds['validated']:
        raise ValueError('Validated paired comparisons required')
    config = dict(dataset_sha256=sha(data_dir/'dataset.json'), parent_sha256=sha(parent),
                  seed=2026110919, epochs=epochs, learning_rate=1e-4, weight_decay=1e-4,
                  loss='Equal-family, absolute-IMP-weighted pairwise logistic loss; zero-IMP contrasts carry no preference label',
                  initialization='Gen3 action network and its PIMC q coefficient=1, preserving its initial rankings',
                  selection='Minimum validation-family mean regret on depth-zero current-Gen4-policy audits; epoch zero eligible',
                  test_rule='Load untouched test only after best epoch is fixed; no adaptation based on test results',
                  deployment='Offline rank scores, not calibrated IMP predictions; not promoted into any arena',
                  source_sha256=sha(Path(__file__)))
    atomic_json(out/'config.json', config)
    training = load_split(data_dir, ds, 'train')
    validation = load_split(data_dir, ds, 'validation')
    if set(training['group']) & set(validation['group']):
        raise ValueError('Family leakage')
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(config['seed'])
    tf.config.experimental.enable_op_determinism()
    model = pair_model(tf, training)
    restore_parent(model, parent)
    q_scale = tf.Variable(1., dtype=tf.float32, trainable=True, name='rank_q_scale')
    variables = [v for v in model.trainable_variables if 'state_value' not in v.path] + [q_scale]
    optimizer = tf.keras.optimizers.AdamW(config['learning_rate'], weight_decay=config['weight_decay'], clipnorm=1.)
    optimizer.build(variables)
    checkpoints = tf.train.Checkpoint(model=model, q_scale=q_scale, optimizer=optimizer)
    manager = tf.train.CheckpointManager(checkpoints, str(out/'resume'), max_to_keep=1)

    @tf.function(reduce_retracing=True)
    def prediction(batch):
        value = model({k: batch[k] for k in INPUTS}, training=False)['score'][..., 0]
        return value[:, 0]-value[:, 1]+q_scale*(batch['q'][:, 0]-batch['q'][:, 1])

    @tf.function(reduce_retracing=True)
    def step(batch):
        with tf.GradientTape() as tape:
            value = model({k: batch[k] for k in INPUTS}, training=True)['score'][..., 0]
            diff = value[:, 0]-value[:, 1]+q_scale*(batch['q'][:, 0]-batch['q'][:, 1])
            sign = tf.sign(batch['y'])
            reward_weight = batch['weight']*tf.abs(batch['y'])
            loss = tf.reduce_sum(reward_weight*tf.nn.softplus(-sign*diff))/tf.maximum(tf.reduce_sum(reward_weight), 1e-8)
        gradients = tape.gradient(loss, variables)
        optimizer.apply_gradients([(g, v) for g, v in zip(gradients, variables) if g is not None])
        return loss

    def predict(data):
        chunks = []
        for start in range(0, len(data['y']), 512):
            batch = {key: data[key][start:start+512] for key in (*INPUTS, 'q')}
            chunks.append(prediction(batch).numpy())
        return np.concatenate(chunks)

    def export(path):
        export_weights(model, path)
        w = weights(path)
        np.savez_compressed(path, **w, rank_neural=np.int8(1), rank_q_scale=np.float32(q_scale.numpy()))

    mask = (validation['depth'] == 0) & validation['current_policy'].astype(bool)
    if len(set(validation['group'][mask])) < 30:
        raise ValueError('Insufficient validation families')
    initial_predictions = predict(validation)
    initial_error = float(np.max(np.abs(initial_predictions-validation['gen3_contrast'])))
    if initial_error > 1e-4:
        raise ValueError('Gen3 initialization did not preserve rankings')
    initial = metrics(validation, initial_predictions, mask)
    best = initial['regret_to_better_recorded_move']['mean']
    best_epoch = 0
    export(out/'best.npz')
    history = [dict(epoch=0, validation=initial, q_scale=float(q_scale.numpy()))]
    started = time.time()
    for epoch in range(1, epochs+1):
        rng = np.random.default_rng(config['seed']+epoch)
        # Keep all family weights, but skip zero-reward examples whose gradient is zero.
        order = rng.permutation(np.flatnonzero(training['y'] != 0))
        losses = []
        for start in range(0, len(order), 512):
            ix = order[start:start+512]
            batch = {k: training[k][ix] for k in (*INPUTS, 'q', 'y', 'weight')}
            losses.append(float(step(batch)))
        result = metrics(validation, predict(validation), mask)
        objective = result['regret_to_better_recorded_move']['mean']
        if objective < best:
            best = objective
            best_epoch = epoch
            export(out/'best.npz')
        entry = dict(epoch=epoch, training_loss=float(np.mean(losses)), validation=result,
                     q_scale=float(q_scale.numpy()), seconds=time.time()-started)
        history.append(entry)
        manager.save(checkpoint_number=epoch)
        atomic_json(out/'training.json', dict(best_epoch=best_epoch, best_validation_regret=best, history=history))
        print(json.dumps(entry), flush=True)
    export(out/'last.npz')
    selected = weights(out/'best.npz')
    last = weights(out/'last.npz')
    last_values = scores(last, validation, 'rank')
    numpy_error = float(np.max(np.abs(last_values[:, 0]-last_values[:, 1]-predict(validation))))
    if numpy_error > 1e-4:
        raise ValueError('NumPy deployment scorer differs from TensorFlow')
    # Test is intentionally first loaded after selection is complete.
    test = load_split(data_dir, ds, 'test')
    if set(test['group']) & (set(training['group']) | set(validation['group'])):
        raise ValueError('Test family leakage')
    selected_values = scores(selected, test, 'rank')
    test['new_contrast'] = selected_values[:, 0]-selected_values[:, 1]
    evidence = {}
    for name, subset in [('root', (test['depth'] == 0) & test['current_policy'].astype(bool)),
                         ('all_depths', test['current_policy'].astype(bool))]:
        output = {label: metrics(test, test[label+'_contrast'], subset) for label in ('gen3', 'gen4', 'new')}
        for old in ('gen3', 'gen4'):
            delta = (choose(test['new_contrast'][subset])-choose(test[old+'_contrast'][subset]))*test['y'][subset]
            output['new_minus_'+old] = family_summary(delta, test['group'][subset])
        output['logged_gen4_minus_reference'] = family_summary(test['y'][subset], test['group'][subset])
        evidence[name] = output
    # Baseline diagnosis uses all fresh source families; no fitting uses test labels.
    diagnosis = {}
    for name, subset in [('root', lambda d:(d['depth'] == 0) & d['current_policy'].astype(bool)),
                         ('all_depths', lambda d:d['current_policy'].astype(bool))]:
        y = np.concatenate([d['y'][subset(d)] for d in (training, validation, test)])
        g = np.concatenate([d['group'][subset(d)] for d in (training, validation, test)])
        pred = np.concatenate([d['gen4_contrast'][subset(d)] for d in (training, validation, test)])
        diagnosis[name] = dict(logged_gain=family_summary(y, g),
                              wins=int((y>0).sum()), ties=int((y==0).sum()), losses=int((y<0).sum()),
                              predicted_gain=family_summary(pred, g),
                              prediction_mse=family_summary((pred-y)**2, g),
                              zero_prediction_mse=family_summary(y*y, g),
                              decisive_win_rate=family_summary((y[y!=0]>0).astype(float), g[y!=0]))
    result = dict(config=config, selected_epoch=best_epoch, selected_sha256=sha(out/'best.npz'),
                  selected_validation_regret=best, initial_validation=initial,
                  initialization_max_error=initial_error, numpy_max_error=numpy_error,
                  parameters=model.count_params()+1, rows={s:len(d['y']) for s,d in
                    [('train',training),('validation',validation),('test',test)]},
                  existing_policy_diagnosis=diagnosis, held_out_test=evidence,
                  elapsed_training_seconds=time.time()-started,
                  promoted=False, whole_game_strength_tested=False,
                  limitations=['Audited two-action comparisons only; unrolled alternatives have no labels.',
                               'Continuation policies are frozen; one-move advantages are not whole-game IMP gains.',
                               'Compute-budget admission limits the population; no known final inclusion propensity.',
                               'Intervals cluster all descendant positions by deal family and are descriptive.'])
    atomic_json(out/'result.json', result)
    np.savez_compressed(out/'test-predictions.npz', **{k:test[k] for k in
                        ('group','source','pair','index','depth','current_policy','y','gen3_contrast','gen4_contrast','new_contrast')})
    print(json.dumps(dict(selected_epoch=best_epoch, held_out_root=evidence['root'], diagnosis=diagnosis['root'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=12)
    args = parser.parse_args()
    train(args.data, args.out, args.parent, args.epochs)
