#!/usr/bin/env python3
"""Which simulated seats give the rollouts the truest values? Recorded rollout decisions played again, on the same
layouts, with the simulated seats set other ways (Max, 17:11 UTC on 14 November: "Should we experiment with different
rollout mechanisms?"; bench/value_check.py found the values optimistic for the side deciding).

  SURE_BIN=... python training/rollout-loop-20261113/bench/seat_variants.py RUN_DIR [RUN_DIR ...] --source CAPSULE/recovery \\
      [--bot candidate] [--boards 100] [--every 3] [--workers 2] [--out rows.jsonl] [--lead]

RUN_DIR is a match played with --episodes (its manifest.json holds the bots as played; several folders of one match's
shards may be given). At a sample of the bot's recorded rollout decisions the bot decides again under each setting below,
every candidate on every layout (no race), all settings on the SAME layouts (drawn once, as the bot draws them). Scored:

  values    declarer's tricks the rollouts expect with the card that WAS played at the table, against what declarer took
            there: the level error by what the seat was doing, and the squared error against the plain draw's, decision by
            decision (the contract's chance likewise: the Brier score). The table's result is one finish of the hand, so a
            single decision says little; the difference between two settings on the same decisions is what is read.
  choices   how often the setting plays another card than the plain draw does, and the tricks each card gives up by
            double dummy on the deal as it lay (hindsight, as bench/dd_ledger.py; a measurement, never an input).

A setting whose values are nearer the table's results simulates the players better. That is not yet a better card: the
choice turns on the differences between candidates, which the double-dummy column and then a match must show.
"""
import argparse
import base64
from collections import defaultdict
from dataclasses import replace
import glob
import gzip
import json
import math
from multiprocessing import Pool
from pathlib import Path
import random
import sys
import time
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from bridge_harness import x8_player                    # noqa: E402
from bridge_harness.core import Board, Game, card      # noqa: E402

VARIANTS = (
    ('draw (as played)', dict()),
    ('top card', dict(seat='top')),
    ('draw, power 2', dict(power=2.)),
    ('draw, cut 0.25', dict(cut=.25)),
    ('others top, own drawn', dict(seat_other='top')),
    ('own top, others drawn', dict(seat='top', seat_other='draw', power_other=1.)),
)
STATE = {}


class Replay(x8_player.X8Player):
    """X8Player that draws a decision's layouts once and gives them to every setting."""
    token, kept = None, None

    def read_layouts(self, o, view, source, rng, n):
        if self.kept is not None and self.kept[0] == self.token:
            return self.kept[1]
        out = super().read_layouts(o, view, source, rng, n)
        self.kept = (self.token, out)
        return out


def start(run, source, role):
    from bridge_harness.dds import DDS
    m = json.loads((Path(run) / 'manifest.json').read_text())
    a, b = m['roster'][:2]
    me, other = (a, b) if role == 'candidate' else (b, a)
    p = Replay(m['bots'][me], source, m['bots'][m['audit_references'][me]])
    p.meet(other)
    base = p.x8
    configs = []
    for _, change in VARIANTS:
        stages = tuple(replace(s, race=0., **change) if s.mode == 'rollout' else s for s in base.stages)
        lead = None if base.lead is None else replace(base.lead, race=0., **change)
        configs.append(replace(base, stages=stages, lead=lead))
    STATE.update(player=p, dds=DDS(), role=role, me=me, configs=configs)


def read(note, symbol_played, declaring, target):
    """(declarer's tricks expected with the card played, the contract's chance) from a decision's note; None where it has none."""
    j = next((i for i, run in enumerate(note.get('runs') or ()) if symbol_played in run), None)
    if j is None or not note.get('roll') or note['roll'][j] is None:
        return None
    tricks = note['roll'][j] if declaring else -note['roll'][j]
    chance = float('nan')
    cap = note.get('cap')
    if cap:
        shape = tuple(cap['shape'])
        w = np.frombuffer(base64.b64decode(cap['w']), np.float32).astype(np.float64)
        t = np.frombuffer(base64.b64decode(cap['t']), np.int8).reshape(shape).astype(np.int64)[:, j]
        f = np.frombuffer(base64.b64decode(cap['f']), np.uint8).reshape(shape).astype(bool)[:, j]
        played = t >= 0
        if played.any():
            final = np.where(f, np.maximum(t, target), t)[played]
            ww = w[played] / w[played].sum()
            tricks, chance = float(ww @ final), float(ww @ (final >= target))
    return float(tricks), chance


