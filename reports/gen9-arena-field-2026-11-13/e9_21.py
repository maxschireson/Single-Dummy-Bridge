#!/usr/bin/env python3
"""E9-21: field choice and Nash average on the current ladder cells (g9, Gen 9).

Rebuilds the ladder's points exactly as scripts/arena_ladder.py fit does (variants merged by its rule), then:
cells by A4 (direct pair mean mixed with the leave-one-out model prediction), field scores under two fields, the
maximum-entropy Nash equilibrium of the cells matrix and each point's Nash average, and bootstrap standard errors
(boards resampled within pair). Read-only; decides nothing.

  python3 e9_21.py --ladder-wt DIR --rows rows.jsonl.gz --out e9_21.json [--boot 200] [--no-priors]
"""
import argparse, gzip, json, math, sys
from pathlib import Path

import numpy as np
from scipy.optimize import linprog, minimize


def load(ladder_wt):
    sys.path.insert(0, str(ladder_wt))
    sys.path.insert(0, str(Path(ladder_wt) / 'scripts'))
    import arena_ladder as al  # noqa
    return al


def points(al, rows, meta, cfg):
    """Steps 1 and 2 of arena_ladder.fit_command: (results [(i, j, x)], players, priors)."""
    settings, fp = {}, {}
    for m in meta['sources']:
        for k, spec in m['bots'].items():
            settings[(m['source'], k)] = al.spec_settings(spec)
    natives = al.native_results(rows, lambda s, b: (s, b))
    vboards = {}
    for i, j, _ in natives:
        vboards[i] = vboards.get(i, 0) + 1; vboards[j] = vboards.get(j, 0) + 1
    fps = {}
    for (s, b), n in vboards.items():
        fp[(s, b)] = al.fingerprint(settings.get((s, b)))
        fps.setdefault(b, {}).setdefault(fp[(s, b)], [0, []])
        fps[b][fp[(s, b)]][0] += n; fps[b][fp[(s, b)]][1].append(s)
    main_fp = {b: max(v, key=lambda f: (f != 'unpublished', v[f][0])) for b, v in fps.items()}

    def vid(s, b):
        f = fp.get((s, b))
        if f is None or len(fps.get(b, {})) < 2 or f == main_fp[b]:
            return b
        return f'{b}#{f}'

    anchor, weak = cfg['anchor'], cfg['weak_prior_sd']

    def priors_for(players):
        out = {}
        for p in players:
            b = p.split('#')[0]
            c = cfg['bots'].get(b, {})
            pr, parent = c.get('prior'), c.get('parent')
            if p == b and pr and parent and parent in players:
                out[p] = (parent, pr['estimate'], al.prior_sd(pr, cfg))
            else:
                out[p] = (None, 0.0, weak)
        return out

    vres = al.native_results(rows, vid)
    vplayers = sorted({x for i, j, _ in vres for x in (i, j)})
    vfit = al.fit_population(vres, vplayers, anchor, priors_for(vplayers), weak)
    merged = {}
    for b, v in fps.items():
        if len(v) < 2:
            continue
        for f, (n, srcs) in v.items():
            p = b if f == main_fp[b] else f'{b}#{f}'
            if p == b:
                continue
            d, se = al.contrast(vfit, vplayers, p, b)
            merged[p] = abs(d) < 2 * se if f == 'unpublished' else (abs(d) < 0.1 and abs(d) < 2 * se)

    def pid(s, b):
        v = vid(s, b)
        return b if v == b or merged.get(v) else v

    res = al.native_results(rows, pid)
    players = sorted({x for i, j, _ in res for x in (i, j)})
    return res, players, priors_for(players), anchor, weak


def fit(al, res, players, anchor, priors, weak, t2=None, skip=None):
    """bayes_fit on pair summaries; skip=(i, j) leaves that pair out (both orders)."""
    pairs = [q for q in al.ar.summarise(res) if q.n > 0]
    if skip is not None:
        pairs = [q for q in pairs if {q.i, q.j} != set(skip)]
    s, C, t2, _ = al.bayes_fit(pairs, players, anchor, priors, weak, t2=t2)
    return pairs, s, C, t2


def cells(al, res, players, anchor, priors, weak):
    """A4 cells: for a played pair, the precision-weighted mix of its own mean and the leave-one-out prediction
    (variance a'Ca + t2); for an unplayed pair, the prediction from the full fit."""
    pairs, s, C, t2 = fit(al, res, players, anchor, priors, weak)
    k = len(players); ix = {p: n for n, p in enumerate(players)}
    cell = np.zeros((k, k)); var = np.zeros((k, k)); direct = {}
    for q in pairs:
        direct[(q.i, q.j)] = (q.mean, q.se2(), q.n)
    for a in range(k):
        for b in range(a + 1, k):
            i, j = players[a], players[b]
            key = (i, j) if (i, j) in direct else ((j, i) if (j, i) in direct else None)
            if key is None:
                v = np.zeros(k); v[a] += 1; v[b] -= 1
                mu, vv = float(v @ s), float(v @ C @ v) + t2
            else:
                m, e2, _ = direct[key]
                if key == (j, i):
                    m = -m
                _, s1, C1, _ = fit(al, res, players, anchor, priors, weak, t2=t2, skip=(i, j))
                v = np.zeros(k); v[a] += 1; v[b] -= 1
                pm, pv = float(v @ s1), float(v @ C1 @ v) + t2
                w1, w2 = 1 / e2, 1 / pv
                mu, vv = (w1 * m + w2 * pm) / (w1 + w2), 1 / (w1 + w2)
            cell[a, b], cell[b, a] = mu, -mu
            var[a, b] = var[b, a] = vv
    return cell, var, s, C, t2


