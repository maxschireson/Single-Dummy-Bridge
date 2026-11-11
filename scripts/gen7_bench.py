#!/usr/bin/env python3
"""Score a search on gap-fork pairs: would it have played the card that did better?

  python scripts/gen7_bench.py --episodes DIR --policy policy.npz [--tricks 1,2] [--breadth 2] [--mass 0.9]
                               [--layouts 8] [--from-trick 3] [--pairs 2000] [--workers 2] [--out rows.json]

--tricks lists the trees to score, ';' between them: a horizon in tricks, optionally ':' and tree
settings that differ from the command line, e.g. "2;2:reply_power=2;2:breadth=1,reply_gap=0.2".

In a gap-fork pair A is the card Gen 6 played and B a card it rated worse, which the collector
forced and played out from the same position (docs/gen7_data_capture_2026-11-11.md). The realized
cost of B is known. Each pair's position is rebuilt, Gen 6's own layouts are drawn again, and A and
B are valued by:

  pimc     plain PIMC on all those layouts (Gen 6 again, with a fresh draw)
  pimc_k   plain PIMC on the --layouts of them that go into the tree
  tree_N   the tree (bridge_harness/gen7_tree.py) to the end of N tricks on the same --layouts
  mix_N    pimc plus the tree's correction: pimc + (tree_N - pimc_k)

An evaluator that prefers B is credited with what B really gained (minus its realized cost);
one that prefers A scores nothing. Gen 6 itself scores zero by construction, so `gain` is tricks
per pair gained over Gen 6 by following that evaluator on these pairs. `over_pimc` is the same
thing measured against the fresh PIMC draw on identical layouts, which removes the luck of the draw
from the comparison. Pairs are sampled by band of estimated gap, so these are per sampled pair.
The opening lead is left out (the tree needs dummy on the table).

--ties adds the tie-audit pairs as band -1: two cards Gen 6 rated exactly level, both played out.
PIMC cannot tell them apart, so any gain there is information the tree adds.
"""
import argparse
import gzip
import json
import math
from multiprocessing import Pool
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import SEATS, Board, Game, card
from bridge_harness.gen6 import View, systematic
from bridge_harness.gen7 import Gen7Player
from bridge_harness.gen7_tree import Tree, TreeConfig
import gen7_check as check
from gen7_lookahead import PHASES, phase

STATE = {}


def label(n, extra):
    return str(n) + ''.join(f'_{k}{v}' for k, v in sorted(extra.items()))


def variants(text):
    """'1,2' or '2;2:reply_power=2;2:breadth=1,reply_gap=0.2' -> ((tricks, {setting: value}), ...)"""
    out = []
    for part in text.replace(',', ';').split(';') if ':' not in text and '=' not in text else text.split(';'):
        n, _, rest = part.partition(':')
        extra = {}
        for item in filter(None, rest.split(',')):
            k, v = item.split('=')
            extra[k] = v if k == 'reply' else float(v) if '.' in v else int(v)
        out.append((int(n), extra))
    return tuple(out)


def start(policy, tricks, breadth, mass, layouts, from_trick, ties=False):
    os.environ['BRIDGE_DDS_CACHE'] = ''                          # thousands of small batches: no disk cache
    STATE.update(player=Gen7Player(check.spec('gen7', policy, play_weight=0., tie_break='gen5'), ROOT),
                 tricks=tricks, breadth=breadth, mass=mass, layouts=layouts, from_trick=from_trick, ties=ties)


def pairs_of(path):
    p, rows = STATE['player'], []
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    for e in d['unique_tables'].values():
        if 'tables' not in e:
            continue
        ok = lambda ply: ply > 0 and ply // 4 + 1 >= STATE['from_trick']
        # (table A was played at, table B was played at, ply, card B, band, estimated gap, sampling probability)
        forks = [(0, g['fork_table'], g['ply'], g['forced_card'], g['band'], g['estimated_gap'], g['propensity'])
                 for g in e.get('gap_forks') or [] if ok(g['ply'])]
        if STATE['ties']:                       # tie audits: two cards Gen 6 rated exactly level, both played out
            forks += [(x['candidate_table'], x['reference_table'], x['ply'], x['reference_card'], -1, 0., x['audit_probability'])
                      for x in e.get('audits') or [] if not x['identical_action'] and ok(x['ply'])]
        if not forks:
            continue
        board = Board.from_dict(e['board'])
        declarer = board.contract.declarer
        for table_a, table_b, ply, forced, band, estimated, propensity in sorted(forks, key=lambda g: (g[2], g[0])):
            root, fork = e['tables'][table_a], e['tables'][table_b]
            game = Game(board)
            for act in root['actions'][:ply]:
                game.play(card(act['card']))
            o = game.observation()
            a, b = card(root['actions'][ply]['card']), card(forced)
            if not root['actions'][ply].get('gen6'):
                continue                        # not a Gen 6 decision
            seat = SEATS.index(root['actions'][ply]['seat'])
            sign = 1 if seat % 2 == declarer % 2 else -1
            row = dict(family=d['family'], phase=phase(ply), ply=ply, band=band, estimated=estimated,
                       propensity=propensity, final=sign * (root['declarer_tricks'] - fork['declarer_tricks']))
            view = View(o)
            rng = np.random.default_rng([ply, int(d['family'][:8], 16)])
            started = time.perf_counter()
            worlds, weights, _ = p.layouts(o, view, p.source(o, view), rng)
            means = {a: 0., b: 0.}
            for (values, _), w in zip(check.solve(p, o, worlds), weights):
                u = check.utilities(o, values)
                means[a] += float(w) * u[a]
                means[b] += float(w) * u[b]
            row['pimc'] = means[a] - means[b]
            row['seconds_pimc'] = time.perf_counter() - started
            k = STATE['layouts']
            index, share = systematic(np.asarray(weights), k, rng) if len(worlds) > k else (np.arange(len(worlds)), np.asarray(weights))
            sub = [worlds[i] for i in index]
            for n, extra in ((0, {}), *STATE['tricks']):
                tree = Tree(p.net, p.dds, TreeConfig(**dict(dict(tricks=n, breadth=STATE['breadth'], mass=STATE['mass'], layouts=k), **extra)))
                started = time.perf_counter()
                v = tree.values(o, sub, share, cards=[a, b])
                name = 'pimc_k' if n == 0 else f'tree_{label(n, extra)}'
                row[name] = v[a] - v[b]
                if n:
                    t = label(n, extra)
                    row[f'seconds_{t}'], row[f'lines_{t}'], row[f'rows_{t}'], row[f'solves_{t}'] = time.perf_counter() - started, tree.lines, tree.net_rows, tree.solves
            rows.append(row)
    return rows


