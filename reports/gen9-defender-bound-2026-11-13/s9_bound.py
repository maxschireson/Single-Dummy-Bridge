"""G9-S9: what knowing one of partner's cards could unlock for the defence (g9, Gen 9).

On recorded Gen 8 tables, at the first decision of a defender with 8 cards (and with 7), contract not yet settled:
for each legal card and each of N layouts the defender cannot rule out (uniform, hand sizes and show-outs kept, as
8X's defender rule samples), would declarer then hold a guaranteed line (8X's `Finder.handovers`, sure_cpp)?

  p0      the hand-over probability of the defender's best card knowing nothing beyond its view
  p_u     the same when the defender is told whether partner holds the unseen honour u (best card on each side)
  p_full  the same knowing the whole layout (the most any information could give)

Bound per position: max over u of (p0 - p_u), against p0 - p_full. Nothing is played; no signal is modelled.

usage: SURE_BIN=... python3 s9_bound.py REPO OUT.jsonl SHARD.json [SHARD.json ...] [--layouts 64] [--cards 8,7]
"""
import json
import sys

import numpy as np


def arg(flag, default, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


REPO, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, REPO)
from bridge_harness.core import Board, Game, card              # noqa: E402
from bridge_harness.gen6 import View                            # noqa: E402
from bridge_harness.x8_claims import Finder                     # noqa: E402

SEATS = 'NESW'
N = arg('--layouts', 64, int)
WANT = {int(x) for x in arg('--cards', '8,7').split(',')}
files = [a for a in sys.argv[3:] if a.endswith('.json')]


def positions(bd, t):
    """(Observation, record) at the first decision of a defender with each wanted card count, contract still open."""
    k = t['contract']
    if not k or k[0] not in '1234567' or t['declarer'] not in SEATS:
        return
    board = Board.from_dict(dict(bd, contract=k, declarer=t['declarer'], auction=t['auction'], opening_lead=None))
    game = Game(board)
    decl = board.contract.declarer
    target = board.contract.level + 6
    plays = [(SEATS.index(p[0]), card(p[1:])) for p in t['plays']]
    if len(plays) != 52:
        return
    done = set()
    for seat, c in plays:
        if game.actor != seat:
            return                                          # the record and the game disagree: skip the table
        if seat % 2 != decl % 2:
            o = game.observation()
            left = len(game.hands[seat])
            need = target - game.declarer_tricks
            if left in WANT and left not in done and 0 < need <= left and len(o.legal) >= 2:
                done.add(left)
                yield o, dict(cards=left, need=need, seat=seat, game=_game(k), contract=k,
                              declarer_tricks=t['declarer_tricks'], made=t['declarer_tricks'] >= target)
        game.play(c)


def _game(k):
    level, strain = int(k[0]), k[1]
    return k.count('X') > 0 or level >= {'N': 3, 'S': 4, 'H': 4, 'D': 5, 'C': 5}[strain]


def main():
    finder = Finder()
    rng = np.random.default_rng(909)
    seen, n = set(), 0
    with open(OUT, 'w') as f:
        for fn in files:
            for b in json.load(open(fn)).values():
                for cond in (b.get('conditions') or {}).values():
                    for t in cond['tables']:
                        key = (b['board']['id'], t['contract'], t['declarer'], tuple(t['plays']))
                        if key in seen:
                            continue
                        seen.add(key)
                        for o, rec in positions(b['board'], t):
                            view = View(o)
                            worlds = [view.world(row) for row in view.uniform(N, rng)]
                            cards = sorted(o.legal)
                            H = finder.handovers(o, worlds, cards, allowance=2.)
                            ok = (H >= 0).all(axis=1)
                            if ok.sum() < N // 2:
                                continue
                            H, W = H[ok].astype(float), [w for w, k in zip(worlds, ok) if k]
                            p0 = float(H.mean(axis=0).min())
                            p_full = float(H.min(axis=1).mean())
                            partner = (o.actor + 2) % 4
                            declarer = o.contract.declarer
                            unseen = sorted({c for w in W for c in w[partner]} | {c for w in W for c in w[declarer]})
                            best = (0., None)
                            per = {}
                            for u in unseen:
                                if u % 13 < 8:                       # honours only: T J Q K A
                                    continue
                                inside = np.array([u in set(w[partner]) for w in W])
                                if inside.all() or (~inside).all():
                                    continue
                                pu = inside.mean() * H[inside].mean(axis=0).min() + (~inside).mean() * H[~inside].mean(axis=0).min()
                                gain = p0 - float(pu)
                                per[str(u)] = round(gain, 4)
                                if gain > best[0] + 1e-12:
                                    best = (gain, u)
                            rec.update(table=len(seen) - 1, layouts=int(ok.sum()), legal=len(cards), p0=p0, p_full=p_full,
                                       best_gain=best[0], best_card=best[1], gains=per)
                            f.write(json.dumps(rec) + '\n')
                            n += 1
    finder.close()
    print(len(seen), 'tables,', n, 'positions')


if __name__ == '__main__':
    main()
