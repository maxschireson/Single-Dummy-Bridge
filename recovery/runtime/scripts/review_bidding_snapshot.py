#!/usr/bin/env python3
"""Evaluate a frozen recovery snapshot on fresh development deals; never promote."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--phase', choices=['dev', 'confirm'], default='dev')
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    lock = (args.out/'worker.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    digest = hashlib.sha256(args.snapshot.read_bytes()).hexdigest()
    unpack = args.out/'snapshot'
    with zipfile.ZipFile(args.snapshot) as z:
        for name in z.namelist():
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('Unsafe archive path')
        z.extractall(unpack)
    hashes = json.loads((unpack/'SHA256.json').read_text())
    for name, expected in hashes.items():
        assert hashlib.sha256((unpack/name).read_bytes()).hexdigest() == expected, name
    state = json.loads((unpack/'run/state.json').read_text())
    manifest = json.loads((unpack/'run/manifest.json').read_text())
    cfg = manifest['config']
    # This first-attempt review has three identical B0 endpoints.
    if state['promotions'] or state['parent'] != manifest['origin']:
        raise ValueError('This review requires the initial B0 league')
    split = 'dev' if args.phase == 'dev' else 'test'
    count = 1000 if args.phase == 'dev' else 5000
    seed = cfg['seed'] + (200000000 if args.phase == 'dev' else 300000000) + state['attempt']*100003 + state['trained_pairs']
    spec = dict(snapshot_sha256=digest, trained_pairs=state['trained_pairs'],
                seed=seed, pairs=count, split=split, greedy=True,
                purpose=('Additional descriptive development screen; no promotion decision' if args.phase == 'dev' else 'Additional descriptive confirm review; no promotion decision'))
    from bridge_harness.bidding_loop import atomic_json
    if (args.out/'spec.json').exists():
        assert json.loads((args.out/'spec.json').read_text()) == spec
    else:
        atomic_json(args.out/'spec.json', spec)
    import tensorflow as tf
    import numpy as np
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(cfg['seed'])
    from bridge_harness.bidding_ppo import Policy, PPO
    from bridge_harness.bidding_env import TableCache, make_board, paired_auctions
    from bridge_harness.loop_stats import estimate
    origin = unpack/'dependencies'/Path(manifest['origin']).name
    anchor = Policy.load(origin)
    candidate = Policy.load(origin, critic=True)
    trainer = PPO(candidate, anchor, learning_rate=cfg['learning_rate'],
                  epsilon=cfg['exploration'], anchor_weight=cfg['anchor_weight'])
    prefix = unpack/'run/checkpoints'/Path(state['checkpoint']).parent.name/Path(state['checkpoint']).name
    trainer.restore(prefix)
    cache = TableCache(args.out/'review-dds.sqlite',
                       unpack/'dependencies'/Path(manifest['dds_library']).name, 1)
    rows = []
    start = time.monotonic()
    try:
        for offset in range(0, count, 128):
            dest = args.out/f'{offset:07d}.json'
            if dest.exists():
                batch = json.loads(dest.read_text())
            else:
                boards = [make_board(seed, i, split) for i in range(offset, min(count,offset+128))]
                tables = cache.get_many(boards)
                batch, _ = paired_auctions(boards, tables, candidate, [anchor]*len(boards),
                                           np.random.default_rng(seed+offset), explore=False)
                atomic_json(dest, batch)
            rows.extend(batch)
            print(json.dumps(dict(completed=len(rows), target=count)), flush=True)
        assert len({r['deal_id'] for r in rows}) == count
        values = [r['imps'] for r in rows]
        result = dict(**spec, descriptive=estimate(values), total_imps=sum(values),
                      wins=sum(x>0 for x in values), losses=sum(x<0 for x in values),
                      ties=sum(x==0 for x in values), screen_passed=float(np.mean(values))>0,
                      promotions=0, elapsed_seconds=time.monotonic()-start)
        atomic_json(args.out/'summary.json', result)
        print(json.dumps(result), flush=True)
    finally:
        cache.close()

if __name__ == '__main__':
    main()

