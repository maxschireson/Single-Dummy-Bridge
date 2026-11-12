#!/usr/bin/env python3
"""Two nets' readings of the play on the same decisions (rows written by scripts/gen7_check.py inference --out).

  python infer_report.py NAME_A=ROWS_A.json[.gz] NAME_B=ROWS_B.json[.gz] [more pairs of files for the same two names ...]

Each rows file lists recorded deal-list decisions of Gen 6 seats (trick 7 on) with the log-probability of the true
layout under the scorer's weights and under scorer x the net's likelihood of the plays seen (exponent 0.5, floor
0.05: Gen 7's setting), and the double-dummy cost on the true deal of the card each weighting picks. Both runs
read the same tables in the same order, so their rows pair up; a run cut short by its time budget pairs on the
tables both finished. Errors are clustered by deal.
"""
import gzip
import json
import math
import sys

import numpy as np

KEY = 'play f0.05 t0.5'


def load(path):
    with (gzip.open(path, 'rt') if path.endswith('.gz') else open(path)) as f:
        return json.load(f)['rows']


def clustered(x, fam):
    by = {}
    for v, f in zip(x, fam):
        by.setdefault(f, []).append(v)
    totals, counts = np.array([sum(v) for v in by.values()]), np.array([len(v) for v in by.values()])
    mean = totals.sum() / counts.sum()
    se = math.sqrt(((totals - mean * counts) ** 2).sum() * len(by) / max(1, len(by) - 1)) / counts.sum()
    return mean, se


specs = [a.split('=', 1) for a in sys.argv[1:]]
names = list(dict.fromkeys(n for n, _ in specs))
assert len(names) == 2 and len(specs) % 2 == 0, 'two names, the same number of files each'
a_rows, b_rows = [], []
for (na, pa), (nb, pb) in zip(specs[0::2], specs[1::2]):
    ra, rb = load(pa), load(pb)
    n = 0
    while n < min(len(ra), len(rb)) and all(ra[n][k] == rb[n][k] for k in ('family', 'trick', 'listed', 'plays')) and abs(ra[n]['scorer'] - rb[n]['scorer']) < 1e-9:
        n += 1
    fams = {r['family'] for r in ra[:n]}
    last = ra[n - 1]['family'] if n and n < max(len(ra), len(rb)) else None    # the table in hand when the shorter run stopped may be incomplete
    keep = [i for i in range(n) if ra[i]['family'] != last] if last else list(range(n))
    a_rows += [ra[i] for i in keep]
    b_rows += [rb[i] for i in keep]
    print(f"{pa}: {len(ra)} rows, {pb}: {len(rb)} rows, paired {len(keep)} on {len({ra[i]['family'] for i in keep})} deals")
A, B = names
fam = [r['family'] for r in a_rows]
fmt = lambda m: f"{m[0]:+.4f} +- {m[1]:.4f}"
def block(rows_a, rows_b, fam, label):
    ga = np.array([r[KEY] - r['scorer'] for r in rows_a]); gb = np.array([r[KEY] - r['scorer'] for r in rows_b])
    ca = np.array([r['gen7_cost'] for r in rows_a]); cb = np.array([r['gen7_cost'] for r in rows_b]); c6 = np.array([r['gen6_cost'] for r in rows_a])
    print(f"\n== {label}: {len(fam)} decisions on {len(set(fam))} deals, {np.mean([r['listed'] for r in rows_a]):.0f} layouts listed on average")
    print(f"  log-probability of the true layout: uniform {np.mean([r['uniform'] for r in rows_a]):.3f}, scorer {np.mean([r['scorer'] for r in rows_a]):.3f}")
    print(f"  gain over the scorer's weights, nats: {A} {fmt(clustered(ga, fam))} | {B} {fmt(clustered(gb, fam))} | {B} minus {A} {fmt(clustered(gb - ga, fam))}")
    print(f"  true layout made more likely: {A} {np.mean(ga > 0):.3f} | {B} {np.mean(gb > 0):.3f}")
    print(f"  double-dummy cost of the card picked: scorer weights {fmt(clustered(c6, fam))} | with {A} {fmt(clustered(ca, fam))} | with {B} {fmt(clustered(cb, fam))}")
    print(f"  cost saved against the scorer's weights: {A} {fmt(clustered(c6 - ca, fam))} | {B} {fmt(clustered(c6 - cb, fam))} | {B} minus {A} {fmt(clustered(ca - cb, fam))}")
    print(f"  picks a different card set than the scorer's weights: {A} {np.mean([r['gen6_cards'] != r['gen7_cards'] for r in rows_a]):.4f} | {B} {np.mean([r['gen6_cards'] != r['gen7_cards'] for r in rows_b]):.4f}"
          f" | the two nets pick different card sets: {np.mean([x['gen7_cards'] != y['gen7_cards'] for x, y in zip(rows_a, rows_b)]):.4f}")
block(a_rows, b_rows, fam, 'all decisions')
for label, test in (('hidden seats played by Gen 6', lambda r: r['hidden_gen6']), ('a hidden seat played by another bot', lambda r: not r['hidden_gen6']),
                    ('declarer deciding', lambda r: r['declaring']), ('defender deciding', lambda r: not r['declaring'])):
    idx = [i for i, r in enumerate(a_rows) if test(r)]
    if len(idx) >= 50:
        block([a_rows[i] for i in idx], [b_rows[i] for i in idx], [fam[i] for i in idx], label)
for k in range(7, 13):
    idx = [i for i, r in enumerate(a_rows) if r['trick'] == k]
    if len(idx) >= 50:
        ga = np.array([a_rows[i][KEY] - a_rows[i]['scorer'] for i in idx]); gb = np.array([b_rows[i][KEY] - b_rows[i]['scorer'] for i in idx]); f = [fam[i] for i in idx]
        print(f"trick {k:2d}: {len(idx):5d} decisions | gain {A} {fmt(clustered(ga, f))} | {B} {fmt(clustered(gb, f))} | {B} minus {A} {fmt(clustered(gb - ga, f))}")
