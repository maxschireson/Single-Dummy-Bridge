#!/usr/bin/env python3
"""Read rows written by scripts/plan_bench.py.

  python scripts/plan_report.py rows.json [more.json ...] [--bands 0,1,2] [--tricks 3,4,5,6]

For every simulated player, per sampled pair, with deals as the unit of the errors:

  share      c in: realized cost of B = k + b x pimc + c x (sim - pimc). The correction is what the playout changes
             in the gap between A and B on the same layouts; c is how much of it shows up in real results.
  true       the same on the real deal alone: realized = k + b x true_dd + c x (true_sim - true_dd). It measures the
             simulator with the layout known, apart from the belief.
  gain       tricks a pair gained over Gen 6 by playing B when pimc + trust x correction < 0, for several trusts
  fit        how close the playout of A on the real deal is to the tricks the table really took
  layout luck  the part of the correction's variance that comes from which layouts happened to be played out
             (the spread of the correction across a pair's layouts, over their number). It dilutes the share:
             "share without it" is the share a very large number of layouts would show.
"""
import argparse
import json
import math
import sys

import numpy as np


def clustered_ols(y, X, groups):
    """OLS coefficients and cluster-robust standard errors (clusters = groups)."""
    X = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    bread = np.linalg.inv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    index = {}
    for i, g in enumerate(groups):
        index.setdefault(g, []).append(i)
    for rows in index.values():
        s = X[rows].T @ resid[rows]
        meat += np.outer(s, s)
    G = len(index)
    cov = bread @ meat @ bread * G / max(1, G - 1)
    return beta, np.sqrt(np.diag(cov))


def clustered_mean(x, groups):
    by = {}
    for v, g in zip(x, groups):
        by.setdefault(g, []).append(v)
    totals, counts = np.array([sum(v) for v in by.values()]), np.array([len(v) for v in by.values()])
    mean = totals.sum() / counts.sum()
    se = math.sqrt(((totals - mean * counts) ** 2).sum() * len(by) / max(1, len(by) - 1)) / counts.sum()
    return float(mean), float(se)


def report(rows, sims, trusts=(0.25, 0.5, 0.75, 1.0), title=''):
    f = np.array([r['final'] for r in rows], float)
    fam = [r['family'] for r in rows]
    pimc = np.array([r['pimc'] for r in rows])
    tdd = np.array([r['true_dd'] for r in rows])
    print(f"\n== {title}: {len(rows)} pairs on {len(set(fam))} deals. B really cost {f.mean():+.3f}; pimc said {pimc.mean():+.3f}; "
          f"B better {np.mean(f < 0):.3f}, worse {np.mean(f > 0):.3f}")
    b, se = clustered_ols(f, pimc[:, None], fam)
    b2, se2 = clustered_ols(f, tdd[:, None], fam)
    print(f"   realized on pimc alone: slope {b[1]:.2f} +- {se[1]:.2f}, residual sd {np.std(f - np.column_stack([np.ones(len(f)), pimc]) @ b):.3f}"
          f" | on the real deal's double dummy alone: slope {b2[1]:.2f} +- {se2[1]:.2f}, residual sd {np.std(f - np.column_stack([np.ones(len(f)), tdd]) @ b2):.3f}")
    print(f"   {'sim':16s} {'share':>14s} {'sd corr':>8s} {'true share':>14s} {'sd true':>8s} | gain a pair at trust " + '  '.join(f'{t:>13.2f}' for t in trusts) + ' | fit: mean abs miss, exact')
    for s in sims:
        v = np.array([r[s] for r in rows])
        corr = v - pimc
        b, se = clustered_ols(f, np.column_stack([pimc, corr]), fam)
        tv = np.array([r['true_' + s] for r in rows])
        tcorr = tv - tdd
        bt, set_ = clustered_ols(f, np.column_stack([tdd, tcorr]), fam)
        gains = []
        for t in trusts:
            prefers_b = pimc + t * corr < -1e-9
            base = pimc < -1e-9
            m, e = clustered_mean(np.where(prefers_b, -f, 0.) - np.where(base, -f, 0.), fam)
            gains.append(f'{m:+.4f}+-{e:.4f}')
        miss = np.array([r['true_a_' + s] - r['real_a'] for r in rows])
        # how much of the correction's spread is the luck of which layouts were played out: the layouts' own spread / their number
        noise = np.array([(r['var_' + s] if 'var_' + s in r else max(0., r['sd_' + s] ** 2 - (r[s] - r['pimc']) ** 2)) / max(1., r.get('neff_' + s, r.get('neff', r['layouts'])))
                          for r in rows])
        kept = max(0., 1 - noise.mean() / max(corr.var(), 1e-12))
        print(f"   {s:16s} {b[2]:+.3f} +- {se[2]:.3f} {corr.std():8.3f} {bt[2]:+.3f} +- {set_[2]:.3f} {tcorr.std():8.3f} | " + '  '.join(gains)
              + f' | {np.abs(miss).mean():.3f}, {np.mean(np.abs(miss) < 1e-9):.3f} (bias {miss.mean():+.3f})'
              + f' | layout luck is {1 - kept:.2f} of the correction\'s variance; share without it {b[2] / kept if kept > .05 else float("nan"):+.2f}')