def field_scores(cell, players, field):
    """Mean cell against the field's members (equal shares), leaving out the player itself."""
    out = {}
    for a, p in enumerate(players):
        js = [players.index(f) for f in field if f in players and f != p]
        out[p] = float(np.mean([cell[a, j] for j in js])) if js else float('nan')
    return out


def maxent_nash(A, tol=1e-9):
    """Maximum-entropy Nash equilibrium of the symmetric zero-sum game with antisymmetric payoff A (row's payoff).
    p is an equilibrium iff p >= 0, sum p = 1, A p <= 0. Among those, maximise entropy (Balduzzi et al. 2018)."""
    k = A.shape[0]
    lp = linprog(np.zeros(k), A_ub=A, b_ub=np.zeros(k) + tol, A_eq=np.ones((1, k)), b_eq=[1], bounds=[(0, 1)] * k,
                 method='highs')
    p0 = lp.x
    cons = [dict(type='eq', fun=lambda p: p.sum() - 1), dict(type='ineq', fun=lambda p: -(A @ p) + tol)]
    ent = lambda p: float(np.sum(p * np.log(np.clip(p, 1e-12, None))))
    r = minimize(ent, np.clip(p0, 1e-6, None) / np.clip(p0, 1e-6, None).sum(), method='SLSQP', bounds=[(0, 1)] * k,
                 constraints=cons, options=dict(maxiter=500, ftol=1e-12))
    p = r.x if r.success and np.all(A @ r.x <= 1e-6) else p0
    p = np.clip(p, 0, None); p /= p.sum()
    return p


def summary(al, res, players, anchor, priors, weak, fields):
    cell, var, s, C, t2 = cells(al, res, players, anchor, priors, weak)
    p = maxent_nash(cell)
    nash = cell @ p
    out = dict(strength={q: float(s[n]) for n, q in enumerate(players)}, t2=t2,
               nash_weights={q: float(p[n]) for n, q in enumerate(players) if p[n] > 1e-4},
               nash_average={q: float(nash[n]) for n, q in enumerate(players)},
               fields={name: field_scores(cell, players, f) for name, f in fields.items()},
               cell=cell.tolist(), cell_se=np.sqrt(var).tolist())
    return out


def bootstrap(res, rng):
    by = {}
    for i, j, x in res:
        by.setdefault((i, j), []).append(x)
    out = []
    for (i, j), xs in by.items():
        xs = np.array(xs)
        out += [(i, j, float(v)) for v in xs[rng.integers(0, len(xs), len(xs))]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ladder-wt', type=Path, required=True)
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--boot', type=int, default=200)
    ap.add_argument('--no-priors', action='store_true')
    ap.add_argument('--seed', type=int, default=921)
    ap.add_argument('--exclude-source', action='append', default=[])
    a = ap.parse_args()
    al = load(a.ladder_wt)
    with gzip.open(a.rows, 'rt') as f:
        rows = [r for r in (json.loads(line) for line in f) if r['source'] not in a.exclude_source]
    meta = json.loads(a.rows.with_suffix('').with_suffix('.meta.json').read_text())
    meta['sources'] = [m for m in meta['sources'] if m['source'] not in a.exclude_source]
    cfg = json.loads((a.ladder_wt / 'configs' / 'ladder-bots.json').read_text())
    res, players, priors, anchor, weak = points(al, rows, meta, cfg)
    if a.no_priors:
        priors = {p: (None, 0.0, weak) for p in players}
    fields = dict(population=[p for p in players],
                  declared_example=[p for p in ('ben64', '8s-32', '71s-32', '6-32') if p in players])
    base = summary(al, res, players, anchor, priors, weak, fields)
    rng = np.random.default_rng(a.seed)
    boots = []
    for b in range(a.boot):
        r = summary(al, bootstrap(res, rng), players, anchor, priors, weak, fields)
        boots.append(dict(nash_average=r['nash_average'], fields=r['fields'], nash_weights=r['nash_weights'],
                          strength=r['strength']))
        if (b + 1) % 25 == 0:
            print(f'bootstrap {b + 1}/{a.boot}', file=sys.stderr, flush=True)

    def se(get):
        return {p: float(np.std([get(x)[p] for x in boots], ddof=1)) if boots else None for p in players}

    base['se'] = dict(strength=se(lambda x: x['strength']), nash_average=se(lambda x: x['nash_average']),
                      **{f'field_{n}': se(lambda x, n=n: x['fields'][n]) for n in fields})
    support = {}
    for x in boots:
        for p in x['nash_weights']:
            support[p] = support.get(p, 0) + 1
    base['nash_support_share'] = {p: c / len(boots) for p, c in sorted(support.items(), key=lambda kv: -kv[1])}
    base['players'] = players
    base['boards'] = len(res)
    base['priors'] = not a.no_priors
    base['field_members'] = fields
    base['excluded_sources'] = a.exclude_source
    a.out.write_text(json.dumps(base, indent=1))
    print(f'{len(players)} points, {len(res):,} boards -> {a.out}')


if __name__ == '__main__':
    main()
