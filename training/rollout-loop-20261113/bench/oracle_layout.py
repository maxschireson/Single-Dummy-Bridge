#!/usr/bin/env python3
"""Where a rollout bot's tricks go: in the layouts it rolls out, or in the rollouts themselves?

  SURE_BIN=... python training/rollout-loop-20261113/bench/oracle_layout.py RUN_DIR --source CAPSULE/recovery \\
      [--bot candidate] [--tables 200] [--to-trick 4] [--copies 64] [--workers 2]

RUN_DIR is a finished match with --episodes (its manifest.json holds the bots as played). At each recorded decision of
the bot up to `--to-trick` that its rollouts decided between two or more candidates, three cards are rated by double
dummy on the deal as it lay (tricks given up, as bench/dd_ledger.py):

  played   the card in the record
  again    the bot's card at that position now, on layouts it draws itself: a control, it should give up what
           `played` does
  oracle   the bot's card when every layout it rolls out IS the deal as it lay (`--copies` rollouts of the true deal;
           the simulated seats still play by the net, each from its own view)

If `oracle` gives up little, the rollouts rank the cards well once the cards are known, and what `played` gives up comes
from not knowing them: the layouts drawn, or what nobody could know. If `oracle` still gives up much, the rollouts
misjudge cards even on the true deal: the simulated play is the limit. The bot never sees the deal in a match; this is a
bench on recorded positions.
"""
import argparse
from collections import defaultdict
import glob
import gzip
import json
from multiprocessing import Pool
from pathlib import Path
import random
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bridge_harness import x8_player                    # noqa: E402
from bridge_harness.core import Board, Game, card      # noqa: E402

STATE = {}


class Oracle(x8_player.X8Player):
    """X8Player whose rollouts run on the deal as it lay when `truth` is set."""
    truth, copies = None, 64

    def read_layouts(self, o, view, source, rng, n):
        if self.truth is None:
            return super().read_layouts(o, view, source, rng, n)
        k = self.copies
        return [self.truth] * k, np.full(k, 1. / k), dict(source='oracle', draws=k, effective=float(k))


def start(run, source, role, copies):
    from bridge_harness.dds import DDS
    m = json.loads((Path(run) / 'manifest.json').read_text())
    a, b = m['roster'][:2]
    me, other = (a, b) if role == 'candidate' else (b, a)
    p = Oracle(m['bots'][me], source, m['bots'][m['audit_references'][me]])
    p.copies = copies
    p.meet(other)
    STATE.update(player=p, dds=DDS(), role=role, me=me)


def given_up(values, o, x):
    return max(values[y] for y in o.legal) - values[x]


def one_file(job):
    path, to_trick = job
    p, dds, role = STATE['player'], STATE['dds'], STATE['role']
    d = json.load(gzip.open(path, 'rt'))
    rows = []
    for e in d['unique_tables'].values():
        if e.get('schema_version') == 'v4-passed-out-v1' or not e.get('tables'):
            continue
        board = Board.from_dict(e['board'])
        for ti, table in enumerate(e['tables']):
            if table.get('depth', 0) or table.get('fork_kind'):
                continue
            g = Game(board)
            for ai, a in enumerate(table['actions']):
                o = g.observation()
                x = card(a['card'])
                note = a.get('x8') or {}
                trick = len(o.history) // 4 + 1
                if (a.get('player') or a.get('role')) == role and note.get('mode') == 'rollout' and len(note.get('cards') or ()) > 1 \
                        and trick <= to_trick and len(o.legal) > 1:
                    world = tuple(tuple(sorted(h)) for h in g.hands)
                    values, _ = dds.solve(world, o.contract.trump, o.leader, list(o.trick))
                    seed = hash((board.id, ti, ai)) & 0xffffffff
                    p.truth = None
                    again = p.choose(o, random.Random(seed))
                    p.truth = world
                    oracle = p.choose(o, random.Random(seed))
                    p.truth = None
                    kind = 'lead' if not o.history else 'declaring' if o.actor % 2 == o.contract.declarer % 2 else 'defending'
                    modes = ((again.details.get('x8') or {}).get('mode'), (oracle.details.get('x8') or {}).get('mode'))
                    rows.append((kind, given_up(values, o, x), given_up(values, o, again.card), given_up(values, o, oracle.card),
                                 x == again.card, modes))
                g.play(x)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path)
    ap.add_argument('--source', required=True)
    ap.add_argument('--bot', default='candidate', help="'candidate' or 'opponent': whose decisions")
    ap.add_argument('--tables', type=int, default=200, help='record files read (a board each, two tables)')
    ap.add_argument('--to-trick', type=int, default=4)
    ap.add_argument('--copies', type=int, default=64)
    ap.add_argument('--workers', type=int, default=2)
    a = ap.parse_args()
    files = sorted(glob.glob(str(a.run / 'episodes' / '*.json.gz')))[:a.tables]
    total, n, same, modes = defaultdict(lambda: np.zeros(3)), defaultdict(int), 0, defaultdict(int)
    square = defaultdict(lambda: np.zeros(3))
    with Pool(a.workers, initializer=start, initargs=(str(a.run), a.source, a.bot, a.copies)) as pool:
        for rows in pool.imap_unordered(one_file, [(f, a.to_trick) for f in files], chunksize=2):
            for kind, played, again, oracle, kept, mode in rows:
                v = np.array([played, again, oracle], float)
                for key in (kind, 'all'):
                    total[key] += v
                    square[key] += (v - v[[2, 2, 2]]) ** 2          # for the error of (played - oracle) and (again - oracle)
                    n[key] += 1
                same += kept
                modes[mode] += 1
    print(f'{len(files)} boards of {a.run.name}; decisions of the {a.bot} by rollouts with a choice, to trick {a.to_trick}: {n["all"]}')
    print(f'the bot plays the recorded card again at {100 * same / max(n["all"], 1):.0f}% of them; how each card was chosen (again, oracle): {dict(modes)}')
    print('double-dummy tricks given up A DECISION (hindsight)     played   again   oracle | oracle below again by')
    for key in ('lead', 'declaring', 'defending', 'all'):
        if n[key]:
            m = total[key] / n[key]
            gap = m[1] - m[2]
            se = float(np.sqrt(max(square[key][1] / n[key] - gap ** 2, 0.) / n[key]))
            print(f'  {key:9s} {n[key]:6d} decisions                         {m[0]:.4f}   {m[1]:.4f}   {m[2]:.4f} | {gap:+.4f} +- {se:.4f}')


if __name__ == '__main__':
    main()
