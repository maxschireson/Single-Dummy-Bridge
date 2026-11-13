#!/usr/bin/env python3
"""  python scripts/plan_play_rule.py plays.pkl      (plays.pkl from scripts/plan_play_scan.py)

Plays by kind, on the real deals: where the search's gap between two cards is off by kind of play, and a rule that
adjusts the gaps by a table of kinds (fitted on half the deals, scored on the other half through the forks)."""
import pickle, sys, math, json
import numpy as np
d = pickle.load(open(sys.argv[1], 'rb'))
rows, tables = d['rows'], d['tables']
print(len(rows), 'forks on', len({r['family'] for r in rows}), 'deals;', tables, 'tables')
side = lambda r: 'declaring' if r['declaring'] else 'defending'
KINDS = {s: sorted({k for r in rows if side(r) == s for k in r['kinds'].values()}) for s in ('declaring', 'defending')}

def design(sel, s):
    K = KINDS[s]; ix = {k: i for i, k in enumerate(K)}
    X = np.zeros((len(sel), len(K) + 1)); y = np.zeros(len(sel))
    for i, r in enumerate(sel):
        X[i, ix[r['kinds'][r['forced']]]] += 1; X[i, ix[r['kinds'][r['played']]]] -= 1
        X[i, -1] = r['est']                                  # last column: the recorded gap (its coefficient is slope - 1)
        y[i] = r['real'] - r['est']
    return X, y

def fit(sel, s, ridge=5.):
    X, y = design(sel, s)
    R = ridge * np.eye(X.shape[1]); R[-1, -1] = 0.
    beta = np.linalg.solve(X.T @ X + R, X.T @ y)
    out = dict(zip(KINDS[s], beta[:-1] - beta[:-1].mean())); out['@slope'] = float(beta[-1])
    return out

def table(s):
    sel = [r for r in rows if side(r) == s]
    X, y = design(sel, s)
    K = KINDS[s]
    R = 5. * np.eye(len(K) + 1); R[-1, -1] = 0.
    full = np.linalg.solve(X.T @ X + R, X.T @ y); beta = full[:-1] - full[:-1].mean()
    print(f'\n{s}: real cost = {1 + full[-1]:.3f} x recorded gap + kinds')
    fams = sorted({r['family'] for r in sel}); where = {f: [] for f in fams}
    for i, r in enumerate(sel):
        where[r['family']].append(i)
    rng = np.random.default_rng(0); reps = []
    for _ in range(100):
        pick = np.concatenate([where[fams[j]] for j in rng.integers(0, len(fams), len(fams))])
        b = np.linalg.solve(X[pick].T @ X[pick] + R, X[pick].T @ y[pick])[:-1]; reps.append(b - b.mean())
    se = np.std(reps, axis=0)
    diff = (np.abs(X[:, :-1]).sum(1) > 0).sum()
    print(f'\n{s}: {len(sel)} forks, {diff} between two kinds. The search flatters a kind by (tricks; + = it does worse in real play than the gap says); times played / forced:')
    for k, b, e in sorted(zip(K, beta, se), key=lambda t: -t[1]):
        npl, nf = int((X[:, K.index(k)] < 0).sum()), int((X[:, K.index(k)] > 0).sum())
        if npl + nf >= 150:
            print(f'   {k:44s} {b:+.3f} +- {e:.3f}   {npl:6d} / {nf:6d}')

def rule(sel, tabs, scale, tricks=None):
    gains, imps, changed, seen = {}, {}, 0, 0
    for r in sel:
        if tricks and not tricks[0] <= r['trick'] <= tricks[1]:
            continue
        t = tabs[side(r)]
        adj = {c: (1 + t['@slope']) * g + scale * t.get(r['kinds'][c], 0.) for c, g in r['gaps'].items() if c == r['played'] or g > 1e-9}
        best = min(adj.values()); top = [c for c, v in adj.items() if v <= best + 1e-9]
        seen += 1
        if r['played'] in top:
            continue
        changed += 1
        if r['forced'] in top:
            gains[r['family']] = gains.get(r['family'], 0.) - r['real'] / r['prop'] / len(top)
            imps[r['family']] = imps.get(r['family'], 0.) - r['imps'] / r['prop'] / len(top)
    return gains, imps, changed / max(1, seen)

for s in ('declaring', 'defending'):
    table(s)

fams = sorted({r['family'] for r in rows}); rng = np.random.default_rng(1); half = set(rng.permutation(fams)[:len(fams) // 2].tolist())
A, B = [r for r in rows if r['family'] in half], [r for r in rows if r['family'] not in half]
N = tables
def tot(dicts):
    v = {}
    for dct in dicts:
        for k, x in dct.items():
            v[k] = v.get(k, 0.) + x
    a = np.array(list(v.values()) + [0.] * max(0, N - len(v)))
    return a.sum() / (2 * N), math.sqrt(N / (N - 1) * ((a ** 2).sum() - a.sum() ** 2 / N)) / (2 * N)
print('\nThe rule (smallest gap + scale x table[kind], among the card played and the cards rated behind it), table from one half of the deals, scored on the other, both ways. A side at one table:')
for tricks in (None, (1, 2), (3, 6), (7, 13)):
    for scale in (0.5, 1.0):
        gs, ims, ch = [], [], []
        for fit_on, score_on in ((A, B), (B, A)):
            tabs = {s: fit([r for r in fit_on if side(r) == s], s) for s in ('declaring', 'defending')}
            g, im, c = rule(score_on, tabs, scale, tricks)
            gs.append(g); ims.append(im); ch.append(c)
        (g, se), (im, ise) = tot(gs), tot(ims)
        print(f'   tricks {"all" if tricks is None else tricks}, scale {scale}: changes {np.mean(ch):.3f} of the forked decisions; {g:+.4f} +- {se:.4f} tricks; {im:+.4f} +- {ise:.4f} IMPs')
