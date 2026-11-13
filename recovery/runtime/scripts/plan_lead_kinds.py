#!/usr/bin/env python3
"""Opening-lead ceiling by kind of lead: where real play (Gen 6 playing on) departs from double dummy.

  python scripts/plan_lead_kinds.py ceilLead.json EPISODES_DIR      (rows of scripts/plan_ceiling.py --leads --max-ply 0)

For each fork pair (lead A played, lead B forced) the correction is (playout A - B) - (double dummy A - B) on the same
layouts, in tricks for the leader's side: positive = double dummy flatters B against A."""
import gzip, json, sys, glob, math, collections
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.core import card, Board
rows = json.load(open(sys.argv[1]))['rows']
files = {}
for f in glob.glob(sys.argv[2] + '/*.json.gz'):
    files[f] = None
want = {r['family'] for r in rows}
by_family = {}
for f in sorted(files):
    d = json.load(gzip.open(f, 'rt'))
    if d['family'] in want:
        by_family[d['family']] = d
    if len(by_family) == len(want):
        break
RANK = '23456789TJQKA'
def kind(c, hand, trump):
    suit = c // 13
    held = sorted([x % 13 for x in hand if x // 13 == suit], reverse=True)
    n, r = len(held), c % 13
    hon = [x for x in held if x >= 9]                      # J or higher
    if trump is not None and suit == trump:
        return 'trump'
    if n == 1:
        return 'singleton'
    if r == 12:
        return 'ace'
    if r >= 9 and len(held) >= 2 and held.index(r) + 1 < n and held[held.index(r) + 1] == r - 1:
        return 'top of touching honours'
    if r >= 9:
        return 'honour, not touching'
    if n == 2:
        return 'small from a doubleton'
    if hon:
        return 'small from an honour'
    return 'small from small cards'
out = []
for r in rows:
    d = by_family.get(r['family'])
    if d is None:
        continue
    e = d['unique_tables'][r['table']]
    root, fork = e['tables'][r['table_a']], e['tables'][r['table_b']]
    a, b = card(root['actions'][0]['card']), card(fork['actions'][0]['card'])
    seat = 'NESW'.index(root['actions'][0]['seat'])
    board = Board.from_dict(e['board'])
    hand = list(board.hands[seat])
    trump = board.contract.trump
    trump = None if trump is None or trump > 3 else trump
    sh = np.array(r['worlds']['share'], float); sh /= sh.sum()
    roll = np.array(r['worlds']['roll'], float); dd = np.array(r['worlds']['dd'], float)
    c = float(sh @ ((roll[:, 0] - roll[:, 1]) - (dd[:, 0] - dd[:, 1])))
    out.append((kind(a, hand, trump), kind(b, hand, trump), c, float(sh @ (roll[:, 0] - roll[:, 1])), float(sh @ (dd[:, 0] - dd[:, 1])), r['estimated'], 'NT' if trump is None else 'suit', r['family'], r['final']))
print(len(out), 'pairs')
kinds = sorted({k for o in out for k in o[:2]})
for scope in ('all', 'NT', 'suit'):
    sel = [o for o in out if scope == 'all' or o[6] == scope]
    if len(sel) < 30:
        continue
    # a slope on the double-dummy gap comes first: real play shrinks every gap, and without the slope that shows up as
    # a 'kind' effect for the kinds that are mostly played (or mostly forced)
    X = np.zeros((len(sel), len(kinds) + 1)); y = np.array([o[2] for o in sel])
    for i, o in enumerate(sel):
        X[i, kinds.index(o[1])] += 1; X[i, kinds.index(o[0])] -= 1; X[i, -1] = o[4]
    R = 1e-6 * np.eye(len(kinds) + 1)
    def solve(X, y):
        b = np.linalg.solve(X.T @ X + R, X.T @ y)
        return np.append(b[:-1] - b[:-1].mean(), b[-1])
    full = solve(X, y); beta = full[:-1]
    fams = sorted({o[7] for o in sel}); idx = {f: [] for f in fams}
    for i, o in enumerate(sel):
        idx[o[7]].append(i)
    rng = np.random.default_rng(0); reps = []
    for _ in range(300):
        pick = np.concatenate([idx[fams[j]] for j in rng.integers(0, len(fams), len(fams))])
        reps.append(solve(X[pick], y[pick]))
    reps = np.array(reps); se = reps.std(0)[:-1]
    print(f'\n{scope}: played-out gap = ({1 + full[-1]:.3f} +- {reps.std(0)[-1]:.3f}) x double-dummy gap on the same layouts + kinds')
    if 'ace' in kinds and 'small from an honour' in kinds:
        ia, ih = kinds.index('ace'), kinds.index('small from an honour')
        print(f'   ace minus small from an honour: {beta[ia] - beta[ih]:+.3f} +- {np.std(reps[:, ia] - reps[:, ih]):.3f}')
    print(f'\n{scope}: {len(sel)} pairs. How much double dummy flatters a lead of each kind against real play (tricks; + = worse in real play than double dummy says), and how often it was the lead played / the forced lead:')
    for k, bta, s_ in sorted(zip(kinds, beta, se), key=lambda t: -t[1]):
        na, nb = sum(o[0] == k for o in sel), sum(o[1] == k for o in sel)
        print(f'   {k:28s} {bta:+.3f} +- {s_:.3f}   played {na:4d}, forced {nb:4d}')
