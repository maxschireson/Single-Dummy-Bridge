#!/usr/bin/env python3
"""Several nets on the same rows, with paired differences.

  TRAIN_DEALS=v0:3355,v1:5240 python scripts/gen7_compare_nets.py DATA SPLIT SOURCE_SET NAME=POLICY [NAME=POLICY ...]

For each net: tricks given up by its most probable card (Gen 6's estimates), exact card, an equal-best card in its
top 3, and cards kept to probability 0.98 and 0.90. For each net after the first: the step from the net before it,
as a difference and as a ratio of tricks given up, with 95% intervals from 2,000 bootstrap draws of deals.
"""
import json
import sys

import numpy as np

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.gen7_net import INPUTS, forward, log_softmax

data, split, source = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
nets = [x.split('=', 1) for x in sys.argv[4:]]
z = np.load(data)
mask = (z['deal_split'][z['deal']] == split) & ((z['source_set'] == source) if 'source_set' in z.files else source == 0)
rows = np.flatnonzero(mask)
D = {k: z[k][rows] for k in INPUTS}
gap = z['gap'][rows].astype(np.float32)
chosen = z['meta'][rows][:, 0]
deal = z['deal'][rows]
legal = D['legal']
n, r = len(rows), np.arange(len(rows))
best = legal & (gap <= 1e-9)
deals, inverse = np.unique(deal, return_inverse=True)
per = {}
out = {}
for name, path in nets:
    with np.load(path) as f:
        params = {k: f[k] for k in f.files}
    lp = np.concatenate([log_softmax(forward(params, {k: v[i:i + 4096] for k, v in D.items()})['policy']) for i in range(0, n, 4096)])
    lp = np.where(legal, lp, -1e9)
    order = np.argsort(-lp, axis=1)
    top1 = order[:, 0]
    regret = gap[r, top1]
    rank = np.empty_like(order)
    np.put_along_axis(rank, order, np.arange(52)[None, :].repeat(n, 0), axis=1)
    p = np.exp(lp)
    cum = np.cumsum(np.take_along_axis(p, order, 1), 1)
    kept = {t: np.minimum((cum < t).sum(1) + 1, legal.sum(1)).mean() for t in (.98, .9)}
    per[name] = np.bincount(inverse, regret, len(deals))
    out[name] = dict(gives_up=float(regret.mean()), exact=float((top1 == chosen).mean()), top3=float(((rank < 3) & best).any(1).mean()),
                     kept98=float(kept[.98]), kept90=float(kept[.9]), nll=float(-lp[r, chosen].mean()))
counts = np.bincount(inverse, minlength=len(deals))
rng = np.random.default_rng(0)
draws = rng.integers(0, len(deals), (2000, len(deals)))
print(f"{n} decisions, {len(deals)} deals")
names = [x[0] for x in nets]
for i, name in enumerate(names):
    o = out[name]
    line = f"{name:12s} gives up {o['gives_up']:.4f} | exact {o['exact']:.3f} | top 3 {o['top3']:.3f} | kept 0.98 {o['kept98']:.2f} 0.90 {o['kept90']:.2f} | log-loss {o['nll']:.4f}"
    if i:
        prev = names[i - 1]
        d = (per[name] - per[prev]).sum() / n
        boot_d = (per[name][draws] - per[prev][draws]).sum(1) / counts[draws].sum(1)
        ratio = per[name].sum() / per[prev].sum()
        boot_r = per[name][draws].sum(1) / per[prev][draws].sum(1)
        line += (f" || from {prev}: {d:+.4f} [{np.percentile(boot_d, 2.5):+.4f}, {np.percentile(boot_d, 97.5):+.4f}], "
                 f"cut {1 - ratio:.1%} [{1 - np.percentile(boot_r, 97.5):.1%}, {1 - np.percentile(boot_r, 2.5):.1%}]")
    print(line)


# where the steps came from: tricks given up by phase, and each step as a cut and as an exponent of training deals
ply = z['meta'][rows][:, 3]
phase = np.where(ply == 0, 0, np.where(ply // 4 + 1 <= 2, 1, np.where(ply // 4 + 1 <= 6, 2, 3)))
names_ph = ('lead', 'tricks 1-2', 'tricks 3-6', 'tricks 7-13')
deals_of = {x.split(':')[0]: float(x.split(':')[1]) for x in __import__('os').environ.get('TRAIN_DEALS', '').split(',') if x}
regrets = {}
for name, path in nets:
    with np.load(path) as f:
        params = {k: f[k] for k in f.files}
    lp = np.concatenate([log_softmax(forward(params, {k: v[i:i + 4096] for k, v in D.items()})['policy']) for i in range(0, n, 4096)])
    regrets[name] = gap[r, np.argmax(np.where(legal, lp, -1e9), axis=1)]
print()
for k, ph in enumerate(names_ph):
    m = phase == k
    print(f"{ph:12s} {m.sum():6d} decisions ({m.mean():.1%}) | " + ' | '.join(f"{name} {regrets[name][m].mean():.4f}" for name in names)
          + ' | share of v-last total ' + f"{regrets[names[-1]][m].sum() / regrets[names[-1]].sum():.1%}")
sums = {name: np.stack([np.bincount(inverse, np.where(phase == k, regrets[name], 0.), len(deals)) for k in range(4)] + [per[name]]) for name in names}
print()
for i in range(1, len(names)):
    a_, b_ = names[i - 1], names[i]
    for k, ph in enumerate((*names_ph, 'all')):
        ratio = sums[b_][k].sum() / sums[a_][k].sum()
        boot = sums[b_][k][draws].sum(1) / sums[a_][k][draws].sum(1)
        extra = ''
        if a_ in deals_of and b_ in deals_of:
            e = np.log(ratio) / np.log(deals_of[b_] / deals_of[a_])
            eb = np.log(boot) / np.log(deals_of[b_] / deals_of[a_])
            extra = f" | exponent {e:+.2f} [{np.percentile(eb, 2.5):+.2f}, {np.percentile(eb, 97.5):+.2f}]"
        print(f"{a_} to {b_} {ph:12s} cut {1 - ratio:6.1%} [{1 - np.percentile(boot, 97.5):6.1%}, {1 - np.percentile(boot, 2.5):6.1%}]{extra}")
if len(names) >= 3 and all(x in deals_of for x in names[-3:]):
    x, y, w = names[-3], names[-2], names[-1]
    e1 = np.log(sums[y][4][draws].sum(1) / sums[x][4][draws].sum(1)) / np.log(deals_of[y] / deals_of[x])
    e2 = np.log(sums[w][4][draws].sum(1) / sums[y][4][draws].sum(1)) / np.log(deals_of[w] / deals_of[y])
    d = e2 - e1
    print(f"\nexponent {y} to {w} minus {x} to {y}: {np.median(d):+.2f} [{np.percentile(d, 2.5):+.2f}, {np.percentile(d, 97.5):+.2f}]; share of draws with a flatter second step {np.mean(d > 0):.3f}")
