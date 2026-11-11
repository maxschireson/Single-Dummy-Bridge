#!/usr/bin/env python3
"""Sweep of the tree stage's two settings on gap-fork pairs (rows written by scripts/gen7_bench.py).

A pair is (A = Gen 6's card, B = another card), both played out by the same bots. With margin m and trust t
the system plays B when Gen 6's gap for B <= m and gap + t x (tree - plain search on the tree's layouts) < 0.
Its gain over Gen 6 on that pair is -(realized cost of B). Pairs are weighted by 1 / propensity and divided by
the sides read, so every figure is per side per table (tricks, IMPs, switches).

Printed: the grid with errors clustered by deal; the grid against the best setting in sample; a held-out pick
(settings chosen on half the deals, scored on the other half, many random halves); the regression of realized
cost on Gen 6's gap and the correction, whose ratio is the trust the data supports. Several ROWS:KEY are pooled.
--other KEY gives, per setting, this tree minus the tree under KEY on the same pairs (one rows file).

  python scripts/gen7_sweep.py ROWS.json:TREE_KEY [ROWS2.json:TREE_KEY2 ...] [--other KEY] [--flat tree_0_plain1] [--label NAME] [--json OUT]
"""
import argparse
import json
import math

import numpy as np

MARGINS = (0.0625, 0.125, 0.1875, 0.25, 0.375, 0.5, 1.0)
TRUSTS = (0.125, 0.1875, 0.25, 0.3125, 0.375, 0.5, 0.625, 0.75, 1.0)


def load(specs, flat, other=None):
    parts, sides, deals = [], 0, 0
    for spec in specs:
        path, key = spec.rsplit(':', 1)
        d = json.load(open(path))
        rows = [r for r in d['rows'] if r.get('imps') is not None and r['band'] >= 0]
        fam = np.array([r['family'] for r in rows])
        names, inv = np.unique(fam, return_inverse=True)
        get = lambda k: np.array([r[k] for r in rows], float)
        part = dict(inv=inv + deals, w=1 / get('propensity'), f=get('final'), imps=get('imps'), est=get('estimated'), corr=get(key) - get(flat))
        if other:
            part['corr_other'] = get(other) - get(flat)
        parts.append(part)
        sides += d['settings']['tables']                   # sides played by a Gen 6 engine at the root tables read
        deals += len(names)
    s = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    s.update(sides=sides, deals=deals, n=len(s['f']))
    return s


def per_deal(s, x):
    """Per-deal sums of weighted x, scaled so that their sum is per side per table."""
    return np.bincount(s['inv'], x * s['w'], s['deals']) / s['sides']


def total(v):
    """Sum over deals with the error of a sum of independent deals."""
    n = len(v)
    return float(v.sum()), float(math.sqrt(n / max(1, n - 1) * ((v - v.mean()) ** 2).sum()))


def switch(s, m, t, corr='corr'):
    return (s['est'] <= m + 1e-9) & (s['est'] + t * s[corr] < -1e-9)


def grid(s, corr='corr'):
    out = {}
    for m in MARGINS:
        for t in TRUSTS:
            k = switch(s, m, t, corr)
            out[(m, t)] = dict(tricks=per_deal(s, np.where(k, -s['f'], 0.)), imps=per_deal(s, np.where(k, -s['imps'], 0.)), switches=per_deal(s, k.astype(float)))
    return out


def show(cell, title):
    print(f"\n{title}")
    print('  margin ' + ''.join(f'{t:>14.4f}' for t in TRUSTS))
    for m in MARGINS:
        print(f'  {m:6.4f} ' + ''.join(f'{cell(m, t):>14s}' for t in TRUSTS))


def held_out(g, deals, what='tricks', splits=400, seed=0):
    """Pick the best setting on a random half of the deals, score it on the other half; many halves."""
    rng = np.random.default_rng(seed)
    keys = list(g)
    table = np.array([g[k][what] for k in keys])                 # [settings, deals]
    got, picks = [], {}
    for _ in range(splits):
        half = rng.permutation(deals) < deals // 2
        best = int(np.argmax(table[:, half].sum(1)))
        best = best if table[best, half].sum() > 0 else -1          # nothing beats leaving Gen 6's card: tree off
        got.append(0. if best < 0 else 2 * table[best, ~half].sum())  # x2: half the deals carry half the sides
        picks[best] = picks.get(best, 0) + 1
    order = sorted(picks.items(), key=lambda kv: -kv[1])
    return float(np.mean(got)), float(np.std(got)), [(('off' if i < 0 else keys[i]), n / splits) for i, n in order[:6]]


