import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Whole-play decision test (every trick after the opening lead) on recorded common-auction tables.

Each player weights hand-type classes (classes.py) instead of listing layouts, so the same
method runs from trick 1 to trick 12. Every non-forced decision is made from 32 layouts per
source and scored double-dummy on the true deal:
  v5       the bot's belief sampler (current behaviour)
  uniform  layouts that fit the cards and show-outs only
  net      classes weighted by the hand-fit scorer (no bidder consulted)
  exact    classes whose two hidden hands pass the Gen5 bidder test (ceiling, offline only)
Also stored: log posterior of the true layout under each source, class counts and timings.

Usage: python play_classes.py SCORER.npz OUT.jsonl START STOP STRIDE OFFSET
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
from nbid import NumpyBidder, AuctionModel, CALL_ID  # noqa: E402
import fit  # noqa: E402
from classes import ClassView, TypeCache, rep_hands, logsumexp, systematic  # noqa: E402
from late_play import replay, pick_weights, ROOT  # noqa: E402
from bridge_harness.core import Board, card, vulnerable  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402
from bridge_harness.belief_capacity import Weights  # noqa: E402
from bridge_harness.bidding_sampling import WeightedSampler  # noqa: E402
from bridge_harness.sampling import Sampler  # noqa: E402

N_LAYOUTS = 32


def caches(board, am, scorer):
    """Per-seat memo of scorer log-scores and bidder verdicts by hand type."""
    calls = np.array([[CALL_ID[c] for c in am.calls]])
    sc, ok = {}, {}
    for seat in range(4):
        own, opp = vulnerable(board.vulnerability, seat), vulnerable(board.vulnerability, (seat + 1) % 4)
        auc = fit.auction_onehot(calls, [board.dealer], [seat])[0]

        def score(length, hon, own=own, opp=opp, auc=auc):
            return np.concatenate([fit.log_score(scorer, length[s:s + 32768], hon[s:s + 32768], own, opp, auc)
                                   for s in range(0, len(length), 32768)])
        sc[seat] = TypeCache(score, np.float64)
        ok[seat] = TypeCache(lambda length, hon, seat=seat: am.check(seat, rep_hands(length, hon)), bool)
    return sc, ok


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
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
        sc, ok = caches(board, am, scorer)
        rng = random.Random(1000003 * index + 53)
        nrng = np.random.default_rng([53, index])
        dummy, trump = board.contract.dummy, board.contract.trump
        rec = dict(index=index, contract=board.contract.text(), declarer=board.contract.declarer,
                   vulnerability=board.vulnerability, calls=len(am.calls), plies=[], decisions=[])
        for ply in range(1, 48):
            st = states[ply]
            o = st['o']
            legal = list(o.legal)
            if len(legal) < 2:
                continue
            k = o.controller
            truth, _ = dds.solve(st['rem'], trump, st['leader'], st['trick'])
            rec['plies'].append(dict(ply=ply, actor=o.actor, controller=k, legal=legal, played=card(acts[ply]['card']),
                                     true_dd=[int(truth[x]) for x in legal]))
            c0 = time.process_time()
            v = ClassView(o, st)
            a, b = v.hidden
            c1 = time.process_time()
            lw = sc[a].get(v.len_a, v.hon_a) + sc[b].get(v.len_b, v.hon_b)
            c2 = time.process_time()
            good = ok[a].get(v.len_a, v.hon_a)
            sub = np.flatnonzero(good)
            good[sub] = ok[b].get(v.len_b[sub], v.hon_b[sub])
            c3 = time.process_time()
            z_cards = logsumexp(v.logmult)
            z_net = logsumexp(v.logmult + lw)
            z_bid = logsumexp(v.logmult[good]) if good.any() else float('-inf')

            def solve(worlds):
                solved = dds.solve_batch(worlds, trump, st['leader'], st['trick'], fixed_seats=[k, dummy])
                return np.array([[x[y] for y in legal] for x, _ in solved], float)
            d = dict(ply=ply, classes=int(len(v.idx)), lp_cards=round(-z_cards, 4), lp_net=round(float(lw[v.true] - z_net), 4),
                     lp_bidder=round(-z_bid, 4) if good[v.true] else None, truth_ok=bool(good[v.true]),
                     t_build=round(c1 - c0, 3), t_score=round(c2 - c1, 3), t_bidder=round(c3 - c2, 3))
            d['net'] = pick_weights(solve(v.worlds(systematic(v.logmult + lw, N_LAYOUTS, nrng.random()), st, nrng)))
            if good.any():
                gi = np.flatnonzero(good)
                d['exact'] = pick_weights(solve(v.worlds(gi[systematic(v.logmult[gi], N_LAYOUTS, nrng.random())], st, nrng)))
            ws = WeightedSampler(o, belief.logits(o), 1.)
            d['v5'] = pick_weights(solve([ws.draw(rng) for _ in range(N_LAYOUTS)]))
            owner = {x: s for s in (a, b) for x in st['rem'][s]}
            d['lp_v5'] = round(float(sum(ws.weights[i][ws.unknown.index(owner[x])] for i, x in enumerate(ws.cards))
                                     - ws.partition(0, ws.caps)), 4)
            us = Sampler(o)
            d['uniform'] = pick_weights(solve([us.draw(rng) for _ in range(N_LAYOUTS)]))
            rec['decisions'].append(d)
        rec['seconds'] = round(time.time() - t0, 1)
        rec['evaluated'] = dict(scorer=int(sum(c.evaluated for c in sc.values())), bidder=int(sum(c.evaluated for c in ok.values())))
        out.write(json.dumps(rec) + '\n')
        out.flush()
    out.close()


if __name__ == '__main__':
    main()
