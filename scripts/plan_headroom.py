#!/usr/bin/env python3
"""What look-ahead can gain at the bench's forks, measured with the ceiling's playouts instead of one real deal.

  python scripts/plan_headroom.py ceil16a.json [ceil16b.json ...] [--sims other_seed.json ...] [--sides N]

A ceiling row (scripts/plan_ceiling.py) holds, for one fork pair and each of K layouts the decider thinks possible, the
tricks cards A and B took when real Gen 6 played every seat from there (`roll`) and double dummy (`dd`). The mean over
layouts of roll A - roll B is an estimate of what B costs in expectation when everyone plays on as Gen 6; it replaces
the single real deal's result (sd about 0.8 tricks a pair) as the measure of a rule that plays B.

1. Calibration: the real deal's result against that mean.
2. The ceiling's own headroom, split so that no layout both chooses and scores: a rule sees half of the layouts
   (n of K), plays B when its estimate of A - B is negative, and is scored on the other layouts. Two rules:
     corrected  recorded gap of Gen 6 at the table + trust x (playout - double dummy on the n layouts)
     plain      mean of the playouts on the n layouts alone
3. Rules from other benches (--sims: rows of scripts/plan_bench.py made with ANOTHER --seed, so their layouts are not
   the ceiling's): B is played when recorded gap + trust x correction < 0, scored by the ceiling's K layouts.

Gains are tricks gained over Gen 6's card: a sampled pair's mean, and, weighted by 1 / the pair's draw probability, a
side's total at one table (`--sides`, default 2 x the files read). Errors take deals as the unit.
"""
import argparse
import json
import math
import sys

import numpy as np


def clustered_mean(x, groups, weights=None, per=None):
    """Mean of x over rows (or, with `per`, the weighted total divided by `per`), deals as the unit of the error."""
    w = np.ones(len(x)) if weights is None else weights
    by = {}
    for v, u, g in zip(x * w, w, groups):
        t = by.setdefault(g, [0., 0.])
        t[0] += v
        t[1] += 1.
    t = np.array([v[0] for v in by.values()])
    n = np.array([v[1] for v in by.values()])
    G = len(t)
    if per:
        return float(t.sum() / per), float(math.sqrt(G / max(1, G - 1) * ((t - t.mean()) ** 2).sum()) / per)
    mean = t.sum() / n.sum()
    return float(mean), float(math.sqrt(G / max(1, G - 1) * ((t - mean * n) ** 2).sum()) / n.sum())


def show(g):
    return f'{g[0]:+.4f}+-{g[1]:.4f}'


def load(paths):
    rows = []
    for p in paths:
        d = json.load(open(p))
        rows += d['rows'] if isinstance(d, dict) else d
    return rows