def regression(s, weighted, boots=1000, seed=0):
    X = np.column_stack([np.ones(s['n']), s['est'], s['corr']])
    w = s['w'] if weighted else np.ones(s['n'])

    def fit(rows):
        sw = np.sqrt(w[rows])
        return np.linalg.lstsq(X[rows] * sw[:, None], s['f'][rows] * sw, rcond=None)[0]
    beta = fit(np.arange(s['n']))
    rng = np.random.default_rng(seed)
    order = np.argsort(s['inv'], kind='stable')
    bounds = np.searchsorted(s['inv'][order], np.arange(s['deals'] + 1))
    index = [order[bounds[d]:bounds[d + 1]] for d in range(s['deals'])]
    draws = np.array([fit(np.concatenate([index[d] for d in rng.integers(0, s['deals'], s['deals'])])) for _ in range(boots)])
    ratio = draws[:, 2] / draws[:, 1]
    return beta, draws.std(0), (float(beta[2] / beta[1]), float(np.percentile(ratio, 2.5)), float(np.percentile(ratio, 97.5)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('specs', nargs='+', help='ROWS.json:TREE_KEY')
    p.add_argument('--other')
    p.add_argument('--flat', default='tree_0_plain1')
    p.add_argument('--label', default='')
    p.add_argument('--json')
    a = p.parse_args()
    s = load(a.specs, a.flat, a.other)
    print(f"== {a.label or a.specs}: {s['n']} pairs, {s['deals']} deals, {s['sides']} sides; Gen 6's gap for B: "
          f"quartiles {np.percentile(s['est'], [25, 50, 75]).round(3).tolist()}; correction sd {s['corr'].std():.3f}")
    print('   other cards a side within each margin: ' + ', '.join(f"{m}: {per_deal(s, (s['est'] <= m + 1e-9).astype(float)).sum():.2f}" for m in MARGINS))
    g = grid(s)
    cell = lambda what, fmt='{:+.3f}': (lambda m, t: fmt.format(total(g[(m, t)][what])[0]) + f"+-{total(g[(m, t)][what])[1]:.3f}")
    show(cell('tricks'), 'tricks a side over Gen 6, by margin (rows) and trust (columns); +- is one standard error')
    show(cell('imps'), 'IMPs a side over Gen 6')
    show(lambda m, t: f"{total(g[(m, t)]['switches'])[0]:.2f}", 'switches a side')
    best = max(g, key=lambda k: g[k]['tricks'].sum())
    print(f"\nbest in sample: margin {best[0]}, trust {best[1]}: {total(g[best]['tricks'])[0]:+.3f} tricks a side (flattered: it was picked on these pairs)")
    show(lambda m, t: '{:+.3f}+-{:.3f}'.format(*total(g[(m, t)]['tricks'] - g[best]['tricks'])), 'each setting minus the best in sample, tricks a side (same pairs)')
    for what in ('tricks', 'imps'):
        mean, sd, picks = held_out(g, s['deals'], what)
        print(f"\nheld-out pick by {what}: {mean:+.3f} {what} a side (sd over halves {sd:.3f}); settings picked: " + ', '.join(f"{k} {share:.0%}" for k, share in picks))
    for weighted in (False, True):
        beta, se, ratio = regression(s, weighted)
        print(f"\nrealized cost of B = a + b x gap + c x correction ({'weighted to sides' if weighted else 'per sampled pair'}): "
              f"a {beta[0]:+.3f} +- {se[0]:.3f}, b {beta[1]:+.3f} +- {se[1]:.3f}, c {beta[2]:+.3f} +- {se[2]:.3f}; trust c/b {ratio[0]:.2f} [{ratio[1]:.2f}, {ratio[2]:.2f}]")
    if a.other:
        h = grid(s, 'corr_other')
        show(lambda m, t: '{:+.3f}+-{:.3f}'.format(*total(g[(m, t)]['tricks'] - h[(m, t)]['tricks'])), f'this tree minus {a.other}, tricks a side (same pairs)')
        show(lambda m, t: '{:+.2f}'.format(total(g[(m, t)]['switches'] - h[(m, t)]['switches'])[0]), f'this tree minus {a.other}, switches a side')
        print(f"correction sd: this {s['corr'].std():.3f}, other {s['corr_other'].std():.3f}")
    if a.json:
        json.dump({f'{m},{t}': dict(tricks=total(g[(m, t)]['tricks']), imps=total(g[(m, t)]['imps']), switches=total(g[(m, t)]['switches'])[0]) for m, t in g},
                  open(a.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
