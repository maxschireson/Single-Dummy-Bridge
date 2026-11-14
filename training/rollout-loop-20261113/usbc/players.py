#!/usr/bin/env python3
"""Named players in units of the adult field's skill spread (SD beyond luck). TEST DATA ONLY.

Per average board (curve or blend measure, see norm_avg.py), per role and pooled (1/4 declarer, 1/2 defender,
1/4 lead). The yardstick is every adult player with 20+ boards in the role on adult boards: their mean, and the
spread of their true scores (variance of the scores minus the mean squared standard error). A named player's
score is on their adult boards (--by-year: also each year's); junior boards are shown on a separate line. + means more tricks lost (worse).
Shrunk: the score pulled toward the field mean by the reliability tau^2 / (tau^2 + se^2), with its posterior SD.
"""
import argparse, collections, math, sys
import numpy as np

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from analyze import load, units  # noqa: E402
from norm_avg import ROLES, expectations  # noqa: E402

W = dict(declarer=.25, defense=.5, lead=.25)


def boot(sc, se2, n=1000, seed=7):
    """Bootstrap standard error of the SD beyond luck, resampling players."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        i = rng.integers(0, len(sc), len(sc))
        out.append(math.sqrt(max(sc[i].var(ddof=1) - se2[i].mean(), 0.)))
    return float(np.std(out, ddof=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--players', nargs='+', default=['Max Schireson'])
    ap.add_argument('--min', type=int, default=20)
    ap.add_argument('--by-year', action='store_true', help='split each player\'s adult boards by year')
    ap.add_argument('--ref', default='', help='yardstick from this category\'s boards only (e.g. Open); default every adult board')
    ap.add_argument('--only-ref', action='store_true', help='score the named players on the --ref category\'s boards only')
    a = ap.parse_args()
    T = load(a.dirs)
    U = units(T)
    E = expectations(T, U)
    loss, role_of, isad = E['loss'], E['role_of'], E['isad']
    exp = dict(curve=E['exp_curve'], both=E['exp_both'])
    ref = E['ref']

    def stat(ks, how):
        d = loss[ks] - exp[how][ks]
        return d.mean() + ref[role_of[ks[0]]]['loss'], d.std(ddof=1) / math.sqrt(len(d))

    # the adult field: per player and role, adult boards
    cat = np.array([T[u[0]]['category'] for u in U])
    inref = (cat == a.ref) if a.ref else isad
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for k, u in enumerate(U):
        if u[3] and inref[k]:
            per[u[3]][u[1]].append(k)
    for how in ('curve', 'both'):
        field = {}
        for role in ROLES:
            v = [stat(np.array(r[role]), how) for r in per.values() if len(r[role]) >= a.min]
            sc = np.array([x[0] for x in v]); se2 = np.array([x[1] ** 2 for x in v])
            field[role] = (sc.mean(), sc.std(ddof=1), math.sqrt(max(sc.var(ddof=1) - se2.mean(), 0.)), len(v), boot(sc, se2))
        v = []
        for r in per.values():
            if all(len(r[role]) >= a.min for role in ROLES):
                s = [stat(np.array(r[role]), how) for role in ROLES]
                v.append((sum(W[role] * x[0] for role, x in zip(ROLES, s)),
                          sum((W[role] * x[1]) ** 2 for role, x in zip(ROLES, s))))
        sc = np.array([x[0] for x in v]); se2 = np.array([x[1] for x in v])
        field['pooled'] = (sc.mean(), sc.std(ddof=1), math.sqrt(max(sc.var(ddof=1) - se2.mean(), 0.)), len(v), boot(sc, se2))
        print(f'\n== {how} measure. Field: {a.ref or "adult"} boards, players with {a.min}+ boards in the role: mean, SD, SD beyond luck, players')
        for role, (m, sd, tau, n, bse) in field.items():
            print(f'  {role:8s} {m:.3f}  SD {sd:.3f}  beyond luck {tau:.3f} +- {bse:.3f} (bootstrap over players)  ({n} players)')

        for name in a.players:
            ids = {u[3] for u in U if (u[4] or '').lower() == name.lower()}
            print(f'  {name}:')
            years = sorted({T[u[0]]['year'] for u in U if u[3] in ids})
            mine = inref if a.only_ref else isad
            splits = [('adult', lambda k: mine[k])]
            if a.by_year:
                splits += [(f'ad {y}', lambda k, y=y: mine[k] and T[U[k][0]]['year'] == y) for y in years]
            splits += [('junior', lambda k: not isad[k])]
            for label, keep in splits:
                s = {}
                for role in ROLES:
                    ks = np.array([k for k, u in enumerate(U) if u[3] in ids and u[1] == role and keep(k)])
                    if len(ks) >= 2:
                        s[role] = (*stat(ks, how), len(ks))
                if not s:
                    continue
                if len(s) == 3:
                    s['pooled'] = (sum(W[r] * s[r][0] for r in ROLES), math.sqrt(sum((W[r] * s[r][1]) ** 2 for r in ROLES)),
                                   s['declarer'][2] + s['defense'][2])
                for role, (x, se, n) in s.items():
                    m, sd, tau, _, _ = field[role]
                    line = f'    {label:6s} {role:8s} {x:.3f} +- {se:.3f} ({n:4d}) | vs field {x - m:+.3f}'
                    if tau > 0:
                        rel = tau ** 2 / (tau ** 2 + se ** 2)
                        line += (f' = {(x - m) / tau:+.2f} +- {se / tau:.2f} SD beyond luck; shrunk {rel * (x - m) / tau:+.2f}'
                                 f' +- {math.sqrt(rel) * se / tau:.2f} (reliability {rel:.2f})')
                    else:
                        line += ' (no spread beyond luck)'
                    print(line)


if __name__ == '__main__':
    main()
