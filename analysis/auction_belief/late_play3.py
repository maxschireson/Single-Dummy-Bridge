import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Late-play test with a card-choice likelihood on the exact lists.

For every decision from trick 6 on, the deciding player's list (layouts consistent with
cards seen, show-outs and the bidding) is weighted by how likely the hidden players'
actual cards were in each layout, under a logit choice model on double-dummy loss:
    P(card | layout) = exp(-lambda * loss) / sum over that player's legal cards
with lambda fitted beforehand on other deals (fit_lambda.py). Every card the hidden
players have played counts, from the opening lead on, including cards that were forced
in the true layout (they need not be forced in another layout).

Arms, each choosing the card with the best mean double-dummy value:
  v5, uniform   32 layouts from the belief sampler / uniform over cards and show-outs
  list          up to CAP listed layouts, equal weights
  wl_u          the first CAP_W listed layouts, equal weights
  wl_all        the same layouts weighted by the choice likelihood of all earlier plays
  wl_late       the same layouts weighted by plays from trick 6 on only
Also stored: log posterior gain of the true layout from the weighting (nats).

Usage: python late_play3.py OUT.jsonl LAMBDA.json START STOP STRIDE OFFSET [CAP CAP_W]
"""
import gzip
import json
import os
import random
import sys
import time

os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbid import NumpyBidder, AuctionModel  # noqa: E402
from late_play import Lister, replay, pick_weights, START_PLY, ROOT  # noqa: E402
from bridge_harness.core import Board, card  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402
from bridge_harness.belief_capacity import Weights  # noqa: E402
from bridge_harness.bidding_sampling import WeightedSampler  # noqa: E402
from bridge_harness.sampling import Sampler  # noqa: E402


def group(ply, controller, declarer):
    if ply == 0:
        return 'lead'
    return ('dec' if controller == declarer else 'def') + ('_early' if ply < START_PLY else '_late')


def loglik(loss, cnt, lam):
    """log P(played card) for loss (tricks given up) and counts of legal cards at loss 0,1,2,3+."""
    z = sum(n * np.exp(-lam * l) for l, n in enumerate(cnt))
    return -lam * min(loss, 3) - np.log(z)


class History:
    """Choice likelihood of every hidden play, per listed layout, computed on demand and cached."""

    def __init__(self, L, states, cards, board, dds, lam):
        self.L, self.states, self.cards, self.dds, self.lam = L, states, cards, dds, lam
        self.dec, self.dummy, self.trump = board.contract.declarer, board.contract.dummy, board.contract.trump
        self.cache = {}                                   # (row, ply) -> log P(card played at ply | layout row)
        self.solves = 0
        self.played = {s: [(p, cards[p]) for p in range(52) if states[p]['o'].actor == s] for s in (L.A, L.B)}
        self.hidden_plies = [p for p in range(48) if states[p]['o'].controller != L.observer]

    def holding(self, row_mask, seat, q):
        base = self.L.U[row_mask if seat == self.L.A else ~row_mask]
        cardset = set(int(x) for x in base)
        for p, c in self.played[seat]:
            if q <= p < START_PLY:
                cardset.add(c)
            elif START_PLY <= p < q:
                cardset.discard(c)
        return tuple(sorted(cardset))

    def ensure(self, rows, upto):
        L = self.L
        for q in self.hidden_plies:
            if q >= upto:
                break
            need = [int(r) for r in rows if (int(r), q) not in self.cache]
            if not need:
                continue
            sq = self.states[q]
            worlds = []
            for r in need:
                hands = [None] * 4
                hands[L.observer] = sq['rem'][L.observer]
                hands[self.dummy] = sq['rem'][self.dummy]
                hands[L.A] = self.holding(L.M[r], L.A, q)
                hands[L.B] = self.holding(L.M[r], L.B, q)
                worlds.append(tuple(hands))
            solved = self.dds.solve_batch(worlds, self.trump, sq['leader'], sq['trick'], fixed_seats=[L.observer, self.dummy])
            self.solves += len(need)
            lam = self.lam[group(q, sq['o'].controller, self.dec)]
            c = self.cards[q]
            for r, (v, _) in zip(need, solved):
                mx = max(v.values())
                cnt = [0, 0, 0, 0]
                for x in v.values():
                    cnt[min(int(mx - x), 3)] += 1
                self.cache[(r, q)] = loglik(int(mx - v[c]), cnt, lam)

    def logw(self, rows, upto, late_only=False):
        qs = [q for q in self.hidden_plies if q < upto and (q >= START_PLY or not late_only)]
        return np.array([sum(self.cache[(int(r), q)] for q in qs) for r in rows])


def weighted_pick(mat, logw):
    w = np.exp(logw - logw.max())
    m = (w[:, None] * mat).sum(axis=0) / w.sum()
    best = np.isclose(m, m.max(), atol=1e-9)
    return (best / best.sum()).tolist(), float(w.sum() ** 2 / (w ** 2).sum())


def logmeanexp(x):
    m = x.max()
    return float(m + np.log(np.exp(x - m).mean()))


def main():
    out_path, lam_path, start, stop, stride, offset = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
    cap, cap_w = (int(sys.argv[7]), int(sys.argv[8])) if len(sys.argv) > 8 else (256, 128)
    lam = json.load(open(lam_path))
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
        rng = random.Random(1000003 * index + 17)
        dec, dummy, trump = board.contract.declarer, board.contract.dummy, board.contract.trump
        listers = {k: Lister(k, board, states, am, rng, cap) for k in range(4) if k != dummy}
        hist = {k: History(L, states, cards, board, dds, lam) for k, L in listers.items()}
        # true layout: log-likelihood of each play under the choice model
        true_ll = {}
        rec = dict(index=index, contract=board.contract.text(), declarer=dec, vulnerability=board.vulnerability,
                   list_start={str(k): [l.n_cards, int(len(l.M)), l.true_row >= 0] for k, l in listers.items()},
                   plies=[], decisions=[])
        for ply in range(52):
            st = states[ply]
            o = st['o']
            c = cards[ply]
            legal = list(o.legal)
            k = o.controller
            led = st['trick'][0][1] // 13 if st['trick'] else None
            if len(legal) > 1 and ply < 48:
                truth, _ = dds.solve(st['rem'], trump, st['leader'], st['trick'])
                true_dd = [int(truth[x]) for x in legal]
                mx = max(true_dd)
                cnt = [0, 0, 0, 0]
                for x in true_dd:
                    cnt[min(mx - x, 3)] += 1
                true_ll[ply] = loglik(mx - true_dd[legal.index(c)], cnt, lam[group(ply, k, dec)])
                rec['plies'].append(dict(ply=ply, actor=o.actor, controller=k, legal=legal, played=c, true_dd=true_dd))
                if ply >= START_PLY:
                    L, H = listers[k], hist[k]
                    rows = L.rows()
                    if len(rows):
                        fixed = [k, dummy]
                        solved = dds.solve_batch(L.worlds(rows, st), trump, st['leader'], st['trick'], fixed_seats=fixed)
                        mat = np.array([[v[x] for x in legal] for v, _ in solved], float)
                        ws = WeightedSampler(o, belief.logits(o), 1.)
                        v5 = dds.solve_batch([ws.draw(rng) for _ in range(32)], trump, st['leader'], st['trick'], fixed_seats=fixed)
                        us = Sampler(o)
                        un = dds.solve_batch([us.draw(rng) for _ in range(32)], trump, st['leader'], st['trick'], fixed_seats=fixed)
                        wr = rows[:cap_w]
                        H.ensure(wr, ply)
                        lw_all, lw_late = H.logw(wr, ply), H.logw(wr, ply, late_only=True)
                        t_all = sum(v for q, v in true_ll.items() if q < ply and states[q]['o'].controller != k)
                        t_late = sum(v for q, v in true_ll.items() if START_PLY <= q < ply and states[q]['o'].controller != k)
                        p_all, ess_all = weighted_pick(mat[:len(wr)], lw_all)
                        p_late, ess_late = weighted_pick(mat[:len(wr)], lw_late)
                        rec['decisions'].append(dict(
                            ply=ply, n_list=int(L.alive.sum()), n_solved=len(rows), n_w=len(wr),
                            list=pick_weights(mat), list32=pick_weights(mat[:32]), wl_u=pick_weights(mat[:len(wr)]),
                            wl_all=p_all, wl_late=p_late, ess_all=round(ess_all, 2), ess_late=round(ess_late, 2),
                            gain_all=round(t_all - logmeanexp(lw_all), 4), gain_late=round(t_late - logmeanexp(lw_late), 4),
                            v5=pick_weights(np.array([[v[x] for x in legal] for v, _ in v5], float)),
                            uniform=pick_weights(np.array([[v[x] for x in legal] for v, _ in un], float))))
            if ply >= START_PLY:
                for L in listers.values():
                    L.update(o.actor, c, led)
                    if L.true_row >= 0 and not L.alive[L.true_row]:
                        raise RuntimeError(f'true layout dropped at ply {ply} deal {index}')
        rec['seconds'] = round(time.time() - t0, 1)
        rec['history_solves'] = int(sum(h.solves for h in hist.values()))
        out.write(json.dumps(rec) + '\n'); out.flush()
    out.close()


if __name__ == '__main__':
    main()
