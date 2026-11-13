#!/usr/bin/env python3
"""Could the layout reader score a sample of hand-type classes instead of all of them? On real decisions of pure Stu's
collection, at the early tricks where it enumerates every class (tricks 1 to 6):

  python training/rollout-loop-20261113/bench/proposal.py EPISODES_DIR --boards 30

For each side's decisions there: the number of classes; the time to score them; and the efficiency of a uniform
proposal (layouts drawn uniformly, then weighted by the hand-fit scorer), that is, the effective sample size per draw:
  (sum m f)^2 / (sum m * sum m f^2)    m = a class's number of layouts (multiplicity), f = its fit weight.
A proposal of M uniform layouts weighted by fit has an effective size of about M times that. Today's reader draws a
pool of 512 from the exact weights (scoring every class).
"""
import argparse, glob, gzip, json, os, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.gen6 import Classes, View  # noqa: E402
from bridge_harness.x8_player import player  # noqa: E402
import gen8_match  # noqa: E402


def lse(x):
    m = x.max(); return m + np.log(np.exp(x - m).sum())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('episodes', type=Path)
    p.add_argument('--boards', type=int, default=30)
    p.add_argument('--source', type=Path, default=Path.home() / 'work/loop/capsule/recovery')
    a = p.parse_args()
    m = gen8_match.build_manifest(a.source, ROOT / 'configs/loop-bots.json', 'stu0-pa~stu0-pb', 9001)
    bot = player(m['bots']['stu0-pa'], a.source)
    files = sorted(a.episodes.glob('*.json.gz'))[:a.boards]
    rows = []
    for f in files:
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            if not e.get('tables'):
                continue
            board = Board.from_dict(e['board']); game = Game(board); bot.meet('stu0-pb')
            for act in e['tables'][0]['actions']:
                o = game.observation()
                if 1 <= len(o.history) < 24 and len(o.legal) > 1 and (act.get('gen6') or {}).get('classes'):
                    view = View(o)
                    if len(view.hidden) == 2:
                        t = time.process_time()
                        classes = Classes(view)
                        bot.scorer.types.clear()
                        f_ = bot.type_log_weights(o, view, classes.length, classes.hon, 'scorer')
                        secs = time.process_time() - t
                        lm = np.asarray(classes.logmult, np.float64)
                        eff = float(np.exp(2 * lse(lm + f_) - lse(lm) - lse(lm + 2 * f_)))
                        rows.append((len(o.history) // 4 + 1, len(classes), secs, eff))
                game.play(card(act['card']))
    rows = np.array(rows)
    print(f'{len(rows)} decisions from {len(files)} boards')
    for lo, hi in ((1, 1), (2, 2), (3, 4), (5, 6)):
        r = rows[(rows[:, 0] >= lo) & (rows[:, 0] <= hi)]
        if len(r):
            e = r[:, 3]
            print(f'tricks {lo}-{hi}: {len(r):3d} decisions | classes mean {r[:, 1].mean():8.0f} | scoring them all {r[:, 2].mean():.2f} s | '
                  f'uniform-proposal efficiency: median {np.median(e):.3f}, 10th pct {np.percentile(e, 10):.3f}, min {e.min():.4f}')
    e = rows[:, 3]
    for M in (2048, 4096, 8192):
        print(f'  M = {M}: effective size median {np.median(e) * M:.0f}, 10th pct {np.percentile(e, 10) * M:.0f}, decisions under 512: {100 * (e * M < 512).mean():.0f}%')


if __name__ == '__main__':
    main()
