#!/usr/bin/env python3
"""Pool the feature forks of 8X matches (scripts/x8_match.py --feature-forks): what each 8X feature's changed cards
gained over the card plain Gen 8 would have played, by feature and contract class.

  python scripts/x8_forks.py DIR [DIR ...]

A fork is one decision where a feature changed the card; both cards were played out from that position by the same
bots. Its value is the IMPs, to the deciding side, of the 8X card's table over plain Gen 8's (gain_imps of
bridge_harness.fork_audit). Errors take boards as the unit (several forks of one board are not independent). "A
board" divides by every board of the match, so it is the features' contribution to the match's IMPs a board on the
first-named bot's side, if the forks' effects added up (they need not: a later fork starts from the 8X line).
"""
import json
import math
from pathlib import Path
import sys

import numpy as np


def clustered(values, boards, total):
    """(mean a fork, its error; sum over the match a board, its error), boards as the unit."""
    by = {}
    for v, b in zip(values, boards):
        by.setdefault(b, []).append(v)
    sums = np.array([sum(x) for x in by.values()], float)
    counts = np.array([len(x) for x in by.values()], float)
    n, g = counts.sum(), len(sums)
    if not n:
        return None
    mean = sums.sum() / n
    se = math.sqrt(g / max(1, g - 1) * ((sums - mean * counts) ** 2).sum()) / n
    per = np.concatenate([sums, np.zeros(max(0, total - g))])
    return mean, se, per.mean(), per.std(ddof=1) / math.sqrt(len(per)) if len(per) > 1 else 0.


def main():
    rows = []
    for d in sys.argv[1:]:
        for line in (Path(d) / 'results.jsonl').read_text().splitlines():
            r = json.loads(line)
            rows.append((d, r))
    boards = len(rows)
    forks = [(f'{d}#{r["index"]}', *f) for d, r in rows for f in (r.get('search') or {}).get('x8_forks') or ()]
    print(f'{boards} boards, {len(forks)} feature forks')
    if not forks:
        return

    def line(name, sub):
        got = clustered([f[4] for f in sub], [f[0] for f in sub], boards)
        if got is None:
            return
        won = sum(f[4] > 0 for f in sub)
        lost = sum(f[4] < 0 for f in sub)
        print(f'  {name:34s} forks {len(sub):5d} (better {won}, worse {lost}): {got[0]:+.3f} +- {got[1]:.3f} IMPs a fork; '
              f'{got[2]:+.4f} +- {got[3]:.4f} a board')

    groups = ((1, 3), (4, 6), (7, 9), (10, 13))
    line('all', forks)
    for cls in ('partscore', 'game', 'doubled'):
        line(f'  {cls}', [f for f in forks if f[2] == cls])
    for trick in range(1, 14):
        line(f'  trick {trick}', [f for f in forks if f[3] == trick])
    for feature in sorted({x for f in forks for x in f[1].split('+')}):
        sub = [f for f in forks if feature in f[1].split('+')]
        line(f'with {feature}', sub)
        for cls in ('partscore', 'game', 'doubled'):
            line(f'  {cls}', [f for f in sub if f[2] == cls])
        for lo, hi in groups:
            line(f'  tricks {lo}-{hi}', [f for f in sub if lo <= f[3] <= hi])
    big = sorted(forks, key=lambda f: -abs(f[4]))[:5]
    line('all, 5 largest swings left out', [f for f in forks if f not in big])


if __name__ == '__main__':
    main()
