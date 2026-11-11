import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Late-play decision test (tricks 6-12) on recorded common-auction tables.

At the start of trick 6 each player (declarer, opening leader, third hand) gets the
complete list of layouts consistent with the cards seen, show-outs and the bidding
(each hidden seat's original 13 cards must pass the Gen5 bidder test). The list is
then filtered by every later card. Every non-forced decision from there on is made
four ways and scored double-dummy on the true deal:
  v5        32 layouts from the bot's belief sampler (current behaviour)
  uniform   32 layouts uniform over cards and show-outs
  list      every listed layout (a uniform random LIST_CAP of them if there are more)
  list32    32 layouts drawn from the list
The true deal's double-dummy value of every legal card is stored for all 52 plies.

Usage: python late_play.py OUT.jsonl START STOP STRIDE OFFSET [LIST_CAP]
"""
import gzip
import itertools
import json
import os
import random
import sys
import time

os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbid import NumpyBidder, AuctionModel  # noqa: E402
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402
from bridge_harness.belief_capacity import Weights  # noqa: E402
from bridge_harness.bidding_sampling import WeightedSampler  # noqa: E402
from bridge_harness.sampling import Sampler  # noqa: E402

ROOT = FEED
START_PLY = 20
COMBOS = {}


def combos(n, k):
    if (n, k) not in COMBOS:
        COMBOS[(n, k)] = np.array(list(itertools.combinations(range(n), k)), np.int64)
    return COMBOS[(n, k)]


def replay(board, acts):
    game = Game(board)
    states = []
    for act in acts:
        o = game.observation()
        states.append(dict(o=o, rem=[tuple(sorted(h)) for h in game.hands], trick=tuple(game.trick),
                           leader=game.leader, decl=game.declarer_tricks))
        game.play(card(act['card']))
    return states


class Lister:
    """All layouts of the two hidden hands, from one observer's seat, kept consistent with the play."""

    def __init__(self, observer, board, states, am, rng, cap):
        st = states[START_PLY]
        dummy = board.contract.dummy
        self.A, self.B = [s for s in range(4) if s not in (observer, dummy)]
        self.observer, self.dummy = observer, dummy
        history = st['o'].history
        self.U = np.array(sorted(st['rem'][self.A] + st['rem'][self.B]))
        self.col = {int(c): i for i, c in enumerate(self.U)}
        ka = len(st['rem'][self.A])
        idx = combos(len(self.U), ka)
        M = np.zeros((len(idx), len(self.U)), bool)
        np.put_along_axis(M, idx, True, axis=1)
        voids = set()
        for i, (seat, c) in enumerate(history):
            led = history[i - i % 4][1] // 13
            if c // 13 != led:
                voids.add((seat, led))
        suit = self.U // 13
        keep = np.ones(len(M), bool)
        for (seat, s) in voids:
            cols = suit == s
            if seat == self.A:
                keep &= ~M[:, cols].any(axis=1)
            elif seat == self.B:
                keep &= ~(~M[:, cols]).any(axis=1)
        M = M[keep]
        self.n_cards = len(M)
        played = {s: [c for seat, c in history if seat == s] for s in (self.A, self.B)}
        ha = np.concatenate([self.U[np.nonzero(M)[1]].reshape(len(M), ka), np.tile(played[self.A], (len(M), 1))], axis=1)
        hb = np.concatenate([self.U[np.nonzero(~M)[1]].reshape(len(M), len(self.U) - ka), np.tile(played[self.B], (len(M), 1))], axis=1)
        ok = am.check(self.A, ha) & am.check(self.B, hb)
        self.M = M[ok]
        self.alive = np.ones(len(self.M), bool)
        self.order = np.array(rng.sample(range(len(self.M)), len(self.M)))     # fixed random order for subsets
        self.cap = cap
        self.gone = np.zeros(len(self.U), bool)                                 # U cards already played
        truth = np.isin(self.U, st['rem'][self.A])
        hit = np.flatnonzero((self.M == truth).all(axis=1))
        self.true_row = int(hit[0]) if len(hit) else -1

    def rows(self):
        """Row ids used for solving: all alive rows, or the first `cap` of the fixed random order."""
        o = self.order[self.alive[self.order]]
        return o if len(o) <= self.cap else o[:self.cap]

    def worlds(self, rows, st):
        out = []
        live = ~self.gone
        for r in rows:
            hands = [None] * 4
            hands[self.observer] = st['rem'][self.observer]
            hands[self.dummy] = st['rem'][self.dummy]
            m = self.M[r]
            hands[self.A] = tuple(int(c) for c in self.U[m & live])
            hands[self.B] = tuple(int(c) for c in self.U[~m & live])
            out.append(tuple(hands))
        return out

    def update(self, seat, c, led):
        """Condition on `seat` having played card c (led = suit led, or None if seat was on lead)."""
        if seat in (self.A, self.B):
            j = self.col[c]
            self.alive &= self.M[:, j] == (seat == self.A)
            if led is not None and c // 13 != led:
                cols = (self.U // 13 == led) & ~self.gone
                if cols.any():
                    has = self.M[:, cols].any(axis=1) if seat == self.A else (~self.M[:, cols]).any(axis=1)
                    self.alive &= ~has
            self.gone[j] = True


def pick_weights(matrix):
    m = matrix.mean(axis=0)
    best = np.isclose(m, m.max(), atol=1e-9)
    return (best / best.sum()).tolist()


def main():
    out_path, start, stop, stride, offset = sys.argv[1], *map(int, sys.argv[2:6])
    cap = int(sys.argv[6]) if len(sys.argv) > 6 else 256
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)['index'] for l in open(out_path)}
    bidder = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
    belief = Weights(ROOT + '/artifacts/v5/belief.npz')
    dds = DDS(cache_path='')
    out = open(out_path, 'a')
    for index in range(start, stop):
        if index % stride != offset or index in done:
            continue
        path = f'{ROOT}/episodes/{index:06d}.json.gz'
        if not os.path.exists(path):
            continue
        ep = json.load(gzip.open(path))
        t = ep['unique_tables'][ep['regimes']['common']['tables'][0]]
        board = Board.from_dict(t['board'])
        acts = t['tables'][0]['actions'] if board.contract is not None else []
        if len(acts) != 52:
            continue
        t0 = time.time()
        states = replay(board, acts)
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
        rng = random.Random(1000003 * index + 17)
        dec, dummy = board.contract.declarer, board.contract.dummy
        trump = board.contract.trump
        listers = {k: Lister(k, board, states, am, rng, cap) for k in range(4) if k != dummy}
        rec = dict(index=index, contract=board.contract.text(), declarer=dec, vulnerability=board.vulnerability,
                   list_start={str(k): [l.n_cards, int(len(l.M)), l.true_row >= 0] for k, l in listers.items()},
                   plies=[], decisions=[])
        for ply in range(52):
            st = states[ply]
            o = st['o']
            c = card(acts[ply]['card'])
            legal = list(o.legal)
            if len(legal) > 1 and ply < 48:
                truth, _ = dds.solve(st['rem'], trump, st['leader'], st['trick'])
                true_dd = [int(truth[x]) for x in legal]
                rec['plies'].append(dict(ply=ply, actor=o.actor, controller=o.controller, legal=legal, played=c, true_dd=true_dd))
                if ply >= START_PLY:
                    k = o.controller
                    L = listers[k]
                    rows = L.rows()
                    if not len(rows):
                        continue
                    fixed = [k, dummy]
                    solved = dds.solve_batch(L.worlds(rows, st), trump, st['leader'], st['trick'], fixed_seats=fixed)
                    mat = np.array([[v[x] for x in legal] for v, _ in solved], float)
                    ws = WeightedSampler(o, belief.logits(o), 1.)
                    v5 = dds.solve_batch([ws.draw(rng) for _ in range(32)], trump, st['leader'], st['trick'], fixed_seats=fixed)
                    us = Sampler(o)
                    un = dds.solve_batch([us.draw(rng) for _ in range(32)], trump, st['leader'], st['trick'], fixed_seats=fixed)
                    rec['decisions'].append(dict(
                        ply=ply, n_list=int(L.alive.sum()), n_solved=len(rows),
                        list=pick_weights(mat), list32=pick_weights(mat[:32]),
                        v5=pick_weights(np.array([[v[x] for x in legal] for v, _ in v5], float)),
                        uniform=pick_weights(np.array([[v[x] for x in legal] for v, _ in un], float)),
                        list_mean=[round(float(x), 4) for x in mat.mean(axis=0)]))
            if ply >= START_PLY:
                led = st['trick'][0][1] // 13 if st['trick'] else None
                for L in listers.values():
                    L.update(o.actor, c, led)
                    if L.true_row >= 0 and not L.alive[L.true_row]:
                        raise RuntimeError(f'true layout dropped at ply {ply} deal {index}')
        rec['seconds'] = round(time.time() - t0, 1)
        out.write(json.dumps(rec) + '\n'); out.flush()
    out.close()


if __name__ == '__main__':
    main()
