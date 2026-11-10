import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""How much is known about the two hidden hands as the play goes on, without using card choices.

For recorded common-auction tables, at each player's first decision in tricks 2, 4, 6, 8, 10:
  cards   number of layouts consistent with the cards seen and show-outs (exact count)
  auction share of those layouts whose hidden ORIGINAL hands (cards held + cards already played)
          would have made their calls under the Gen5 bidder (exact when the list is short, sampled otherwise)
  v5      the belief sampler's exact probability of the true layout at that position
Usage: python play_info.py OUT.jsonl START STOP STRIDE OFFSET
"""
import gzip
import itertools
import json
import math
import os
import random
import sys

os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbid import NumpyBidder, AuctionModel  # noqa: E402
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.belief_capacity import Weights  # noqa: E402
from bridge_harness.bidding_sampling import WeightedSampler  # noqa: E402
from bridge_harness.sampling import Sampler  # noqa: E402

ROOT = FEED
TRICKS = (2, 4, 6, 8, 10)
LIMIT = 4000


def measure(o, board, am, belief, rng):
    hidden = [s for s in range(4) if o.known_hands[s] is None]
    played = {s: [c for seat, c in o.history if seat == s] for s in hidden}
    u = Sampler(o)
    n_void = u.count(0, u.caps)
    unseen = [c for suit in u.suits for c in suit]
    caps = dict(zip(u.unknown, u.caps))
    a, b = hidden
    if n_void <= LIMIT * 4 and math.comb(len(unseen), caps[a]) <= 20000:
        rows_a = []
        for combo in itertools.combinations(unseen, caps[a]):
            rest = [c for c in unseen if c not in combo]
            if all(u.allowed[c // 13][u.unknown.index(a)] for c in combo) and all(u.allowed[c // 13][u.unknown.index(b)] for c in rest):
                rows_a.append((combo, tuple(rest)))
        exact = True
    else:
        rows_a = []
        for _ in range(LIMIT):
            w = u.draw(rng)
            rows_a.append((w[a], w[b]))
        exact = False
    ha = np.array([list(r[0]) + played[a] for r in rows_a])
    hb = np.array([list(r[1]) + played[b] for r in rows_a])
    ok = am.check(a, ha) & am.check(b, hb)
    true_ok = bool(am.check(a, np.array([board.hands[a]]))[0] and am.check(b, np.array([board.hands[b]]))[0])
    ws = WeightedSampler(o, belief.logits(o), 1.)
    owner = {c: s for s in hidden for c in board.hands[s]}
    logw = sum(ws.weights[i][ws.unknown.index(owner[c])] for i, c in enumerate(ws.cards))
    logp = logw - ws.partition(0, ws.caps)
    return dict(unseen=len(unseen), log_cards=math.log(n_void), exact=exact, listed=len(rows_a), consistent=int(ok.sum()),
                true_consistent=true_ok, logp_v5=float(logp), n_hidden_played=len(played[a]) + len(played[b]))


def main():
    out_path, start, stop, stride, offset = sys.argv[1], *map(int, sys.argv[2:6])
    bidder = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
    belief = Weights(ROOT + '/artifacts/v5/belief.npz')
    out = open(out_path, 'a')
    for index in range(start, stop):
        if index % stride != offset:
            continue
        path = f'{ROOT}/episodes/{index:06d}.json.gz'
        if not os.path.exists(path):
            continue
        ep = json.load(gzip.open(path))
        t = ep['unique_tables'][ep['regimes']['common']['tables'][0]]
        board = Board.from_dict(t['board'])
        if board.contract is None:
            continue
        acts = t['tables'][0]['actions']
        if len(acts) != 52:
            continue
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
        game = Game(board)
        rng = random.Random(index)
        dec = board.contract.declarer
        todo = {(T, v) for T in TRICKS for v in ('declarer', 'leader', 'third')}
        for ply, act in enumerate(acts):
            o = game.observation()
            trick = ply // 4 + 1
            view = 'declarer' if o.controller == dec else 'leader' if o.controller == (dec + 1) % 4 else 'third'
            for T in TRICKS:
                if trick == T and (T, view) in todo:
                    todo.discard((T, view))
                    rec = measure(o, board, am, belief, rng)
                    rec.update(index=index, trick=T, view=view, ply=ply)
                    out.write(json.dumps(rec) + '\n'); out.flush()
            game.play(card(act['card']))
    out.close()


if __name__ == '__main__':
    main()
