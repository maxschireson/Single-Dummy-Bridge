#!/usr/bin/env python3
"""Where a bot and its opponent first play differently, and how those boards come out.

  python training/rollout-loop-20261113/first_divergence.py RUN=DIR [RUN=DIR ...] --out where.json

A match board is played at two tables with the seats swapped, the same auction at both. The play is the same card for
card until some seat plays a different card at one table than at the other. At that card the two bots sat in the same
seat with the same hand, the same dummy and the same play before them: one position, two choices. This script finds
that card on every board of a run's full records (`episodes/`) and sorts the boards by where it falls:

  none          the two tables are the same play to the end (the board is flat)
  lead          the opening lead
  declaring     a card of the declaring side (declarer's hand or dummy's), by trick
  defending     a defender's card after the lead, by trick

For each group: boards, the IMPs to the first-named bot summed over them and per board, and the group's share of the
run's total. The first difference is where the two plays part, not a verdict on that card: the IMPs a board ends with
also carry every later difference. It says where the two bots disagree and how those boards go.

Cards that do the same job are not a difference: a card is known here by its suit and by how many cards of that suit
still out against the hand (in the other hands or on the table) outrank it, so the king and the queen from king-queen
are one card, and stay one after either has gone.
"""
import argparse
import collections
import gzip
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bridge_harness.core import Board, Game, card  # noqa: E402

BANDS = ((1, 1), (2, 3), (4, 6), (7, 9), (10, 13))


def job(game, x):
    """What the card does for the hand that plays it: its suit and how many live cards of the suit outside that hand
    outrank it."""
    o = game.observation()
    out = [c for seat, hand in enumerate(game.hands) if seat != o.actor for c in hand] + [c for _, c in o.trick]
    return x // 13, sum(1 for c in out if c // 13 == x // 13 and c > x)


def first_difference(board, a, b):
    """(ply, the seat's side is declaring) of the first card that does a different job at the two tables, or None."""
    ga, gb = Game(board), Game(board)
    for k, (xa, xb) in enumerate(zip(a, b)):
        if job(ga, xa) != job(gb, xb):
            o = ga.observation()
            return k, o.controller % 2 == board.contract.declarer % 2
        ga.play(xa)
        gb.play(xb)
    return None


def group(found):
    if found is None:
        return 'none'
    ply, declaring = found
    if ply == 0:
        return 'lead'
    trick = ply // 4 + 1
    lo, hi = next(band for band in BANDS if band[0] <= trick <= band[1])
    return f"{'declaring' if declaring else 'defending'}, trick{'s' if hi > lo else ''} {lo}{'' if hi == lo else f' to {hi}'}"


def read(path):
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    imps = (d['regimes'].get('common') or {}).get('imps')
    keys = [d['bidding'][f'common/{k}']['table'] for k in (0, 1) if f'common/{k}' in d['bidding']]
    if imps is None or len(keys) != 2:
        return None
    tables = [d['unique_tables'][k] for k in keys]
    if any(t.get('schema_version') == 'v4-passed-out-v1' for t in tables):
        return 'passed out', 0
    plays = [[card(x['card']) for x in t['tables'][0]['actions']] for t in tables]
    return group(first_difference(Board.from_dict(tables[0]['board']), *plays)), imps


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('runs', nargs='+', help='NAME=DIR[,DIR...]: a run and its folders (each with episodes/)')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    report = dict(what='first_divergence.py: see its docstring', runs={})
    for item in a.runs:
        name, folders = item.split('=', 1)
        by = collections.defaultdict(list)
        for folder in folders.split(','):
            for f in sorted((Path(folder) / 'episodes').glob('*.json.gz')):
                got = read(f)
                if got is not None:
                    by[got[0]].append(got[1])
        boards = sum(len(v) for v in by.values())
        total = sum(sum(v) for v in by.values())
        rows = []
        order = ['none', 'passed out', 'lead'] + [f"{side}, trick{'s' if hi > lo else ''} {lo}{'' if hi == lo else f' to {hi}'}"
                                                   for side in ('declaring', 'defending') for lo, hi in BANDS]
        for g in order:
            v = by.get(g)
            if not v:
                continue
            n, s = len(v), sum(v)
            m = s / n
            se = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1) / n) if n > 1 else float('nan')
            rows.append(dict(group=g, boards=n, imps=s, imps_a_board=round(m, 3), se=round(se, 3) if n > 1 else None,
                             of_all_boards=round(s / boards, 4)))
        report['runs'][name] = dict(boards=boards, imps_a_board=round(total / max(boards, 1), 4), groups=rows)
        print(f'{name}: {boards} boards, {total / max(boards, 1):+.3f} IMPs a board to the first-named bot')
        print(f"  {'first difference':26s} {'boards':>6s} {'IMPs':>6s} {'a board':>16s} {'of the total':>13s}")
        for r in rows:
            mean = f"{r['imps_a_board']:+.2f} +- {r['se']:.2f}" if r['se'] is not None else f"{r['imps_a_board']:+.2f}"
            print(f"  {r['group']:26s} {r['boards']:6d} {r['imps']:+6d} {mean:>16s} {r['of_all_boards']:+13.3f}")
    a.out.write_text(json.dumps(report, indent=1) + '\n')


if __name__ == '__main__':
    main()