def per_side(rows, sims, sides, margins=(0.125, 0.25, 0.5), trusts=(0.2, 0.3, 0.5, 0.75, 1.0)):
    """The bot's rule weighted back to whole tables: B is played when Gen 6's gap for B is at most the margin and
    pimc + trust x correction is negative. Every gap fork records the probability with which it was drawn, so the sum
    over drawn pairs of (what the rule gains by playing B) / probability estimates the total over every (decision,
    other card) of one side at one table; `sides` is the number of sides at the root tables read (two a board in
    self-play). Tie-audit pairs (band -1) are left out. When a rule prefers two other cards at one decision both count."""
    rows = [r for r in rows if r['band'] >= 0]
    if not rows or not sides:
        return
    f = np.array([r['final'] for r in rows], float)
    imps = np.array([r['imps'] if r.get('imps') is not None else 0. for r in rows], float)
    w = 1 / np.array([r['propensity'] for r in rows])
    fam = [r['family'] for r in rows]
    pimc = np.array([r['pimc'] for r in rows])
    est = np.array([r['estimated'] for r in rows])

    def total(x):
        by = {}
        for v, g in zip(x * w, fam):
            by[g] = by.get(g, 0.) + v
        t = np.array(list(by.values()))
        return float(t.sum() / sides), float(math.sqrt(len(t) / max(1, len(t) - 1) * ((t - t.mean()) ** 2).sum()) / sides)

    print(f"\n== per side per table ({sides} sides, {len(rows)} gap-fork pairs): overrules a side | tricks a side | IMPs a side, against Gen 6's card")
    for s in sims:
        corr = np.array([r[s] for r in rows]) - pimc
        for m in margins:
            cells = []
            for t in trusts:
                play_b = (est <= m + 1e-9) & (pimc + t * corr < -1e-9)
                n, _ = total(play_b.astype(float))
                tr, tr_se = total(np.where(play_b, -f, 0.))
                im, im_se = total(np.where(play_b, -imps, 0.))
                cells.append(f'{n:4.2f} | {tr:+.3f}+-{tr_se:.3f} | {im:+.3f}+-{im_se:.3f}')
            print(f"   {s:16s} margin {m:5.3f}: " + '   '.join(f'trust {t:.2f}: {c}' for t, c in zip(trusts, cells)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('files', nargs='+')
    p.add_argument('--sides', type=int, default=0, help='sides at the root tables read (default: two for every file the bench read)')
    p.add_argument('--bands')
    p.add_argument('--tricks')
    p.add_argument('--split', action='store_true', help='also by band, by trick and by side')
    a = p.parse_args()
    rows, sims, sides = [], None, 0
    for path in a.files:
        d = json.load(open(path))
        rows += d['rows']
        sides += 2 * d['settings'].get('files', 0)
        names = [s['name'] for s in d['settings']['sims']]
        sims = names if sims is None else [s for s in sims if s in names]
    if a.bands:
        keep = {int(x) for x in a.bands.split(',')}
        rows = [r for r in rows if r['band'] in keep]
    if a.tricks:
        keep = {int(x) for x in a.tricks.split(',')}
        rows = [r for r in rows if r['trick'] in keep]
    report(rows, sims, title='all')
    if not a.tricks and not a.bands:
        per_side(rows, sims, a.sides or sides)
    if a.split:
        for band in sorted({r['band'] for r in rows}):
            sub = [r for r in rows if r['band'] == band]
            if len(sub) >= 100:
                report(sub, sims, title=f'band {band}')
        for name, test in (('declaring', lambda r: r['declaring']), ('defending', lambda r: not r['declaring'])):
            sub = [r for r in rows if test(r)]
            if len(sub) >= 100:
                report(sub, sims, title=name)
        for lo, hi in ((1, 2), (3, 4), (5, 6), (7, 9), (10, 13)):
            sub = [r for r in rows if lo <= r['trick'] <= hi]
            if len(sub) >= 100:
                report(sub, sims, title=f'tricks {lo}-{hi}')


if __name__ == '__main__':
    main()
