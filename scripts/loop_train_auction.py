#!/usr/bin/env python3
"""Reference loop adapter: warm-start the existing auction-only belief network.

This is NOT the pending auction+play policy experiment. A finalized v2 using a
policy should supply its own trainer via the same request/result contract.
Requires NumPy and TensorFlow in the training interpreter, not in play workers.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha, verify_bot
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest, split_for
from bridge_harness.core import Board


def prepare_shards(request, out):
    import numpy as np
    from bridge_harness.auction_belief import encode_auction
    dataset = Path(request['dataset'])
    if sha(dataset) != request['dataset_sha256']: raise ValueError('Dataset changed')
    ds = read(dataset)
    if ds['parent'] != request['parent_identity']: raise ValueError('Wrong behavior parent')
    paths = {'train': [], 'validation': []}; seen = set()
    for i, shard in enumerate(ds['shards']):
        root = Path(shard['path'])
        if sha(root / 'shard.json') != shard['sha256']: raise ValueError('Shard manifest changed')
        m = read(root / 'shard.json')
        rows = {s:[] for s in paths}
        for name, expected in m['episodes'].items():
            file = root / 'episodes' / name
            if sha(file) != expected: raise ValueError('Episode changed')
            record = read(file); b = Board.from_dict(record['board'])
            did = digest(b.hands)
            if did in seen: raise ValueError('Repeated training deal')
            seen.add(did)
            split = split_for(b)
            if split not in rows: continue  # Internal test split remains unused.
            truth = np.empty(52, np.int32)
            for s, h in enumerate(b.hands): truth[list(h)] = s
            for observer in range(4):
                x, support = encode_auction(b.hands[observer], observer, b.dealer, b.vulnerability, b.auction)
                y = (truth-observer) % 4
                rows[split].append((x,y,y != 0,support))
        for split, examples in rows.items():
            if not examples: continue
            arrays = {k:np.stack([r[0][k] for r in examples]) for k in examples[0][0]}
            arrays.update(y=np.stack([r[1] for r in examples]), mask=np.stack([r[2] for r in examples]),
                          support=np.stack([r[3] for r in examples]))
            path = out / f'{split}-{i}.npz'
            np.savez_compressed(path, **arrays); paths[split].append(path)
    if len(seen) != ds['independent_deals'] or not all(paths.values()):
        raise ValueError('Dataset incomplete or no train/validation examples')
    return paths


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request', type=Path, required=True)
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--patience', type=int, default=4)
    p.add_argument('--batch-size', type=int, default=1024)
    p.add_argument('--threads', type=int, default=4)
    a = p.parse_args()
    if min(a.epochs, a.patience, a.batch_size, a.threads) < 1: raise ValueError('Positive settings required')
    req = read(a.request); parent = verify_bot(req['parent_manifest'])
    if parent['spec']['factory'] not in ('bridge_harness.loop_registry:auction_pimc','bridge_harness.combined_player:CombinedPlayer'):
        raise ValueError('Unsupported parent belief factory')
    if parent['identity'] != req['parent_identity']: raise ValueError('Parent changed')
    output = Path(req['output']); work = output.parent / 'auction-training'; work.mkdir(exist_ok=True)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
    import numpy as np
    import tensorflow as tf
    from bridge_harness.auction_belief import make_model
    from bridge_harness.belief_model import masked_loss
    tf.config.threading.set_intra_op_parallelism_threads(a.threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(req['seed']); tf.config.experimental.enable_op_determinism()
    paths = prepare_shards(req, work)
    def load(path):
        with np.load(path, allow_pickle=False) as z: return {k:z[k] for k in z.files}
    first = load(paths['train'][0])
    model = make_model(first['state'].shape[1])
    weight_argument='belief' if parent['spec']['factory'].endswith(':CombinedPlayer') else 'weights'
    weight_key = parent['spec']['kwargs'][weight_argument].removeprefix('$artifact:')
    weights = Path(req['parent_manifest']).parent / parent['spec']['artifacts'][weight_key]['file']
    with np.load(weights, allow_pickle=False) as z: model.set_weights([z[f'w{i}'] for i in range(8)])
    optimizer = tf.keras.optimizers.AdamW(.001, weight_decay=.0001, clipnorm=1.)
    rng = np.random.default_rng(req['seed']); inputs = ('state','calls','seats')
    @tf.function(reduce_retracing=True)
    def step(x,y,m,s):
        with tf.GradientTape() as tape:
            num, den = masked_loss(model(x, training=True),y,m,s)
            loss = num / tf.maximum(den,1.)
        optimizer.apply_gradients(zip(tape.gradient(loss,model.trainable_variables),model.trainable_variables))
        return num,den
    def evaluate():
        total = np.zeros(2)
        for path in paths['validation']:
            d=load(path)
            for start in range(0,len(d['y']),a.batch_size):
                ix=slice(start,start+a.batch_size)
                num,den=masked_loss(model({k:d[k][ix] for k in inputs},training=False),
                                   d['y'][ix],d['mask'][ix].astype(np.float32),d['support'][ix])
                total += [float(num),float(den)]
        return float(total[0]/total[1])
    best = evaluate(); initial = best; best_epoch = 0; stale = 0
    selected = work/'best.npz'
    def save_selected(): np.savez_compressed(selected, **{f'w{i}':v for i,v in enumerate(model.get_weights())})
    save_selected()  # Parent/epoch zero is a real selectable checkpoint.
    # Interruption restarts this deterministic fit; completed collection/arena work is preserved.
    history=[]
    for epoch in range(1,a.epochs+1):
        for i in rng.permutation(len(paths['train'])):
            d=load(paths['train'][i]); order=rng.permutation(len(d['y']))
            for start in range(0,len(order),a.batch_size):
                ix=order[start:start+a.batch_size]
                step({k:d[k][ix] for k in inputs},d['y'][ix],d['mask'][ix].astype(np.float32),d['support'][ix])
        val=evaluate(); history.append(dict(epoch=epoch,validation_nll=val))
        if val < best-1e-5: best=val; best_epoch=epoch; stale=0; save_selected()
        else: stale+=1
        atomic_json(work/'history.json',history)
        print(json.dumps(history[-1]),flush=True)
        if stale>=a.patience: break
    spec = {k:v for k,v in parent['spec'].items() if k not in ('source_sha256','factory_sha256','training')}
    spec['artifacts'] = {k:str(Path(req['parent_manifest']).parent/v['file']) for k,v in parent['spec']['artifacts'].items()}
    # Preserve byte identity when validation selects the parent; avoid an arena
    # run caused only by different ZIP metadata in an identical NumPy export.
    spec['artifacts'][weight_key]=str(selected if best_epoch else weights)
    provenance=dict(dataset_sha256=req['dataset_sha256'],parent_identity=req['parent_identity'],seed=req['seed'],
                    selection_split='validation',test_access=False,best_epoch=best_epoch,
                    parent_validation_nll=initial,best_validation_nll=best,
                    learning='warm-start auction-only belief; no policy training',tensorflow=tf.__version__)
    atomic_json(output,dict(bot=spec,training=provenance))


if __name__=='__main__': main()
