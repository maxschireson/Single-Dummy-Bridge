#!/usr/bin/env python3
"""Policy head against gap head as a ranking of the cards: python scripts/gen7_head_eval.py DATA SPLIT SOURCE_SET NAME=POLICY ..."""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.gen7_net import forward, log_softmax, INPUTS
data, split, source = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
z = np.load(data)
mask = (z['deal_split'][z['deal']] == split) & ((z['source_set'] == source) if 'source_set' in z.files else True)
rows = np.flatnonzero(mask)
D = {k: z[k][rows] for k in INPUTS}
gap = z['gap'][rows].astype(np.float32); meta = z['meta'][rows]; legal = D['legal']; n = len(rows); r = np.arange(n)
deal = z['deal'][rows]; deals, inv = np.unique(deal, return_inverse=True)
ply = meta[:, 3]; stage = np.where(ply == 0, 0, np.where(ply < 8, 1, np.where(ply < 24, 2, 3)))
best = legal & (gap <= 1e-9)
rng = np.random.default_rng(0); draws = [rng.integers(0, len(deals), len(deals)) for _ in range(1000)]
def ci(x, y=None):                                       # mean of x (or relative cut of x against y), bootstrap over deals
    sx = np.bincount(inv, x, len(deals)); c = np.bincount(inv, minlength=len(deals)).astype(float)
    if y is None:
        return x.mean()
    sy = np.bincount(inv, y, len(deals))
    b = [1 - sx[d].sum() / sy[d].sum() for d in draws]
    return 1 - x.sum() / y.sum(), np.percentile(b, 2.5), np.percentile(b, 97.5)
for spec in sys.argv[4:]:
    name, path = spec.split('=')
    with np.load(path) as f: params = {k: f[k] for k in f.files}
    outs = [forward(params, {k: v[i:i + 4096] for k, v in D.items()}) for i in range(0, n, 4096)]
    lp = np.concatenate([log_softmax(o['policy']) for o in outs]); gh = np.concatenate([o['gap'] for o in outs])
    print(f"== {name}: {n} decisions, {len(deals)} deals")
    base = None
    for label, score in (('policy head', lp), ('gap head', -gh), ('policy - 1 x gap', lp - 1 * gh), ('policy - 3 x gap', lp - 3 * gh), ('policy - 10 x gap', lp - 10 * gh)):
        s = np.where(legal, score, -1e9)
        order = np.argsort(-s, axis=1); rank = np.empty_like(order); np.put_along_axis(rank, order, np.arange(52)[None, :].repeat(n, 0), axis=1)
        given = gap[r, order[:, 0]]
        cover = [((rank < k) & best).any(1).mean() for k in (1, 2, 3)]
        by = [given[stage == s_].mean() for s_ in range(4)]
        line = f"  {label:18s} gives up {given.mean():.4f} | best card first {cover[0]:.3f}, in top 2 {cover[1]:.3f}, top 3 {cover[2]:.3f} | lead {by[0]:.3f}, t1-2 {by[1]:.3f}, t3-6 {by[2]:.3f}, t7-13 {by[3]:.3f}"
        if base is None: base = given
        else:
            c = ci(given, base); line += f" | cut vs policy head {100 * c[0]:.1f}% [{100 * c[1]:.1f}, {100 * c[2]:.1f}]"
        print(line)
    # the tree's reply rule: cards until probabilities add to 0.9, at most 2
    p = np.exp(np.where(legal, lp, -1e9)); order = np.argsort(-p, axis=1); cum = np.cumsum(np.take_along_axis(p, order, 1), 1)
    rank = np.empty_like(order); np.put_along_axis(rank, order, np.arange(52)[None, :].repeat(n, 0), axis=1)
    k = np.minimum(np.minimum((cum < .9).sum(1) + 1, 2), legal.sum(1)); keep = (rank < k[:, None]) & legal
    print(f"  mass 0.9, at most 2 cards: kept {k.mean():.2f}, an equal-best card kept {(keep & best).any(1).mean():.4f}, Gen 6's card kept {keep[r, meta[:, 0]].mean():.4f}")