def summarize(rows, tricks):
    f = np.array([r['final'] for r in rows], float)
    n = len(rows)
    families = [r['family'] for r in rows]

    def clustered(x):
        """Mean and standard error with deals as the unit."""
        by = {}
        for v, fam in zip(x, families):
            by.setdefault(fam, []).append(v)
        totals, counts = np.array([sum(v) for v in by.values()]), np.array([len(v) for v in by.values()])
        mean = totals.sum() / counts.sum()
        se = math.sqrt(((totals - mean * counts) ** 2).sum() * len(by) / max(1, len(by) - 1)) / counts.sum()
        return round(float(mean), 4), round(float(se), 4)

    evaluators = {'pimc': np.array([r['pimc'] for r in rows]), 'pimc_k': np.array([r['pimc_k'] for r in rows])}
    tricks = [label(n, extra) for n, extra in tricks]
    for t in tricks:
        tree = np.array([r[f'tree_{t}'] for r in rows])
        evaluators[f'tree_{t}'] = tree
        evaluators[f'mix_{t}'] = evaluators['pimc'] + tree - evaluators['pimc_k']
    out = dict(pairs=n, deals=len(set(families)), realized_cost_of_b=clustered(f), b_did_better=round(float((f < 0).mean()), 3),
               hindsight=clustered(np.maximum(0, -f)))
    base = {}
    for name, diff in evaluators.items():
        prefers_b = diff < -1e-9
        gain = np.where(prefers_b, -f, 0.)
        base[name] = gain
        ref = base['pimc'] if name.startswith('mix') or name == 'pimc' else base['pimc_k']
        out[name] = dict(prefers_b=round(float(prefers_b.mean()), 3), gain=clustered(gain), over_pimc=clustered(gain - ref),
                         cost_of_b_when_preferred=round(float(f[prefers_b].mean()), 3) if prefers_b.any() else None)
    for t in tricks:
        out[f'tree_{t}'].update(seconds=round(float(np.mean([r[f'seconds_{t}'] for r in rows])), 3),
                                lines=round(float(np.mean([r[f'lines_{t}'] for r in rows])), 1),
                                net_rows=round(float(np.mean([r[f'rows_{t}'] for r in rows])), 1),
                                solves=round(float(np.mean([r[f'solves_{t}'] for r in rows])), 1))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--episodes', type=Path)
    p.add_argument('--policy', type=Path)
    p.add_argument('--tricks', default='1,2')
    p.add_argument('--breadth', type=int, default=2)
    p.add_argument('--mass', type=float, default=.9)
    p.add_argument('--layouts', type=int, default=8)
    p.add_argument('--from-trick', type=int, default=3)
    p.add_argument('--pairs', type=int, default=2000)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--seconds', type=float, default=1e9)
    p.add_argument('--ties', action='store_true', help='also score tie-audit pairs (band -1): two cards Gen 6 rated level')
    p.add_argument('--rows', type=Path, help='summarize a rows file written earlier with --out instead of running')
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    tricks = variants(a.tricks)
    if a.rows:
        saved = json.loads(a.rows.read_text())
        rows, tricks = saved['rows'], tuple((t, {}) if isinstance(t, int) else (t[0], t[1]) for t in saved['settings']['tricks'])
    else:
        files = sorted(a.episodes.glob('*.json.gz'))
        rows, started = [], time.time()
        with Pool(a.workers, initializer=start, initargs=(a.policy, tricks, a.breadth, a.mass, a.layouts, a.from_trick, a.ties)) as pool:
            for got in pool.imap_unordered(pairs_of, files, chunksize=4):
                rows += got
                if len(rows) >= a.pairs or time.time() - started > a.seconds:
                    pool.terminate()
                    break
        if a.out:
            a.out.write_text(json.dumps(dict(settings=dict(tricks=tricks, breadth=a.breadth, mass=a.mass, layouts=a.layouts, from_trick=a.from_trick,
                                                           policy=str(a.policy), seconds=round(time.time() - started)), rows=rows)))
    result = dict(all=summarize(rows, tricks),
                  by_phase={k: summarize(sub, tricks) for k in PHASES for sub in [[r for r in rows if r['phase'] == k]] if len(sub) >= 50},
                  by_band={str(b): summarize(sub, tricks) for b in sorted({r['band'] for r in rows}) for sub in [[r for r in rows if r['band'] == b]] if len(sub) >= 50})
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
