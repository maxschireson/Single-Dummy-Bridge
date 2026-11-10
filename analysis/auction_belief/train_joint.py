import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Train the joint auction belief prototype on generated auctions.

Usage: python train_joint.py OUT_PREFIX MINUTES VAL.npz TRAIN.npz [TRAIN.npz ...]
"""
import sys
import time

import numpy as np
from autograd import grad

sys.path.insert(0, HERE)
import joint  # noqa: E402


def load(paths):
    parts = [np.load(p) for p in paths]
    return {k: np.concatenate([q[k] for q in parts]) for k in parts[0].files}


def evaluate(p, d, n=10000, batch=2000):
    tot, parts = [], []
    for s in range(0, min(n, len(d['n'])), batch):
        b = joint.prepare(d, np.arange(s, min(s + batch, len(d['n']))))
        v, (l1, l2, lg) = joint.nats(p, b)
        tot.append(np.asarray(v)); parts.append([np.asarray(l1).mean(), np.asarray(l2).mean(), np.asarray(lg).mean()])
    tot = np.concatenate(tot)
    return tot.mean(), tot.std(ddof=1) / np.sqrt(len(tot)), np.mean(parts, axis=0)


def main():
    out, minutes, val_path, train_paths = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4:]
    val = load([val_path])
    d = load(train_paths)
    N = len(d['n'])
    print(f'train rows {N}, val rows {len(val["n"])}', flush=True)
    p = joint.init(0)
    g = grad(joint.loss)
    m = {k: np.zeros_like(v) for k, v in p.items()}
    v = {k: np.zeros_like(v) for k, v in p.items()}
    rng = np.random.default_rng(0)
    batch, lr0, lr1, step, t0 = 512, 2e-3, 1e-4, 0, time.time()
    budget = minutes * 60
    run = None
    seen = 0
    next_eval = 0
    done = False
    while not done:
        order = rng.permutation(N)
        for s in range(0, N - batch + 1, batch):
            el = time.time() - t0
            if el >= budget:
                done = True
                break
            frac = el / budget
            lr = lr1 + 0.5 * (lr0 - lr1) * (1 + np.cos(np.pi * frac))
            if step < 200:
                lr *= (step + 1) / 200
            b = joint.prepare(d, np.sort(order[s:s + batch]))
            gr = g(p, b)
            step += 1
            seen += batch
            for k in p:
                gk = np.asarray(gr[k])
                m[k] = 0.9 * m[k] + 0.1 * gk
                v[k] = 0.999 * v[k] + 0.001 * gk * gk
                p[k] = (p[k] - lr * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v[k] / (1 - 0.999 ** step)) + 1e-8)).astype(np.float32)
            if el >= next_eval:
                mean, se, parts = evaluate(p, val)
                print(f'{el/60:5.1f} min step {step} rows {seen} ({seen/N:.2f} epochs) lr {lr:.5f}: val nats over uniform {mean:.3f} +- {se:.3f} '
                      f'(shape D {parts[0]:.3f}, shape M {parts[1]:.3f}, honours {parts[2]:.3f}) {seen/max(el,1):.0f} rows/s', flush=True)
                np.savez(out + '.npz', **p)
                next_eval = el + max(60, budget / 30)
    mean, se, parts = evaluate(p, val, n=len(val['n']))
    print(f'final after {step} steps, {seen} rows ({seen/N:.2f} epochs): val nats over uniform {mean:.3f} +- {se:.3f} '
          f'(log-prob parts: shape D {parts[0]:.3f}, shape M {parts[1]:.3f}, honours {parts[2]:.3f})', flush=True)
    np.savez(out + '.npz', **p)


if __name__ == '__main__':
    main()
