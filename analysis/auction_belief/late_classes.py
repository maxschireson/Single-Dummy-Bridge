import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Tricks 6-12 again for the tables of play_classes.py, with layout-level picks.

play_classes.py picks 32 classes and deals the low cards at random inside each, which leaves
sampling noise even when few layouts remain. Here each source instead takes 32 picks evenly
spaced over layouts, and every layout with its exact weight when 32 or fewer carry weight.
Only the scorer and bidder arms are redone; v5 and cards-only picks are read from the stored run.

Usage: python late_classes.py SCORER.npz OUT.jsonl START STOP STRIDE OFFSET
"""
import gzip
import json
import os
import sys
import time

os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbid import NumpyBidder, AuctionModel  # noqa: E402
from classes import ClassView  # noqa: E402
from play_classes import caches, N_LAYOUTS  # noqa: E402
from late_play import replay, ROOT  # noqa: E402
from bridge_harness.core import Board  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402


def weighted_pick(mat, w):
    m = (w[:, None] * mat).sum(axis=0) / w.sum()
    best = np.isclose(m, m.max(), atol=1e-9)
    return (best / best.sum()).tolist()


def main():
    scorer_path, out_path, start, stop, stride, offset = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
    first_ply = int(sys.argv[7]) if len(sys.argv) > 7 else 20
    scorer = dict(np.load(scorer_path))
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)['index'] for l in open(out_path)}
    bidder = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
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
        nrng = np.random.default_rng([71, index])
        dummy, trump = board.contract.dummy, board.contract.trump
        rec = dict(index=index, decisions=[])
        for ply in range(first_ply, 48):
            st = states[ply]
            o = st['o']
            legal = list(o.legal)
            if len(legal) < 2:
                continue
            k = o.controller
            v = ClassView(o, st)
            a, b = v.hidden
            lw = sc[a].get(v.len_a, v.hon_a) + sc[b].get(v.len_b, v.hon_b)
            good = ok[a].get(v.len_a, v.hon_a)
            sub = np.flatnonzero(good)
            good[sub] = ok[b].get(v.len_b[sub], v.hon_b[sub])

            def choose(logw):
                worlds, w = v.spaced_layouts(logw, N_LAYOUTS, nrng.random(), st)
                solved = dds.solve_batch(worlds, trump, st['leader'], st['trick'], fixed_seats=[k, dummy])
                return weighted_pick(np.array([[x[y] for y in legal] for x, _ in solved], float), w), len(worlds)
            d = dict(ply=ply)
            d['net_x'], d['net_n'] = choose(v.logmult + lw)
            if good.any():
                d['exact_x'], d['exact_n'] = choose(np.where(good, v.logmult, -np.inf))
            rec['decisions'].append(d)
        rec['seconds'] = round(time.time() - t0, 1)
        out.write(json.dumps(rec) + '\n')
        out.flush()
    out.close()


if __name__ == '__main__':
    main()
