#!/usr/bin/env python3
"""Would a layout pool kept for the whole hand save the reader's play-likelihood work? On real decisions of pure Stu's
collection, at the early tricks where the reader draws its pool from the hand-type classes:

  python training/rollout-loop-20261113/bench/pool_survival.py EPISODES_DIR --boards 30

At each such decision the pool is drawn as the reader draws it (512 layouts by class weight, low cards at random). At
the same player's next such decision, the bench counts how many of those layouts are still possible (every card a
hidden hand has played since was in that hand, and no hand holds a suit it has shown out of). A kept pool would score
only the new plays on the layouts still possible and every play on the fresh layouts that replace the rest, so the
share of the net's play-likelihood rows it would save is
  survivors * old plays / (pool * all plays)
counting each hidden play as one row (an upper bound: the reader skips forced cards and finds some rows in its cache).
"""
import argparse, gzip, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'scripts'))
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.gen6 import Classes, View, spaced  # noqa: E402
from bridge_harness.gen7 import hidden_plays  # noqa: E402
from bridge_harness.x8_player import player  # noqa: E402
import x8_match  # noqa: E402

SUIT_BITS = [sum(1 << c for c in range(13 * s, 13 * s + 13)) for s in range(4)]


def bits(cards):
    return sum(1 << int(c) for c in cards)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('episodes', type=Path)
    p.add_argument('--boards', type=int, default=30)
    p.add_argument('--pool', type=int, default=512)
    p.add_argument('--source', type=Path, default=Path.home() / 'work/loop/capsule/recovery')
    a = p.parse_args()
    m = x8_match.build_manifest(a.source, ROOT / 'configs/loop-bots.json', 'stu0-pa~stu0-pb', 9001)
    bot = player(m['bots']['stu0-pa'], a.source)
    rng = np.random.default_rng(1)
    rows = []          # trick, survivors share, plays now, new plays, saved share
    files = sorted(a.episodes.glob('*.json.gz'))[:a.boards]
    for f in files:
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            if not e.get('tables'):
                continue
            board = Board.from_dict(e['board']); game = Game(board); bot.meet('stu0-pb')
            pools = {}                                  # controller -> (hidden, plays then, original masks of hidden[0])
            for act in e['tables'][0]['actions']:
                o = game.observation()
                if 1 <= len(o.history) < 24 and len(o.legal) > 1 and (act.get('gen6') or {}).get('classes'):
                    view = View(o)
                    if len(view.hidden) == 2:
                        h0, h1 = view.hidden
                        plays = hidden_plays(o, True)
                        old = pools.get(o.controller)
                        if old is not None and old[0] == view.hidden and plays:
                            p0, p1 = bits(view.played[h0]), bits(view.played[h1])
                            unseen_or_played = bits(view.unseen) | p0 | p1
                            ok = 0
                            for mask in old[2]:
                                cur0, cur1 = mask & ~p0, unseen_or_played & ~mask & ~p1
                                good = (p0 & ~mask) == 0 and (p1 & mask) == 0
                                for seat, suit in view.voids:
                                    good = good and ((cur0 if seat == h0 else cur1) & SUIT_BITS[suit]) == 0
                                ok += good
                            s = ok / len(old[2])
                            n_old = old[1]
                            rows.append((len(o.history) // 4 + 1, s, len(plays), len(plays) - n_old, s * n_old / len(plays)))
                        classes = Classes(view)
                        logw = classes.logmult + bot.type_log_weights(o, view, classes.length, classes.hon, 'scorer')
                        worlds = classes.worlds(spaced(logw, a.pool, rng.random()), rng)
                        masks = [bits(w[h0]) | bits(view.played[h0]) for w in worlds]
                        pools[o.controller] = (view.hidden, len(plays), masks)
                game.play(card(act['card']))
    r = np.array(rows)
    print(f'{len(r)} next decisions from {len(files)} boards (pool {a.pool})')
    print('trick  decisions  survivors  plays  new plays  rows saved')
    for t in range(1, 8):
        k = r[r[:, 0] == t]
        if len(k):
            print(f'{t:5d}  {len(k):9d}  {k[:, 1].mean():9.3f}  {k[:, 2].mean():5.1f}  {k[:, 3].mean():9.1f}  {k[:, 4].mean():10.3f}')
    w = r[:, 2]
    print(f'all    {len(r):9d}  {r[:, 1].mean():9.3f}  {w.mean():5.1f}  {r[:, 3].mean():9.1f}  '
          f'{r[:, 4].mean():10.3f}  (weighted by plays: {(r[:, 4] * w).sum() / w.sum():.3f})')


if __name__ == '__main__':
    main()
