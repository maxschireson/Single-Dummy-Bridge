#!/usr/bin/env python3
"""Where the tricks go: every card played with a choice in recorded tables, rated by double dummy on the deal as it lay.

  python training/rollout-loop-20261113/bench/dd_ledger.py EPISODES_DIR [EPISODES_DIR ...] [--boards N] [--workers K]

For each card: the tricks its side could still take with best play by all four hands seen (double dummy), before and
after it. The difference is what the card gave up. Summed by bot, by what the seat was doing (the opening lead,
declaring, defending) and by trick. A card "turns the contract" when the contract was making before it and is not
after (declaring side), or was failing before it and is not after (defence): Max, 04:28 UTC on 14 November, "don't go
down in a cold game or slam".

Double dummy sees all four hands, so this is hindsight. A card that gives up a trick here may have been right on what
its player could know, and a bot that itself chooses by double dummy on sampled layouts (Gen 8) is flattered by the
measure. It says where a bot's tricks go and how two bots differ on the same deals, not what a card was worth.

For a rollout bot the tricks given up are also split by where a double-dummy best card stood at that decision: not among
the rollouts' candidates (the table net's prior left it out), a candidate the rollouts rated lower, or a card not chosen
by rollouts at all (a claim, a guard, the net's own card).
"""
import argparse
from collections import defaultdict
import glob
import gzip
import json
from multiprocessing import Pool
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bridge_harness.core import Board, Game, card      # noqa: E402

BUCKETS = (('lead', 0, 0), ('tricks 1-4', 1, 4), ('tricks 5-8', 5, 8), ('tricks 9-13', 9, 13))
_DDS = None


def bucket(trick, lead):
    return 'lead' if lead else next(name for name, lo, hi in BUCKETS[1:] if lo <= trick <= hi)


def one_file(path):
    global _DDS
    if _DDS is None:
        from bridge_harness.dds import DDS
        _DDS = DDS()
    d = json.load(gzip.open(path, 'rt'))
    who = {'candidate': d['candidate'], 'opponent': d['opponent']}
    out = []
    for e in d['unique_tables'].values():
        if e.get('schema_version') == 'v4-passed-out-v1' or not e.get('tables'):
            continue
        board = Board.from_dict(e['board'])
        target = board.contract.level + 6
        for table in e['tables']:
            if table.get('depth', 0) or table.get('fork_kind'):        # a fork of a record, not the table as played
                continue
            g = Game(board)
            rows = []
            for a in table['actions']:
                o = g.observation()
                x = card(a['card'])
                if len(o.legal) > 1:
                    values, _ = _DDS.solve(tuple(tuple(h) for h in g.hands), o.contract.trump, o.leader, list(o.trick))
                    best, got = max(values[y] for y in o.legal), values[x]
                    declaring = o.actor % 2 == o.contract.declarer % 2
                    left = 13 - len(o.history) // 4
                    total = lambda t: o.declarer_tricks + (t if declaring else left - t)      # declarer's final tricks
                    before, after = total(best), total(got)
                    turned = (before >= target > after) if declaring else (before < target <= after)
                    note = a.get('x8') or {}
                    if note.get('mode') == 'rollout' and note.get('runs'):       # a rollout decision: was a best card among its candidates?
                        candidates = {card(y) for run in note['runs'] for y in run}
                        kind = 'a candidate, rated lower' if any(values[y] == best for y in candidates & set(o.legal)) else 'not a candidate'
                    else:
                        kind = 'no rollout (%s)' % (note.get('mode') or ('search' if a.get('estimates') else 'other'))
                    rows.append((who.get(a.get('player') or a.get('role'), '?'), 'lead' if not o.history else 'declaring' if declaring else 'defending',
                                 bucket(len(o.history) // 4 + 1, not o.history), best - got, bool(turned), kind))
                g.play(x)
            out.append(rows)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('episodes', type=Path, nargs='+')
    p.add_argument('--boards', type=int, default=0, help='at most this many record files a folder (0 = all)')
    p.add_argument('--workers', type=int, default=2)
    a = p.parse_args()
    files = []
    for folder in a.episodes:
        found = sorted(glob.glob(str(folder / '*.json.gz')))
        files += found[:a.boards] if a.boards else found
    tables = defaultdict(int)
    lost, cards, turned, sizes = defaultdict(float), defaultdict(int), defaultdict(int), defaultdict(lambda: defaultdict(int))
    why = defaultdict(float)
    with Pool(a.workers) as pool:
        for per_file in pool.imap_unordered(one_file, files, chunksize=4):
            for rows in per_file:
                for bot in {r[0] for r in rows}:
                    tables[bot] += 1
                for bot, role, when, loss, turn, kind in rows:
                    for key in ((bot, role, when), (bot, role, 'all'), (bot, 'all', 'all')):
                        lost[key] += loss
                        cards[key] += 1
                        turned[key] += turn
                    sizes[bot][min(int(loss), 3)] += 1
                    if loss > 0:
                        why[(bot, 'early' if when in ('lead', 'tricks 1-4') else 'later', kind)] += loss
                        why[(bot, 'all', kind)] += loss
    print(f'{len(files)} record files; tables by bot: {dict(tables)}')
    print('double-dummy tricks given up A TABLE (hindsight on the deal as it lay), and cards that turned the contract a 100 tables')
    for bot in sorted(tables):
        n = tables[bot]
        print(f'\n{bot}: {n} tables | all cards {lost[(bot, "all", "all")] / n:.3f} tricks a table | turned the contract {100 * turned[(bot, "all", "all")] / n:.1f} a 100 tables'
              f' | cards giving up 0/1/2/3+ tricks: {[sizes[bot][k] for k in range(4)]}')
        for role in ('lead', 'declaring', 'defending'):
            parts = [f'{when} {lost[(bot, role, when)] / n:.3f}' for when in [b[0] for b in BUCKETS] if cards[(bot, role, when)]]
            print(f'  {role:9s} {lost[(bot, role, "all")] / n:.3f} tricks a table, turned {100 * turned[(bot, role, "all")] / n:.1f} a 100 | ' + ' | '.join(parts))
        kinds = sorted({k[2] for k in why if k[0] == bot}, key=lambda k: -why[(bot, 'all', k)])
        if any('candidate' in k for k in kinds):       # a rollout bot: of the tricks given up, where the best card stood
            print('  of the tricks given up (a table: all, the lead and tricks 1-4, later): ' + '; '.join(
                f'{k} {why[(bot, "all", k)] / n:.3f}, {why[(bot, "early", k)] / n:.3f}, {why[(bot, "later", k)] / n:.3f}' for k in kinds))


if __name__ == '__main__':
    main()