def key(r):
    return (r['family'], r['table'], r['ply'], r['table_a'], r['table_b'])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('files', nargs='+')
    p.add_argument('--sims', nargs='*', default=[])
    p.add_argument('--sides', type=int, default=0)
    p.add_argument('--ties', action='store_true', help='keep the forks between cards the search rated exactly level (band -1)')
    p.add_argument('--splits', type=int, default=40)
    p.add_argument('--margins', default='0.125,0.25,0.5,9')
    p.add_argument('--trusts', default='0.25,0.5,0.75,1')
    p.add_argument('--seed', type=int, default=0)
    a = p.parse_args()
    rows = [r for r in load(a.files) if (r['band'] >= 0 or a.ties) and r.get('worlds')]
    seen, kept = set(), []
    for r in rows:
        if key(r) not in seen:
            seen.add(key(r))
            kept.append(r)
    rows = kept
    files = len({(r['family'], r['table']) for r in rows})
    sides = a.sides or 2 * len({r['family'] for r in rows})
    trusts = [float(t) for t in a.trusts.split(',')]
    margins = [float(m) for m in a.margins.split(',')]
    fam = [r['family'] for r in rows]
    final = np.array([r['final'] for r in rows], float)
    est = np.array([r['estimated'] for r in rows], float)
    pimc = np.array([r['pimc'] for r in rows], float)
    band = np.array([r['band'] for r in rows])
    w = 1 / np.array([r['propensity'] for r in rows])
    K = max(len(r['worlds']['roll']) for r in rows)
    count = np.array([len(r['worlds']['roll']) for r in rows])
    pad = lambda x, fill=0.: np.array([list(v) + [fill] * (K - len(v)) for v in x], float)
    sh = pad([r['worlds']['share'] for r in rows])                                   # 0 where a pair has fewer layouts
    sh = sh / sh.sum(1, keepdims=True)
    roll_a, roll_b = pad([[x[0] for x in r['worlds']['roll']] for r in rows]), pad([[x[1] for x in r['worlds']['roll']] for r in rows])
    dd_a, dd_b = pad([[x[0] for x in r['worlds']['dd']] for r in rows]), pad([[x[1] for x in r['worlds']['dd']] for r in rows])
    d = roll_a - roll_b                                                              # what B costs on each layout, real bots
    c = d - (dd_a - dd_b)                                                            # the same beyond double dummy
    mean = lambda x, m=None: ((x * sh * (1 if m is None else m)).sum(1) / np.maximum((sh * (1 if m is None else m)).sum(1), 1e-12))
    truth = mean(d)
    neff = 1 / (sh ** 2).sum(1)
    luck = lambda x: np.where(neff > 1.5, ((x - mean(x)[:, None]) ** 2 * sh).sum(1) / np.maximum(neff - 1, 1e-9), 0.)   # variance of the mean
    print(f'{len(rows)} gap-fork pairs on {len(set(fam))} deals ({files} tables read as {sides} sides); layouts a pair: {K} for '
          f'{np.mean(count == K):.3f} of pairs, fewer for the rest (mean {count.mean():.1f})')

    # 1. calibration
    X = np.column_stack([np.ones(len(rows)), truth])
    beta = np.linalg.lstsq(X, final, rcond=None)[0]
    noise = luck(d).mean()
    print(f'\n1. Calibration. B really cost {show(clustered_mean(final, fam))} on the real deal; the playouts on the layouts say '
          f'{show(clustered_mean(truth, fam))}; double dummy on the same layouts {show(clustered_mean(mean(dd_a - dd_b), fam))}; '
          f'the 32-layout search {show(clustered_mean(pimc, fam))}; Gen 6 at the table had {show(clustered_mean(est, fam))}.')
    print(f'   real result on the playout mean: slope {beta[1]:.2f}; the mean\'s variance {truth.var():.4f} of which layout luck {noise:.4f} '
          f'({noise / truth.var():.2f}), so slope 1 would show as {1 - noise / truth.var():.2f}.')
    signal = max(0., mean(c).var() - luck(c).mean())
    print(f'   correction beyond double dummy: sd {mean(c).std():.3f}, of which real (not layout luck) sd {math.sqrt(signal):.3f}')
    for b in sorted(set(band)):
        m = band == b
        s_ = max(0., mean(c)[m].var() - luck(c)[m].mean())
        print(f'     band {b}: {m.sum()} pairs, recorded gap mean {est[m].mean():.3f}, real correction sd {math.sqrt(s_):.3f} '
              f'(measured {mean(c)[m].std():.3f}); B better in expectation (playout mean < 0) in {np.mean(truth[m] < -1e-9):.3f}')

    # 2. the ceiling's own headroom, split
    rng = np.random.default_rng(a.seed)
    valid = sh > 0
    print(f'\n2. Real Gen 6 playouts as the look-ahead: a share of a pair\'s layouts chooses and the others score. Tricks a pair | a side at one table.')
    for share_ in (0.25, 0.5, 0.75):
        n = np.maximum(1, np.round(share_ * count)).astype(int)
        gains = {('corrected', t, m): np.zeros(len(rows)) for t in trusts for m in margins}
        gains.update({('plain', 1., m): np.zeros(len(rows)) for m in margins})
        gains.update({('behind', th, m): np.zeros(len(rows)) for th in (.125, .25, .375, .5) for m in (0.25, 9.)})   # needs the estimate to be this far below zero
        plays = {k: np.zeros(len(rows)) for k in gains}
        for _ in range(a.splits):
            rank = np.argsort(np.argsort(np.where(valid, rng.random(sh.shape), 9.), axis=1), axis=1)
            first = (rank < n[:, None]) & valid
            rest = (rank >= n[:, None]) & valid
            rest = np.where(rest.any(1, keepdims=True), rest, first)                 # a single layout scores itself
            c1, d1, score = mean(c, first), mean(d, first), -mean(d, rest)
            for (kind, t, m) in gains:
                b = ((est + t * c1 < -1e-9) if kind == 'corrected' else (est + c1 < -t) if kind == 'behind' else (d1 < -1e-9)) & (est <= m + 1e-9)
                gains[(kind, t, m)] += np.where(b, score, 0.) / a.splits
                plays[(kind, t, m)] += b / a.splits
        print(f'   {share_:.2f} of the layouts choose ({int(round(share_ * K))} of {K}):')
        for (kind, t, m), g in gains.items():
            if m not in (0.25, 9) and not (kind == 'corrected' and t == 0.5):
                continue
            print(f'     {kind:9s} {"by" if kind == "behind" else "trust"} {t:.3f} margin {m:5.3f}: plays B in {plays[(kind, t, m)].mean():.3f} of pairs; '
                  f'{show(clustered_mean(g, fam))} | overrules a side {float((plays[(kind, t, m)] * w).sum() / sides):.2f}, '
                  f'tricks a side {show(clustered_mean(g, fam, w, sides))}')
    # upper bound with hindsight on the same layouts (biased up: the layouts that choose also score)
    print(f'   hindsight on all layouts (biased up): {show(clustered_mean(np.maximum(0, -truth), fam))} a pair, '
          f'{show(clustered_mean(np.maximum(0, -truth), fam, w, sides))} a side')
    print(f'   pairs a side at one table (sum of 1 / draw probability): {float(w.sum() / sides):.1f}; with recorded gap <= 0.25: {float((w * (est <= 0.25 + 1e-9)).sum() / sides):.1f}')

    # 2b. a model of the same: within bins of Gen 6's recorded gap, the true expected cost of B is taken as normal
    G = lambda x: math.exp(-x * x / 2) / math.sqrt(2 * math.pi) - x * (1 - 0.5 * (1 + math.erf(x / math.sqrt(2))))
    edges = [-1, 1e-9, .0625, .125, .25, .5, 1., 99.]
    per_layout = np.where(neff > 1.5, ((d - truth[:, None]) ** 2 * sh).sum(1) * neff / np.maximum(neff - 1, 1e-9), 0.)   # variance of one layout's result
    luck_d = luck(d)
    ns = ('exact', 8, 16, 32, 64, 128, 512)

    def model(index, sides_, text=False):
        totals, low = {n: 0. for n in ns}, {n: 0. for n in ns}
        e_, t_, w_, l_, p_ = est[index], truth[index], w[index], luck_d[index], per_layout[index]
        for lo, hi in zip(edges[:-1], edges[1:]):
            m_ = (e_ > lo) & (e_ <= hi)
            if m_.sum() < 10:
                continue
            mu = float(np.average(t_[m_], weights=w_[m_]))
            tau2 = max(0., float(np.average((t_[m_] - mu) ** 2, weights=w_[m_])) - float(np.average(l_[m_], weights=w_[m_])))
            s2 = float(np.average(p_[m_], weights=w_[m_]))
            tau = math.sqrt(tau2)
            pairs = float(w_[m_].sum() / sides_)
            line = f'     gap ({max(lo, 0):.4f}, {hi:.4f}]: {m_.sum():4d} pairs, {pairs:5.2f} a side; m {mu:+.3f}, s {tau:.3f}, one layout sd {math.sqrt(s2):.2f};'
            for n in ns:
                t = tau if n == 'exact' else (tau2 / math.sqrt(tau2 + s2 / n) if tau2 > 0 else 0.)
                g = t * G(mu / t) if t > 1e-9 else max(0., -mu)
                totals[n] += pairs * g
                if hi <= 1.:
                    low[n] += pairs * g
                line += f' {n}: {pairs * g:.4f}'
            if text:
                print(line)
        return totals, low

    print(f'\n2b. Model: in each bin of the recorded gap the true expected cost of B is normal (mean m, sd s after taking out layout luck). '
          f'Tricks a side at one table from knowing it exactly, and from n layouts of real playouts used with the right shrinkage.')
    totals, low = model(np.arange(len(rows)), sides, True)
    ids = sorted(set(fam))
    where = {g: [] for g in ids}
    for i, g in enumerate(fam):
        where[g].append(i)
    reps = []
    brng = np.random.default_rng(a.seed + 1)
    for _ in range(200):
        pick = brng.integers(0, len(ids), len(ids))
        index = np.concatenate([where[ids[j]] for j in pick])
        reps.append(model(index, sides)[1])
    print('     total a side:                      ' + ', '.join(f'{n}: {v:.3f}' for n, v in totals.items()))
    print('     without recorded gaps above 1:     ' + ', '.join(f'{n}: {low[n]:.3f} +- {np.std([r[n] for r in reps]):.3f}' for n in ns) + '   (+- from resampling deals)')

    # 3. rules from other benches
    for path in a.sims:
        d2 = json.load(open(path))
        other = {key(r): r for r in d2['rows']}
        if d2['settings'].get('seed', 0) == 0:
            print(f'\n   WARNING: {path} was made with the ceiling\'s seed: its layouts are the ceiling\'s, and the figures below are biased up.')
        index = [i for i, r in enumerate(rows) if key(r) in other]
        if not index:
            continue
        sub = [other[key(rows[i])] for i in index]
        f2, t2, e2, w2 = [fam[i] for i in index], truth[index], est[index], w[index]
        fin2 = final[index]
        sides2 = a.sides or 2 * len(set(f2))
        names = [s['name'] for s in d2['settings']['sims']]
        wide = np.array([r['pimc'] for r in sub])
        layouts = np.mean([r['layouts'] for r in sub])
        noise2 = luck_d[index].mean()
        print(f'\n3. Rules from {path} ({len(index)} pairs shared, {len(set(f2))} deals, {layouts:.0f} layouts a pair there, recorded gap up to '
              f'{e2.max():.3f}): tricks gained over Gen 6\'s card, scored by the ceiling\'s playouts [and by the real deal]. A pair | a side at one table.')
        print(f'   the ceiling\'s playout mean has variance {t2.var():.4f} here, of which layout luck {noise2:.4f}')

        def line(name, b):
            return (f'     {name:34s} plays B in {b.mean():.3f}; a pair {show(clustered_mean(np.where(b, -t2, 0.), f2))} '
                    f'[{show(clustered_mean(np.where(b, -fin2, 0.), f2))}] | a side: overrules {float((b * w2).sum() / sides2):.2f}, '
                    f'tricks {show(clustered_mean(np.where(b, -t2, 0.), f2, w2, sides2))} [{show(clustered_mean(np.where(b, -fin2, 0.), f2, w2, sides2))}]')

        X = np.column_stack([np.ones(len(sub)), e2, wide - e2])
        beta = np.linalg.lstsq(X, t2, rcond=None)[0]
        print(f'   double dummy on the bench\'s own layouts: ceiling = {beta[0]:+.3f} {beta[1]:+.2f} x recorded gap {beta[2]:+.2f} x (wide - recorded); '
              f'residual variance {np.var(t2 - X @ beta):.4f}')
        for u in (0.5, 0.75, 1.0):
            print(line(f'double dummy, {u:.2f} wide + {1 - u:.2f} recorded', (1 - u) * e2 + u * wide < -1e-9))
        for s in names:
            corr = np.array([r[s] - r['pimc'] for r in sub])
            X = np.column_stack([np.ones(len(sub)), e2, wide - e2, corr])
            beta = np.linalg.lstsq(X, t2, rcond=None)[0]
            res = np.var(t2 - X @ beta)
            print(f'   {s}: ceiling = {beta[0]:+.3f} {beta[1]:+.2f} x recorded gap {beta[2]:+.2f} x (wide - recorded) {beta[3]:+.3f} x correction; '
                  f'residual variance {res:.4f} (luck alone would leave {noise2:.4f}); sd of the correction {corr.std():.3f}')
            for t in trusts:
                print(line(f'recorded + {t:.2f} x correction', e2 + t * corr < -1e-9))
            for t in trusts:
                print(line(f'half wide dd + {t:.2f} x correction', .5 * e2 + .5 * wide + t * corr < -1e-9))
            for t in trusts:
                print(line(f'wide dd + {t:.2f} x correction', wide + t * corr < -1e-9))
            plain = np.array([r[s] for r in sub])                       # the playouts' own mean, no double dummy on the bench's layouts needed
            for t in trusts:
                print(line(f'{1 - t:.2f} recorded + {t:.2f} playout mean', (1 - t) * e2 + t * plain < -1e-9))


if __name__ == '__main__':
    sys.exit(main())
