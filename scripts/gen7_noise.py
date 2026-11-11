#!/usr/bin/env python3
"""How much of a Gen 6 decision is sampling noise, and where the net stands against that floor.

  python scripts/gen7_noise.py --episodes DIR --policy policy.npz [--from-trick 3] [--tables 120]
                               [--split 2] [--workers 2] [--out rows.json]
  python scripts/gen7_noise.py --rows rows.json            # report on rows written earlier

On root tables of Gen 6 self-play, every searched Gen 6 decision from --from-trick on is searched
again nine times with fresh layouts (32 each, the live settings):

  draw 1       a fresh 6-32 search; 8 of its layouts make an 8-layout search
  draws 2-5    pooled, a 128-layout search
  draws 6-9    pooled, the yardstick: every decider's card is valued on these 128 layouts, which no
               decider saw

Deciders: the card played at the table (6-32 then), the fresh 6-32, the 8-layout and 128-layout
searches, the net's most probable card, and the card the net's gap head rates best. Tricks given
up by a decider are the yardstick's value of the 128-layout search's card minus the yardstick's
value of the decider's card, so the 128-layout search is zero by definition and every other figure
is what that decider loses to it. The yardstick's own noise has mean zero and no decider saw it,
so these are unbiased; exact ties in a decider's own estimates count as an even split.

This measures sampling noise only. Every decider here shares the double-dummy assumption, and the
yardstick has it too. The opening lead is left out (it needs the lead net).
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
from bridge_harness.core import Board, Game, card
from bridge_harness.gen6 import View, systematic
from bridge_harness.gen7 import Gen7Player
import gen7_check as check
from gen7_lookahead import phase

STATE = {}
DRAWS = 9


def start(policy, from_trick, split):
    os.environ['BRIDGE_DDS_CACHE'] = ''
    STATE.update(player=Gen7Player(check.spec('gen7', policy, play_weight=0., tie_break='gen5'), ROOT), from_trick=from_trick, split=split)


def search(p, o, view, rng):
    """(per-layout utilities [layouts, cards], normalised weights) of one fresh 6-32 search; cards in o.legal order."""
    worlds, weights, _ = p.layouts(o, view, p.source(o, view), rng)
    u = np.array([[x[c] for c in o.legal] for x in (check.utilities(o, values) for values, _ in check.solve(p, o, worlds))], float)
    w = np.asarray(weights, float)
    return u, w / w.sum()


def decisions_of(path):
    p, rows = STATE['player'], []
    with gzip.open(path, 'rt') as f:
        d = json.load(f)
    if STATE['split'] >= 0 and check.split_of(d['family']) != STATE['split']:
        return rows
    if d['candidate'] != '6-32' or d['opponent'] != '6-32':
        return rows
    for e in d['unique_tables'].values():
        if 'tables' not in e:
            continue
        board = Board.from_dict(e['board'])
        table = e['tables'][0]
        game = Game(board)
        for ply, act in enumerate(table['actions']):
            o = game.observation()
            played = card(act['card'])
            if ply and ply // 4 + 1 >= STATE['from_trick'] and act.get('gen6') and act.get('samples') and len(o.legal) > 1:
                view = View(o)
                seed = int(d['family'][:8], 16)
                started = time.perf_counter()
                draws = [search(p, o, view, np.random.default_rng([ply, seed, k])) for k in range(DRAWS)]
                seconds = (time.perf_counter() - started) / DRAWS
                u, w = draws[0]
                index, share = systematic(w, 8, np.random.default_rng([ply, seed, 99])) if len(w) > 8 else (np.arange(len(w)), w)
                share = np.asarray(share, float)
                pooled = lambda ks: np.mean([draws[k][1] @ draws[k][0] for k in ks], axis=0)
                heads = p.net.heads([o])
                legal = list(o.legal)
                rows.append(dict(family=d['family'], ply=ply, phase=phase(ply), played=legal.index(played), seconds=seconds,
                                 table_gap=[act['estimates'][str_card(c)]['gap_to_best'] for c in legal],
                                 m8=(share / share.sum() @ u[index]).tolist(), m32=(w @ u).tolist(),
                                 m128=pooled(range(1, 5)).tolist(), yard=pooled(range(5, 9)).tolist(),
                                 logp=[float(heads['policy'][0][c]) for c in legal], net_gap=[float(heads['gap'][0][c]) for c in legal]))
            game.play(played)
    return rows


def str_card(c):
    return 'SHDC'[c // 13] + '23456789TJQKA'[c % 13]


def clustered(x, fam):
    by = {}
    for v, k in zip(x, fam):
        by.setdefault(k, []).append(v)
    totals, counts = np.array([sum(v) for v in by.values()]), np.array([len(v) for v in by.values()])
    mean = totals.sum() / counts.sum()
    se = math.sqrt(((totals - mean * counts) ** 2).sum() * len(by) / max(1, len(by) - 1)) / counts.sum()
    return float(mean), float(se)


def split_value(score, yard):
    """Yardstick value of the card a decider picks by `score` (higher is better), exact ties split evenly."""
    score, yard = np.asarray(score, float), np.asarray(yard, float)
    return float(yard[score >= score.max() - 1e-9].mean())


def report(rows, title):
    fam = [r['family'] for r in rows]
    base = np.array([split_value(r['m128'], r['yard']) for r in rows])
    deciders = {
        'table card (6-32 then)': lambda r: r['yard'][r['played']],
        'fresh 6-32': lambda r: split_value(r['m32'], r['yard']),
        '8 layouts': lambda r: split_value(r['m8'], r['yard']),
        '128 layouts': lambda r: split_value(r['m128'], r['yard']),
        'net, most probable card': lambda r: split_value(r['logp'], r['yard']),
        'net, gap head': lambda r: split_value(-np.asarray(r['net_gap']), r['yard']),
    }
    for k in (8, 32):       # the net's gap head as a prior worth `k` layouts, added to an 8-layout search
        deciders[f'8 layouts + net gap head as {k} layouts'] = lambda r, k=k: split_value(8 * np.asarray(r['m8']) - k * np.asarray(r['net_gap']), r['yard'])
    deciders['fresh 6-32 + net gap head as 32 layouts'] = lambda r: split_value(np.asarray(r['m32']) - np.asarray(r['net_gap']), r['yard'])
    print(f"\n== {title}: {len(rows)} decisions, {len(set(fam))} deals; one 32-layout search {np.mean([r['seconds'] for r in rows]):.3f} s")
    out = {}
    for name, f in deciders.items():
        got = np.array([f(r) for r in rows])
        out[name] = clustered(base - got, fam)
        print(f"   {name:42s} gives up {out[name][0]:+.4f} +- {out[name][1]:.4f} to the 128-layout search")
    r32, r8 = out['fresh 6-32'][0], out['8 layouts'][0]
    print(f"   noise law check: (8 minus 128)/(32 minus 128) = {r8 / r32 if abs(r32) > 1e-9 else float('nan'):.2f}; 5.0 if what noise costs falls as 1/layouts")
    print(f"   implied cost of noise against endless layouts: 6-32 {r32 * 4 / 3:.4f}, 6-128 {r32 / 3:.4f}, 8 layouts {r32 * 16 / 3:.4f} (from the 6-32 figure and that law)")
    agree = lambda a, b: np.mean([np.argmax(r[a]) == np.argmax(r[b]) for r in rows])
    close = np.mean([np.sort(np.asarray(r['yard']))[-1] - max([v for v in r['yard'] if v < max(r['yard']) - 1e-9] or [-99]) <= .125 for r in rows])
    print(f"   same card as the 128-layout search: fresh 6-32 {agree('m32', 'm128'):.3f}, 8 layouts {agree('m8', 'm128'):.3f}, net {agree('logp', 'm128'):.3f}; "
          f"a second card within 0.125 on the yardstick {close:.3f}")
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--episodes', type=Path)
    a.add_argument('--policy', type=Path)
    a.add_argument('--from-trick', type=int, default=3)
    a.add_argument('--tables', type=int, default=120)
    a.add_argument('--split', type=int, default=2, help='0 train, 1 validation, 2 test, -1 every deal')
    a.add_argument('--workers', type=int, default=2)
    a.add_argument('--seconds', type=float, default=1e9)
    a.add_argument('--rows', type=Path)
    a.add_argument('--out', type=Path)
    a = a.parse_args()
    if a.rows:
        rows = json.loads(a.rows.read_text())['rows']
    else:
        files = sorted(a.episodes.glob('*.json.gz'))
        rows, tables, started = [], 0, time.time()
        with Pool(a.workers, initializer=start, initargs=(a.policy, a.from_trick, a.split)) as pool:
            for got in pool.imap_unordered(decisions_of, files, chunksize=2):
                rows += got
                tables += bool(got)
                if tables >= a.tables or time.time() - started > a.seconds:
                    pool.terminate()
                    break
        if a.out:
            a.out.write_text(json.dumps(dict(settings=dict(from_trick=a.from_trick, split=a.split, policy=str(a.policy), tables=tables,
                                                           seconds=round(time.time() - started)), rows=rows)))
    report(rows, 'ALL')
    for ph in sorted({r['phase'] for r in rows}):
        sub = [r for r in rows if r['phase'] == ph]
        if len(sub) >= 100:
            report(sub, ph)


if __name__ == '__main__':
    main()
