#!/usr/bin/env python3
"""Opening leads by kind, on the real deals, and a rule that adjusts the search's lead by kind.

  python scripts/plan_lead_rule.py leads.pkl [tables_out.json]      (leads.pkl from scripts/plan_lead_scan.py)

1. For every lead fork: (what the forced lead really cost) - (the search's gap), regressed on kind(forced) - kind(played).
   A positive figure for a kind = the search flatters it: it does worse in real play than the search's estimate says.
2. A rule: lead the card with the smallest (gap + scale x table[kind]). Its gain over the search's lead is estimated
   from the forks alone: a fork counts when its forced lead is the rule's lead, weighted by 1 / its draw probability.
"""
import pickle, sys, math, json
import numpy as np
recs = pickle.load(open(sys.argv[1], 'rb')) if __name__ == '__main__' else []

def kind(c, hand, trump, split=False):
    suit = c // 13
    held = sorted([x % 13 for x in hand if x // 13 == suit], reverse=True)
    n, r = len(held), c % 13
    if trump is not None and trump <= 3 and suit == trump:
        k = 'trump'
    elif n == 1:
        k = 'singleton'
    elif r == 12:
        k = 'ace'
    elif r >= 9 and held.index(r) + 1 < n and held[held.index(r) + 1] == r - 1:
        k = 'top of touching honours'
    elif r >= 9:
        k = 'honour, not touching'
    elif n == 2:
        k = 'small from a doubleton'
    elif any(x >= 9 for x in held):
        k = 'small from an honour'
    else:
        k = 'small from small cards'
    return k

KINDS = ['singleton', 'ace', 'top of touching honours', 'honour, not touching', 'small from a doubleton', 'small from an honour', 'small from small cards', 'trump']
def scope_of(o):
    return 'NT' if o['trump'] is None or o['trump'] > 3 else 'suit'

def fit(sel):
    """table by kind from the forks of `sel` (records), least squares, mean zero."""
    X, y, fam = [], [], []
    for o in sel:
        ka = kind(o['played'], o['hand'], o['trump'])
        for b, est, prop, real, imps, band in o['forks']:
            row = np.zeros(len(KINDS)); row[KINDS.index(kind(b, o['hand'], o['trump']))] += 1; row[KINDS.index(ka)] -= 1
            X.append(row); y.append(real - est); fam.append(o['family'])
    X, y = np.array(X), np.array(y)
    beta = np.linalg.solve(X.T @ X + 1e-6 * np.eye(len(KINDS)), X.T @ y)
    return beta - beta.mean(), X, y, fam

def table(sel, label):
    beta, X, y, fam = fit(sel)
    fams = sorted(set(fam)); where = {f: [] for f in fams}
    for i, f in enumerate(fam):
        where[f].append(i)
    rng = np.random.default_rng(0); reps = []
    for _ in range(200):
        pick = np.concatenate([where[fams[j]] for j in rng.integers(0, len(fams), len(fams))])
        b = np.linalg.solve(X[pick].T @ X[pick] + 1e-6 * np.eye(len(KINDS)), X[pick].T @ y[pick]); reps.append(b - b.mean())
    se = np.std(reps, axis=0)
    played = {k: 0 for k in KINDS}
    for o in sel:
        played[kind(o['played'], o['hand'], o['trump'])] += 1
    print(f'\n{label}: {len(sel)} leads, {len(y)} forks. The search flatters a kind by (tricks, real deals):')
    for k, b, s in sorted(zip(KINDS, beta, se), key=lambda t: -t[1]):
        print(f'   {k:26s} {b:+.3f} +- {s:.3f}   the search leads it {played[k] / len(sel):.3f} of the time; forced {int((X[:, KINDS.index(k)] > 0).sum())}')
    return dict(zip(KINDS, beta))

def rule(sel, tab, scale, by_scope=None):
    """(tricks gained a side, se, share of leads changed, IMPs a side, se) of leading the smallest gap + scale x table[kind]."""
    gains, imps, changed = {}, {}, 0
    for o in sel:
        t = tab if by_scope is None else by_scope[scope_of(o)]
        adj = {c: g + scale * t[kind(c, o['hand'], o['trump'])] for c, g in o['gaps'].items()}
        best = min(adj.values())
        top = [c for c, v in adj.items() if v <= best + 1e-9]
        if o['played'] in top:
            continue
        changed += 1
        for b, est, prop, real, im, band in o['forks']:
            if b in top:
                gains[o['family']] = gains.get(o['family'], 0.) - real / prop / len(top)
                imps[o['family']] = imps.get(o['family'], 0.) - im / prop / len(top)
    N = len(sel)
    def tot(d):
        v = np.array(list(d.values()) + [0.] * (N - len(d)))
        return v.sum() / (2 * N), math.sqrt(N / (N - 1) * ((v ** 2).sum() - v.sum() ** 2 / N)) / (2 * N)
    return (*tot(gains), changed / N, *tot(imps))

if __name__ == '__main__':
    allr = recs
    print(len(allr), 'leads;', sum(len(o['forks']) for o in allr), 'lead forks;', {s: sum(o['set'] == s for o in allr) for s in sorted({o['set'] for o in allr})})
    tabs = {}
    for sc in ('all', 'suit', 'NT'):
        tabs[sc] = table([o for o in allr if sc == 'all' or scope_of(o) == sc], f'{sc} contracts')
    # cross-fitted rule: the table from one half of the deals, the rule scored on the other half
    fams = sorted({o['family'] for o in allr}); rng = np.random.default_rng(1); half = set(rng.permutation(fams)[:len(fams) // 2].tolist())
    A, B = [o for o in allr if o['family'] in half], [o for o in allr if o['family'] not in half]
    print('\nThe rule, table fitted on one half of the deals and scored on the other (both ways, pooled). Tricks and IMPs a side at one table:')
    for scale in (0.25, 0.5, 0.75, 1.0, 1.5):
        res = []
        for fit_on, score_on in ((A, B), (B, A)):
            by = {sc: dict(zip(KINDS, fit([o for o in fit_on if scope_of(o) == sc])[0])) for sc in ('suit', 'NT')}
            res.append((rule(score_on, None, scale, by), len(score_on)))
        n = sum(r[1] for r in res)
        g = sum(r[0][0] * r[1] for r in res) / n; se = math.sqrt(sum((r[0][1] * r[1]) ** 2 for r in res)) / n
        im = sum(r[0][3] * r[1] for r in res) / n; ise = math.sqrt(sum((r[0][4] * r[1]) ** 2 for r in res)) / n
        ch = sum(r[0][2] * r[1] for r in res) / n
        print(f'   scale {scale:4.2f}: changes {ch:.3f} of leads; {g:+.4f} +- {se:.4f} tricks a side; {im:+.4f} +- {ise:.4f} IMPs a side')
    if len(sys.argv) > 2:
        json.dump(tabs, open(sys.argv[2], 'w'), indent=1)
