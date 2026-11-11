import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Hand-fit scorer: P(a hand would have made this seat's calls), a belief net in per-seat form.

The posterior over hidden hands given the auction is uniform over layouts in which every
hidden hand fits its seat's calls. This net learns "fits" from free data, so layouts can be
weighted by the product of its scores with no bidder at the table. Like the bidder, it sees
a hand as honours and suit lengths, so spot cards cannot matter.

Train: python fit.py OUT_PREFIX MINUTES VAL.npz TRAIN.npz [TRAIN.npz ...]
"""
import os
import sys
import time

import numpy as np
import autograd.numpy as anp
from autograd import grad

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen import MAX_SLOTS, POP, HON_HCP, VUL_NS, VUL_EW  # noqa: E402

D_HAND = 56 + 20 + 4 + 38 + 2
D_AUC = MAX_SLOTS * 38
EYE14 = np.eye(14, dtype=np.float32)
EYE38 = np.eye(38, dtype=np.float32)
BITS5 = np.array([[(i >> j) & 1 for j in range(5)] for i in range(32)], np.float32)


def hand_features(length, hon, own_vul, opp_vul):
    """length, hon: (n,4) ints. Returns (n, D_HAND) float32."""
    length = np.asarray(length).astype(np.int64)
    hon = np.asarray(hon).astype(np.int64)
    n = len(length)
    hcp = HON_HCP[hon].sum(axis=1)
    low = (length - POP[hon]) / 8.0
    v = np.empty((n, 2), np.float32)
    v[:, 0], v[:, 1] = own_vul, opp_vul
    return np.concatenate([EYE14[length].reshape(n, 56), BITS5[hon].reshape(n, 20), low.astype(np.float32),
                           EYE38[hcp], v], axis=1)


def auction_onehot(calls, dealer, seat):
    """calls: (n,T) int with -1 padding; dealer, seat: (n,). Seat-aligned (n, D_AUC) one-hot."""
    calls = np.asarray(calls).astype(np.int64)
    n, T = calls.shape
    d0 = (np.asarray(dealer) - np.asarray(seat)) % 4
    pos = d0[:, None] + np.arange(T)[None, :]
    oh = np.zeros((n, D_AUC + 1), np.float32)
    idx = np.where((calls >= 0) & (pos < MAX_SLOTS), pos * 38 + calls - 2, D_AUC)
    np.put_along_axis(oh, idx, 1.0, axis=1)
    return oh[:, :-1]


def init(seed=0, widths=(768, 512, 256)):
    rng = np.random.default_rng(seed)
    w = lambda i, o: (rng.standard_normal((i, o)) * np.sqrt(2.0 / i)).astype(np.float32)
    p = dict(Wh=w(D_HAND, widths[0]), Wa=(rng.standard_normal((D_AUC, widths[0])) * 0.05).astype(np.float32),
             b0=np.zeros(widths[0], np.float32))
    for k in range(1, len(widths)):
        p[f'W{k}'] = w(widths[k - 1], widths[k]); p[f'b{k}'] = np.zeros(widths[k], np.float32)
    p['Wo'] = w(widths[-1], 1) * 0.1; p['bo'] = np.zeros(1, np.float32)
    return p


def logits(p, xh, xa):
    z = anp.maximum(anp.dot(xh, p['Wh']) + anp.dot(xa, p['Wa']) + p['b0'], 0)
    k = 1
    while f'W{k}' in p:
        z = anp.maximum(anp.dot(z, p[f'W{k}']) + p[f'b{k}'], 0)
        k += 1
    return (anp.dot(z, p['Wo']) + p['bo'])[:, 0]


def loss(p, xh, xa, y):
    z = logits(p, xh, xa)
    return anp.mean(anp.logaddexp(0.0, z) - y * z)


def log_score(p, length, hon, own_vul, opp_vul, auc_row):
    """log P(fit) for many hands of one seat in one auction (NumPy). auc_row: (D_AUC,) one-hot."""
    xh = hand_features(length, hon, own_vul, opp_vul)
    z = np.maximum(xh @ p['Wh'] + (auc_row @ p['Wa'] + p['b0']), 0)
    k = 1
    while f'W{k}' in p:
        z = np.maximum(z @ p[f'W{k}'] + p[f'b{k}'], 0)
        k += 1
    z = (z @ p['Wo'] + p['bo'])[:, 0].astype(np.float64)
    return -np.logaddexp(0.0, -z)


def batch(d, ix):
    dl = d['deal'][ix]
    seat = d['seat'][ix].astype(np.int64)
    vul = d['d_vul'][dl].astype(np.int64)
    own = np.where(seat % 2 == 0, VUL_NS[vul], VUL_EW[vul])
    opp = np.where(seat % 2 == 0, VUL_EW[vul], VUL_NS[vul])
    xh = hand_features(d['length'][ix], d['hon'][ix], own, opp)
    xa = auction_onehot(d['d_calls'][dl], d['d_dealer'][dl].astype(np.int64), seat)
    return xh, xa, d['label'][ix].astype(np.float32)


def load(paths):
    parts = [dict(np.load(q)) for q in paths]
    out, offset = {}, 0
    for q in parts:
        q['deal'] = q['deal'] + offset
        offset += len(q['d_dealer'])
    for k in parts[0]:
        out[k] = np.concatenate([q[k] for q in parts])
    return out


def evaluate(p, d, n=40000):
    ix = np.arange(min(n, len(d['label'])))
    zs, ys = [], []
    for s in range(0, len(ix), 8000):
        xh, xa, y = batch(d, ix[s:s + 8000])
        zs.append(np.asarray(logits(p, xh, xa))); ys.append(y)
    z, y = np.concatenate(zs), np.concatenate(ys)
    kind = d['kind'][ix]
    bce = np.mean(np.logaddexp(0, z) - y * z)
    acc = lambda m: np.mean((z[m] > 0) == (y[m] > 0.5))
    return bce, acc(kind == 0), acc(kind == 1), acc(kind == 2), np.mean(1 / (1 + np.exp(-z[kind == 0])))


def main():
    out, minutes, val_path, train_paths = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4:]
    val, d = load([val_path]), load(train_paths)
    N = len(d['label'])
    print(f'train examples {N} from {len(d["d_dealer"])} deals; positive share {d["label"].mean():.3f}', flush=True)
    p = init(0)
    g = grad(loss)
    m = {k: np.zeros_like(v) for k, v in p.items()}
    v = {k: np.zeros_like(v) for k, v in p.items()}
    rng = np.random.default_rng(0)
    bs, lr0, lr1, step, t0, seen, next_eval, budget, done = 1024, 2e-3, 1e-4, 0, time.time(), 0, 0, minutes * 60, False
    while not done:
        order = rng.permutation(N)
        for s in range(0, N - bs + 1, bs):
            el = time.time() - t0
            if el >= budget:
                done = True
                break
            lr = lr1 + 0.5 * (lr0 - lr1) * (1 + np.cos(np.pi * el / budget))
            if step < 200:
                lr *= (step + 1) / 200
            xh, xa, y = batch(d, np.sort(order[s:s + bs]))
            gr = g(p, xh, xa, y)
            step += 1; seen += bs
            for k in p:
                gk = np.asarray(gr[k])
                m[k] = 0.9 * m[k] + 0.1 * gk
                v[k] = 0.999 * v[k] + 0.001 * gk * gk
                p[k] = (p[k] - lr * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v[k] / (1 - 0.999 ** step)) + 1e-8)).astype(np.float32)
            if el >= next_eval:
                bce, a0, a1, a2, pt = evaluate(p, val)
                print(f'{el/60:5.1f} min step {step} examples {seen} ({seen/N:.2f} passes) lr {lr:.5f}: val loss {bce:.4f}; accuracy true hands {a0:.3f}, random {a1:.3f}, near {a2:.3f}; mean score of true hands {pt:.3f}; {seen/max(el,1):.0f}/s', flush=True)
                np.savez(out + '.npz', **p)
                next_eval = el + max(60, budget / 30)
    bce, a0, a1, a2, pt = evaluate(p, val, n=len(val['label']))
    print(f'final after {step} steps, {seen} examples ({seen/N:.2f} passes): val loss {bce:.4f}; accuracy true hands {a0:.3f}, random {a1:.3f}, near {a2:.3f}; mean score of true hands {pt:.3f}', flush=True)
    np.savez(out + '.npz', **p)


if __name__ == '__main__':
    main()
