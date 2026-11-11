"""Summarise info_test.py rows: nats about the true layout beyond cards and show-outs, per decision.

  python analyze_info.py rows.jsonl[.gz] [...] [--base=v0] [--by-trick]

Standard errors are clustered by board (all decisions of one table share its deal).
"""
import gzip
import json
import math
import sys
from collections import defaultdict

import numpy as np

args = [x for x in sys.argv[1:] if not x.startswith('--')]
base = next((x.split('=')[1] for x in sys.argv[1:] if x.startswith('--base=')), 'v0')
by_trick = '--by-trick' in sys.argv
rows = [json.loads(l) for p in args for l in (gzip.open(p, 'rt') if p.endswith('.gz') else open(p))]
scorers = [k for k in rows[0] if isinstance(rows[0][k], dict)]
alphas = list(rows[0][scorers[0]])


def clustered(values, groups):
    """Mean per decision and its standard error, clustered by group."""
    tot, cnt = defaultdict(float), defaultdict(int)
    for v, g in zip(values, groups):
        tot[g] += v
        cnt[g] += 1
    t = np.array([tot[g] for g in tot])
    c = np.array([cnt[g] for g in tot])
    m = t.sum() / c.sum()
    G = len(t)
    se = math.sqrt(((t - m * c) ** 2).sum() * G / (G - 1)) / c.sum() if G > 1 else float('nan')
    return m, se


def report(sub, title):
    g = [(r['ep'], r['table']) for r in sub]
    u = np.array([r['uniform'] for r in sub])
    print(f'== {title}: {len(sub)} decisions on {len(set(g))} boards; median layouts listed {int(np.median([r["n"] for r in sub]))}, '
          f'median fitting the auction {int(np.median([r["n_fit"] for r in sub]))}')
    ex = np.array([r['exact'] for r in sub]) - u
    m, s = clustered(ex, g)
    print(f'   exact bidder list        {m:.3f} +- {s:.3f}')
    for name in scorers:
        line = f'   {name:24s}'
        for al in alphas:
            v = np.array([r[name][al] for r in sub]) - u
            m, s = clustered(v, g)
            line += f' a={al}: {m:.3f}+-{s:.3f}'
        print(line)
    if base in scorers:
        for name in scorers:
            if name == base:
                continue
            d = np.array([r[name]['1.0'] - r[base]['1.0'] for r in sub])
            m, s = clustered(d, g)
            best = max(alphas, key=lambda al: np.mean([r[name][al] for r in sub]))
            d2 = np.array([r[name][best] - r[base]['1.0'] for r in sub])
            m2, s2 = clustered(d2, g)
            print(f'   {name} - {base} (both a=1): {m:+.3f} +- {s:.3f} | {name} at its best a={best} - {base} a=1: {m2:+.3f} +- {s2:.3f}')
        d = np.array([r['exact'] - r[base]['1.0'] for r in sub])
        m, s = clustered(d, g)
        print(f'   exact - {base}: {m:+.3f} +- {s:.3f} (what a perfect scorer would add)')


report(rows, 'all tricks')
if by_trick:
    for t in sorted({r['trick'] for r in rows}):
        report([r for r in rows if r['trick'] == t], f'trick {t}')
