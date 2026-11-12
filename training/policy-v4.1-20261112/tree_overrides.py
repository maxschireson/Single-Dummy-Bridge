#!/usr/bin/env python3
"""What the tree's overrides really gained, from the audit tables of Gen 7 boards.

  python tree_overrides.py PAIRS.npz [PAIRS.npz ...]        (files made by scripts/gen7_pairs.py; the first is named "first")

In a Gen 7 board with `tree_audit`, an audit whose two cards the search did not rate level is an override: the bot played
the tree's card, and the audit table played the card it would have played without the tree (`audit_reference:
without-tree`), from the same position, with the same bots to the end. In the pairs files those are the audits
(source 0) of a Gen 7 bot (bot 2) whose played card has the larger search gap. This prints the played card's result
minus the reference card's, in tricks and IMPs, with standard errors that take the deal as the unit.
"""
import math
import sys

import numpy as np


def clustered(x, fam):
    _, inv = np.unique(fam, return_inverse=True)
    t, c = np.bincount(inv, x), np.bincount(inv)
    m, k = t.sum() / c.sum(), len(c)
    return m, math.sqrt(((t - m * c) ** 2).sum() * k / (k - 1)) / c.sum() if k > 1 else float('nan'), k


def main():
    parts = []
    for n, path in enumerate(sys.argv[1:]):
        with np.load(path) as z:
            p = {k: z[k] for k in z.files}
        m = (p['bot'] == 2) & (p['source'] == 0) & (p['est_a'] > p['est_b'] + 1e-9)
        print(f"{path}: {len(p['row'])} pairs, {int((p['bot'] == 2).sum())} at a Gen 7 bot's decisions, {int(m.sum())} overrides")
        parts.append(dict(first=np.full(m.sum(), n == 0), fam=p['family'][p['deal']][m], y=p['realized'][m].astype(float), imps=p['imps'][m].astype(float),
                          gap=(p['est_a'] - p['est_b'])[m], trick=p['ply'][m] // 4 + 1))
    c = {k: np.concatenate([x[k] for x in parts]) for k in parts[0]}
    print('overrides by trick:', {int(t): int(n) for t, n in zip(*np.unique(c['trick'], return_counts=True))})
    for label, m in (('all files', np.ones(len(c['y']), bool)), ('the first file', c['first']), ('the other files', ~c['first']),
                     ('gap up to 0.1', c['gap'] <= .1), ('gap over 0.1', c['gap'] > .1)):
        if m.sum() < 30:
            continue
        ok = np.isfinite(c['imps'][m])
        a, b = clustered(c['y'][m], c['fam'][m]), clustered(c['imps'][m][ok], c['fam'][m][ok])
        print(f"{label:16s} {int(m.sum()):5d} overrides on {a[2]:4d} deals | played card minus the search's card {a[0]:+.4f} +- {a[1]:.4f} tricks, {b[0]:+.3f} +- {b[1]:.3f} IMPs"
              f" | better {np.mean(c['y'][m] > 0):.1%}, worse {np.mean(c['y'][m] < 0):.1%} | search's gap {c['gap'][m].mean():.3f}")


if __name__ == '__main__':
    main()
