import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Grade the hand-fit scorer in late play (tricks 6-12) on recorded common-auction tables.

At the start of trick 6 each player lists every layout that fits the cards seen and show-outs
(pure counting). Each layout is weighted by the scorer: the product of P(fit) for the two hidden
hands' original 13 cards. No bidder is consulted for that arm. The bidder-built list is kept
alongside as the ceiling.

Arms (best mean double-dummy value, scored on the true deal):
  v5       32 layouts from the bot's belief sampler
  uniform  32 layouts that fit the cards
  blist    up to 256 layouts from the bidder-built list (ceiling)
  net      256 layouts resampled from the card-fit list in proportion to scorer weight
  net32    32 such layouts
Also stored: log posterior of the true layout under cards only, v5, the scorer, and the bidder list.

Usage: python late_net.py SCORER.npz OUT.jsonl START STOP STRIDE OFFSET
"""
import gzip
import json
import math
import os
import random
import sys
import time

os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbid import NumpyBidder, AuctionModel, CALL_ID  # noqa: E402
import fit  # noqa: E402
from gen import types  # noqa: E402
from late_play import combos, replay, pick_weights, ROOT  # noqa: E402
from bridge_harness.core import Board, card, vulnerable  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402
from bridge_harness.belief_capacity import Weights  # noqa: E402
from bridge_harness.bidding_sampling import WeightedSampler  # noqa: E402

START_PLY = 20


class NetLister:
    def __init__(self, observer, board, states, am, scorer, rng):
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
        suit = self.U // 13
        keep = np.ones(len(M), bool)
        for i, (seat, c) in enumerate(history):
            led = history[i - i % 4][1] // 13
            if c // 13 != led:
                cols = suit == led
                if seat == self.A:
                    keep &= ~M[:, cols].any(axis=1)
                elif seat == self.B:
                    keep &= ~(~M[:, cols]).any(axis=1)
        self.M = M = M[keep]
        n = len(M)
        played = {s: [c for seat, c in history if seat == s] for s in (self.A, self.B)}
        ha = np.concatenate([self.U[np.nonzero(M)[1]].reshape(n, ka), np.tile(played[self.A], (n, 1))], axis=1)
        hb = np.concatenate([self.U[np.nonzero(~M)[1]].reshape(n, len(self.U) - ka), np.tile(played[self.B], (n, 1))], axis=1)
        self.ok_bidder = am.check(self.A, ha) & am.check(self.B, hb)          # ceiling arm only
        calls = np.array([[CALL_ID[c] for c in am.calls]])
        self.logw = np.zeros(n)
        t0 = time.process_time()
        for seat, hands in ((self.A, ha), (self.B, hb)):
            mem = np.zeros((n, 52), np.float32)
            np.put_along_axis(mem, hands, 1.0, axis=1)
            ln, hon, _ = types(mem)
            key = np.concatenate([ln, hon], axis=1)
            uniq, inv = np.unique(key, axis=0, return_inverse=True)
            auc = fit.auction_onehot(calls, [board.dealer], [seat])[0]
            ls = fit.log_score(scorer, uniq[:, :4], uniq[:, 4:], vulnerable(board.vulnerability, seat),
                               vulnerable(board.vulnerability, (seat + 1) % 4), auc)
            self.logw += ls[inv.ravel()]
        self.score_seconds = time.process_time() - t0
        self.alive = np.ones(n, bool)
        self.gone = np.zeros(len(self.U), bool)
        self.order = np.array(rng.sample(range(n), n))
        truth = np.isin(self.U, st['rem'][self.A])
        self.true_row = int(np.flatnonzero((M == truth).all(axis=1))[0])

    def worlds(self, rows, st):
        out, live = [], ~self.gone
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
        if seat in (self.A, self.B):
            j = self.col[c]
            self.alive &= self.M[:, j] == (seat == self.A)
            if led is not None and c // 13 != led:
                cols = (self.U // 13 == led) & ~self.gone
                if cols.any():
                    has = self.M[:, cols].any(axis=1) if seat == self.A else (~self.M[:, cols]).any(axis=1)
                    self.alive &= ~has
            self.gone[j] = True

    def resample(self, m, u):
        """Systematic resampling of m layouts in proportion to scorer weight. Returns rows, multiplicities."""
        rows = np.flatnonzero(self.alive)
        lw = self.logw[rows]
        p = np.exp(lw - lw.max()); p /= p.sum()
        picks = np.searchsorted(np.cumsum(p), (u + np.arange(m)) / m, side='left').clip(max=len(p) - 1)
        uniq, mult = np.unique(picks, return_counts=True)
        return rows[uniq], mult


def weighted_pick(mat, mult):
    m = (mult[:, None] * mat).sum(axis=0) / mult.sum()
    best = np.isclose(m, m.max(), atol=1e-9)
    return (best / best.sum()).tolist()


def main():
    scorer_path, out_path, start, stop, stride, offset = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
    scorer = dict(np.load(scorer_path))
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
        cards = [card(a['card']) for a in acts]
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
        rng = random.Random(1000003 * index + 41)
        dummy, trump = board.contract.dummy, board.contract.trump
        L = {k: NetLister(k, board, states, am, scorer, rng) for k in range(4) if k != dummy}
        rec = dict(index=index, contract=board.contract.text(), declarer=board.contract.declarer,
                   vulnerability=board.vulnerability, plies=[], decisions=[],
                   start={str(k): dict(cards=int(len(l.M)), bidder=int(l.ok_bidder.sum()), truth_bidder=bool(l.ok_bidder[l.true_row]),
                                       score_seconds=round(l.score_seconds, 3)) for k, l in L.items()})
        for ply in range(START_PLY, 48):
            st = states[ply]
            o = st['o']
            c = cards[ply]
            legal = list(o.legal)
            k = o.controller
            led = st['trick'][0][1] // 13 if st['trick'] else None
            if len(legal) > 1:
                truth, _ = dds.solve(st['rem'], trump, st['leader'], st['trick'])
                rec['plies'].append(dict(ply=ply, actor=o.actor, controller=k, legal=legal, played=c,
                                         true_dd=[int(truth[x]) for x in legal]))
                l = L[k]
                fixed = [k, dummy]

                def solve(worlds):
                    solved = dds.solve_batch(worlds, trump, st['leader'], st['trick'], fixed_seats=fixed)
                    return np.array([[v[x] for x in legal] for v, _ in solved], float)
                alive = l.order[l.alive[l.order]]
                b_rows = alive[l.ok_bidder[alive]][:256]
                u_rows = alive[:32]
                n_rows, n_mult = l.resample(256, rng.random())
                s_rows, s_mult = l.resample(32, rng.random())
                need = sorted(set(b_rows.tolist()) | set(u_rows.tolist()) | set(n_rows.tolist()) | set(s_rows.tolist()))
                pos = {r: i for i, r in enumerate(need)}
                mat = solve(l.worlds(need, st))
                sub = lambda rows: mat[[pos[int(r)] for r in rows]]
                ws = WeightedSampler(o, belief.logits(o), 1.)
                v5 = solve([ws.draw(rng) for _ in range(32)])
                owner = {x: s for s in (l.A, l.B) for x in st['rem'][s]}
                lp_v5 = sum(ws.weights[i][ws.unknown.index(owner[x])] for i, x in enumerate(ws.cards)) - ws.partition(0, ws.caps)
                lw = l.logw[alive]
                mx = lw.max()
                lp_net = l.logw[l.true_row] - (mx + math.log(np.exp(lw - mx).sum()))
                pn = np.exp(lw - mx); pn /= pn.sum()
                rec['decisions'].append(dict(
                    ply=ply, n_cards=int(len(alive)), n_bidder=int(l.ok_bidder[alive].sum()),
                    lp_cards=round(-math.log(len(alive)), 4), lp_bidder=round(-math.log(max(int(l.ok_bidder[alive].sum()), 1)), 4),
                    lp_net=round(float(lp_net), 4), lp_v5=round(float(lp_v5), 4), net_eff=round(float(1 / (pn ** 2).sum()), 1),
                    v5=pick_weights(v5), uniform=pick_weights(sub(u_rows)),
                    blist=pick_weights(sub(b_rows)) if len(b_rows) else pick_weights(sub(u_rows)),
                    net=weighted_pick(sub(n_rows), n_mult), net32=weighted_pick(sub(s_rows), s_mult),
                    n_net_unique=int(len(n_rows))))
            for l in L.values():
                l.update(o.actor, c, led)
        rec['seconds'] = round(time.time() - t0, 1)
        out.write(json.dumps(rec) + '\n'); out.flush()
    out.close()


if __name__ == '__main__':
    main()