def one_file(job):
    path, every, lead = job
    p, dds, role, configs = STATE['player'], STATE['dds'], STATE['role'], STATE['configs']
    d = json.load(gzip.open(path, 'rt'))
    rows = []
    for key, e in d['unique_tables'].items():
        if e.get('schema_version') == 'v4-passed-out-v1' or not e.get('tables'):
            continue
        board = Board.from_dict(e['board'])
        target = board.contract.level + 6
        for ti, table in enumerate(e['tables']):
            if table.get('depth', 0) or table.get('fork_kind') or table.get('declarer_tricks') is None:
                continue
            g = Game(board)
            for ai, a in enumerate(table['actions']):
                o = g.observation()
                x = card(a['card'])
                note = a.get('x8') or {}
                seed = zlib.crc32(f'{board.id}|{ti}|{ai}'.encode())
                if (a.get('player') or a.get('role')) == role and note.get('mode') == 'rollout' and len(note.get('cards') or ()) > 1 \
                        and len(o.legal) > 1 and (lead or o.history) and seed % every == 0:
                    declaring = o.actor % 2 == o.contract.declarer % 2
                    world = tuple(tuple(sorted(h)) for h in g.hands)
                    values, _ = dds.solve(world, o.contract.trump, o.leader, list(o.trick))
                    best = max(values[y] for y in o.legal)
                    p.token, out, started = (path, key, ti, ai), [], time.process_time()
                    for config in configs:
                        p.x8 = config
                        got = p.choose(o, random.Random(seed))
                        n2 = (got.details or {}).get('x8') or {}
                        est = read(n2, a['card'], declaring, target) if n2.get('mode') == 'rollout' else None
                        out.append(None if est is None else (int(got.card), float(best - values[got.card]), est[0], est[1]))
                    p.x8 = configs[0]
                    if all(v is not None for v in out):
                        rows.append(dict(table=f'{path}|{key}|{ti}', role='lead' if not o.history else 'declaring' if declaring else 'defending',
                                         trick=len(o.history) // 4 + 1, took=int(table['declarer_tricks']), target=int(target),
                                         played=float(best - values[x]), v=out, cpu=round(time.process_time() - started, 3)))
                g.play(x)
    return rows


def clustered(pairs):
    by = defaultdict(lambda: [0., 0])
    for table, v in pairs:
        by[table][0] += v
        by[table][1] += 1
    n, g = sum(c for _, c in by.values()), len(by)
    if not n:
        return float('nan'), float('nan')
    m = sum(s for s, _ in by.values()) / n
    return m, math.sqrt(sum((s - m * c) ** 2 for s, c in by.values()) * g / max(g - 1, 1)) / n


def report(rows):
    print(f'{len(rows)} decisions on {len({r["table"] for r in rows})} tables; CPU a decision, every setting: {np.mean([r["cpu"] for r in rows]):.2f} s')
    for scope in ('all', 'declaring', 'defending', 'lead', 'tricks 1-4', 'tricks 5-13'):
        sel = [r for r in rows if scope == 'all' or r['role'] == scope or (scope == 'tricks 1-4' and r['trick'] <= 4 and r['role'] != 'lead')
               or (scope == 'tricks 5-13' and r['trick'] >= 5)]
        if len(sel) < 30:
            continue
        print(f'\n{scope}: {len(sel)} decisions. Recorded card gives up {np.mean([r["played"] for r in sel]):.4f} tricks a decision by double dummy')
        print(f'  {"simulated seats":24s} | {"own-side optimism":>18s} | {"squared error - draw":>21s} | {"Brier - draw":>18s} | {"other card":>10s} | {"DD given up":>11s} {"minus draw":>18s}')
        for k, (name, _) in enumerate(VARIANTS):
            sign = lambda r: 1 if r['role'] == 'declaring' else -1
            opt = clustered([(r['table'], sign(r) * (r['v'][k][2] - r['took'])) for r in sel])
            mse = clustered([(r['table'], (r['v'][k][2] - r['took']) ** 2 - (r['v'][0][2] - r['took']) ** 2) for r in sel])
            ok = [r for r in sel if not math.isnan(r['v'][k][3]) and not math.isnan(r['v'][0][3])]
            made = lambda r: float(r['took'] >= r['target'])
            brier = clustered([(r['table'], (r['v'][k][3] - made(r)) ** 2 - (r['v'][0][3] - made(r)) ** 2) for r in ok]) if ok else (float('nan'),) * 2
            moved = np.mean([r['v'][k][0] != r['v'][0][0] for r in sel])
            dd = clustered([(r['table'], r['v'][k][1] - r['v'][0][1]) for r in sel])
            print(f'  {name:24s} | {opt[0]:+8.3f} +- {opt[1]:.3f} | {mse[0]:+10.4f} +- {mse[1]:.4f} | {brier[0]:+8.4f} +- {brier[1]:.4f} | {100 * moved:9.1f}% |'
                  f' {np.mean([r["v"][k][1] for r in sel]):11.4f} {dd[0]:+9.4f} +- {dd[1]:.4f}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', type=Path, nargs='+')
    ap.add_argument('--source', default='')
    ap.add_argument('--bot', default='candidate', help="'candidate' or 'opponent': whose decisions")
    ap.add_argument('--boards', type=int, default=100, help='record files read from each folder')
    ap.add_argument('--every', type=int, default=3, help='one decision in this many (by a hash of the position)')
    ap.add_argument('--lead', action='store_true', help='the opening lead too')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', type=Path, help='the rows, a decision a line (appended to as boards finish)')
    ap.add_argument('--report', type=Path, nargs='+', help='print the report of rows files written earlier, and stop')
    a = ap.parse_args()
    if a.report:
        report([json.loads(line) for f in a.report for line in open(f) if line.strip()])
        return
    files = [f for run in a.runs for f in sorted(glob.glob(str(run / 'episodes' / '*.json.gz')))[:a.boards]]
    rows = []
    out = open(a.out, 'a') if a.out else None
    with Pool(a.workers, initializer=start, initargs=(str(a.runs[0]), a.source, a.bot)) as pool:
        for part in pool.imap_unordered(one_file, [(f, a.every, a.lead) for f in files], chunksize=1):
            rows += part
            if out:
                for r in part:
                    out.write(json.dumps(r) + '\n')
                out.flush()
    print(f'{len(files)} boards of {", ".join(r.name for r in a.runs[:3])}{" ..." if len(a.runs) > 3 else ""}; the {a.bot}\'s rollout decisions, one in {a.every}')
    report(rows)


if __name__ == '__main__':
    main()
