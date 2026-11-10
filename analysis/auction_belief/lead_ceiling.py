import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Opening-lead ceiling test: exact auction-posterior worlds vs the belief sampler.

For each recorded common-auction deal, at the opening leader's decision:
  exact    layouts drawn from the exact posterior given own hand and auction
  belief   layouts from the frozen Gen5 belief sampler (the bot's own sampler)
  uniform  layouts uniform over the unseen cards (no auction information)
Every layout gets a double-dummy value for every legal lead. The true deal is
solved too, so any lead can be scored on it afterwards.

Usage: python lead_ceiling.py OUT.jsonl START STOP STRIDE OFFSET [n_exact n_belief n_uniform]
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
from exact import exact_posterior  # noqa: E402
from bridge_harness.core import Board, Game  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402
from bridge_harness.belief_capacity import Weights  # noqa: E402
from bridge_harness.bidding_sampling import WeightedSampler  # noqa: E402
from bridge_harness.sampling import Sampler  # noqa: E402

ROOT = FEED
HCP = np.array([max(0, c % 13 - 8) for c in range(52)])


def summary(world, hidden):
    """HCP and suit lengths of each hidden hand."""
    out = []
    for s in hidden:
        h = np.array(world[s])
        out.append([int(HCP[h].sum())] + [int((h // 13 == k).sum()) for k in range(4)])
    return out


def main():
    out_path, start, stop, stride, offset = sys.argv[1], *map(int, sys.argv[2:6])
    n_exact, n_belief, n_uniform = (map(int, sys.argv[6:9]) if len(sys.argv) >= 9 else (128, 192, 32))
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            try:
                done.add(json.loads(line)['index'])
            except Exception:
                pass
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
        board = Board.from_dict(ep['board'])
        if board.contract is None:
            out.write(json.dumps(dict(index=index, passed_out=True)) + '\n'); out.flush()
            continue
        o = Game(board).observation()
        leader = o.actor
        hidden = [s for s in range(4) if s != leader]
        legal = list(o.legal)
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
        true_ok = [bool(am.check(s, np.array([board.hands[s]]))[0]) for s in hidden]
        unknown = np.array(sorted(set(range(52)) - set(board.hands[leader])))
        nrng = np.random.default_rng([20261110, index])
        prng = random.Random(20261110 * 100003 + index)

        t = time.time()
        checks = [lambda h, s=s: am.check(s, h) for s in hidden]
        layouts, st = exact_posterior(unknown, checks, n_exact, nrng)
        t_exact = time.time() - t

        def world(triple):
            hands = [None] * 4
            hands[leader] = tuple(board.hands[leader])
            for s, h in zip(hidden, triple):
                hands[s] = tuple(sorted(int(c) for c in h))
            return tuple(hands)
        exact_worlds = [world(l) for l in layouts]

        t = time.time()
        sampler = WeightedSampler(o, belief.logits(o), 1.)
        belief_worlds = [sampler.draw(prng) for _ in range(n_belief)]
        usampler = Sampler(o)
        uniform_worlds = [usampler.draw(prng) for _ in range(n_uniform)]
        t_sample = time.time() - t

        def consistent(worlds):
            if not worlds:
                return []
            ok = np.ones(len(worlds), bool)
            for s in hidden:
                ok &= am.check(s, np.array([w[s] for w in worlds]))
            return [int(x) for x in ok]

        sets = dict(exact=exact_worlds, belief=belief_worlds, uniform=uniform_worlds)
        t = time.time()
        rec = dict(index=index, family=ep['family'], contract=board.contract.text(),
                   declarer=board.contract.declarer, leader=leader, vulnerability=board.vulnerability,
                   dealer=board.dealer, auction=list(board.auction), legal=legal, true_consistent=true_ok,
                   exact_stats=st, true_summary=summary(board.hands, hidden))
        truth, _ = dds.solve(board.hands, o.contract.trump, o.leader, o.trick)
        rec['true_dd'] = [int(truth[c]) for c in legal]
        for name, worlds in sets.items():
            if worlds:
                solved = dds.solve_batch(worlds, o.contract.trump, o.leader, o.trick, fixed_seats=[leader])
                rec[name + '_dd'] = [[int(v[c]) for c in legal] for v, _ in solved]
            else:
                rec[name + '_dd'] = []
            rec[name + '_summary'] = [summary(w, hidden) for w in worlds]
            rec[name + '_consistent'] = consistent(worlds)
        rec['seconds'] = dict(exact=round(t_exact, 2), sample=round(t_sample, 2), dds=round(time.time() - t, 2))
        out.write(json.dumps(rec) + '\n'); out.flush()
    out.close()


if __name__ == '__main__':
    main()
