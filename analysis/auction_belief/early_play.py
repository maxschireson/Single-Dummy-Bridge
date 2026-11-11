import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Early-play decision test (tricks 1-5 after the opening lead) on recorded common-auction tables.

Every non-forced decision is made from four layout sets and scored double-dummy on the true deal:
  v5        32 layouts from the bot's belief sampler (current behaviour)
  uniform   32 layouts uniform over cards and show-outs
  exact32   32 layouts from the exact auction posterior: uniform over layouts in which both
            hidden seats' original 13 cards pass the Gen5 bidder test (rejection sampling)
  exact64   64 such layouts

Usage: python early_play.py OUT.jsonl START STOP STRIDE OFFSET
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
from gen import types  # noqa: E402
from bridge_harness.core import vulnerable  # noqa: E402
from late_play import replay, pick_weights, START_PLY, ROOT  # noqa: E402
from bridge_harness.core import Board, card  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402
from bridge_harness.belief_capacity import Weights  # noqa: E402
from bridge_harness.bidding_sampling import WeightedSampler  # noqa: E402
from bridge_harness.sampling import Sampler  # noqa: E402

MAX_FIRST, MAX_TOPUP = 200000, 60000


def exact_layouts(pool, o, st, am, nrng, need):
    """Uniform draws over layouts consistent with cards, show-outs and the bidding.

    `pool` holds this player's earlier accepted layouts (52-wide membership of seat a's original hand).
    Rows that the cards played since have ruled out are dropped, which leaves exact draws from the
    current posterior; fresh rejection draws top the pool up. Returns worlds, proposals used.
    """
    hidden = [s for s in range(4) if o.known_hands[s] is None]
    a, b = hidden
    played = {s: [c for seat, c in o.history if seat == s] for s in hidden}
    unseen = np.array(sorted(st['rem'][a] + st['rem'][b]))
    ka = len(st['rem'][a])
    voids = set()
    for i, (seat, c) in enumerate(o.history):
        led = o.history[i - i % 4][1] // 13
        if c // 13 != led and seat in hidden:
            voids.add((seat, led))
    first = pool.get('MA') is None
    MA = np.zeros((0, 52), bool) if first else pool['MA']
    if len(MA):
        ok = MA[:, played[a]].all(axis=1) & ~MA[:, played[b]].any(axis=1)
        for (seat, s) in voids:
            cols = unseen[unseen // 13 == s]
            if len(cols):
                ok &= ~(MA[:, cols].any(axis=1) if seat == a else (~MA[:, cols]).any(axis=1))
        MA = MA[ok]
    proposals, limit = 0, (MAX_FIRST if first else MAX_TOPUP)
    while len(MA) < need and proposals < limit:
        n = 4096
        perm = nrng.permuted(np.broadcast_to(unseen, (n, len(unseen))), axis=1)
        proposals += n
        A, B = perm[:, :ka], perm[:, ka:]
        ok = np.ones(n, bool)
        for (seat, s) in voids:
            side = A if seat == a else B
            ok &= ~(side // 13 == s).any(axis=1)
        A, B = A[ok], B[ok]
        if not len(A):
            continue
        ha = np.concatenate([A, np.tile(np.array(played[a], np.int64), (len(A), 1))], axis=1)
        good = am.check(a, ha)
        ha, B = ha[good], B[good]
        if not len(ha):
            continue
        hb = np.concatenate([B, np.tile(np.array(played[b], np.int64), (len(B), 1))], axis=1)
        good = am.check(b, hb)
        if good.any():
            add = np.zeros((int(good.sum()), 52), bool)
            np.put_along_axis(add, ha[good], True, axis=1)
            MA = np.concatenate([MA, add])
    pool['MA'] = MA
    worlds = []
    un = set(int(c) for c in unseen)
    for row in MA[:need]:
        hands = [None] * 4
        for s in range(4):
            if o.known_hands[s] is not None:
                hands[s] = st['rem'][s]
        hands[a] = tuple(c for c in sorted(un) if row[c])
        hands[b] = tuple(c for c in sorted(un) if not row[c])
        worlds.append(tuple(hands))
    return worlds, proposals


def net_layouts(scorer, ctx, o, st, nrng, need, n=4096):
    """Layouts that fit the cards, resampled in proportion to the hand-fit scorer's weight (no bidder)."""
    hidden = [s for s in range(4) if o.known_hands[s] is None]
    a, b = hidden
    played = {s: [c for seat, c in o.history if seat == s] for s in hidden}
    unseen = np.array(sorted(st['rem'][a] + st['rem'][b]))
    ka = len(st['rem'][a])
    perm = nrng.permuted(np.broadcast_to(unseen, (n, len(unseen))), axis=1)
    A, B = perm[:, :ka], perm[:, ka:]
    ok = np.ones(n, bool)
    for i, (seat, c) in enumerate(o.history):
        led = o.history[i - i % 4][1] // 13
        if c // 13 != led and seat in hidden:
            side = A if seat == a else B
            ok &= ~(side // 13 == led).any(axis=1)
    A, B = A[ok], B[ok]
    logw = np.zeros(len(A))
    for seat, part in ((a, A), (b, B)):
        hands = np.concatenate([part, np.tile(np.array(played[seat], np.int64), (len(part), 1))], axis=1)
        mem = np.zeros((len(hands), 52), np.float32)
        np.put_along_axis(mem, hands, 1.0, axis=1)
        ln, hon, _ = types(mem)
        uniq, inv = np.unique(np.concatenate([ln, hon], axis=1), axis=0, return_inverse=True)
        own, opp, auc = ctx[seat]
        logw += fit.log_score(scorer, uniq[:, :4], uniq[:, 4:], own, opp, auc)[inv.ravel()]
    pr = np.exp(logw - logw.max()); pr /= pr.sum()
    picks = np.searchsorted(np.cumsum(pr), (nrng.random() + np.arange(need)) / need, side='left').clip(max=len(pr) - 1)
    uniq, mult = np.unique(picks, return_counts=True)
    worlds = []
    for r in uniq:
        hands = [None] * 4
        for s in range(4):
            if o.known_hands[s] is not None:
                hands[s] = st['rem'][s]
        hands[a] = tuple(sorted(int(c) for c in A[r]))
        hands[b] = tuple(sorted(int(c) for c in B[r]))
        worlds.append(tuple(hands))
    return worlds, mult, float(1 / (pr ** 2).sum())


def main():
    out_path, start, stop, stride, offset = sys.argv[1], *map(int, sys.argv[2:6])
    scorer = dict(np.load(sys.argv[6])) if len(sys.argv) > 6 else None
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
        rng = random.Random(1000003 * index + 29)
        nrng = np.random.default_rng([31, index])
        dummy, trump = board.contract.dummy, board.contract.trump
        rec = dict(index=index, contract=board.contract.text(), declarer=board.contract.declarer,
                   vulnerability=board.vulnerability, plies=[], decisions=[])
        pools = {k: {} for k in range(4)}
        ctx = {}
        if scorer is not None:
            calls = np.array([[CALL_ID[c] for c in am.calls]])
            for seat in range(4):
                ctx[seat] = (vulnerable(board.vulnerability, seat), vulnerable(board.vulnerability, (seat + 1) % 4),
                             fit.auction_onehot(calls, [board.dealer], [seat])[0])
        for ply in range(1, START_PLY):
            st = states[ply]
            o = st['o']
            legal = list(o.legal)
            if len(legal) < 2:
                continue
            k = o.controller
            fixed = [k, dummy]
            truth, _ = dds.solve(st['rem'], trump, st['leader'], st['trick'])
            rec['plies'].append(dict(ply=ply, actor=o.actor, controller=k, legal=legal, played=card(acts[ply]['card']),
                                     true_dd=[int(truth[x]) for x in legal]))
            ex, proposals = exact_layouts(pools[k], o, st, am, nrng, 64)
            if len(ex) < 8:
                rec['decisions'].append(dict(ply=ply, proposals=proposals, found=len(ex)))
                continue

            def picks(worlds):
                solved = dds.solve_batch(worlds, trump, st['leader'], st['trick'], fixed_seats=fixed)
                return np.array([[v[x] for x in legal] for v, _ in solved], float)
            mat = picks(ex)
            ws = WeightedSampler(o, belief.logits(o), 1.)
            us = Sampler(o)
            extra = {}
            if scorer is not None:
                for name, need in (('net32', 32),):
                    nw, mult, eff = net_layouts(scorer, ctx, o, st, nrng, need)
                    nm = picks(nw)
                    mean = (mult[:, None] * nm).sum(axis=0) / mult.sum()
                    best = np.isclose(mean, mean.max(), atol=1e-9)
                    extra[name] = (best / best.sum()).tolist()
                    extra[name + '_eff'] = round(eff, 1)
            rec['decisions'].append(dict(
                ply=ply, proposals=proposals, found=len(ex), **extra,
                exact64=pick_weights(mat), exact32=pick_weights(mat[:32]),
                v5=pick_weights(picks([ws.draw(rng) for _ in range(32)])),
                uniform=pick_weights(picks([us.draw(rng) for _ in range(32)]))))
        rec['seconds'] = round(time.time() - t0, 1)
        out.write(json.dumps(rec) + '\n'); out.flush()
    out.close()


if __name__ == '__main__':
    main()
