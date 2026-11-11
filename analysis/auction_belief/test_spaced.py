import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Checks for ClassView.world and ClassView.spaced_layouts: full coverage, exact weights, unbiased picks.

Usage: python test_spaced.py SCORER.npz
"""
import gzip, itertools, json, os, sys
os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbid import NumpyBidder, AuctionModel
from classes import ClassView
from play_classes import caches
from late_play import replay, ROOT
from bridge_harness.core import Board

scorer = dict(np.load(sys.argv[1]))
bidder = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
rng = np.random.default_rng(3)
n_views = n_small = n_big = 0
worst = 0.0
for index in (1400, 1401, 1402, 1405):
    ep = json.load(gzip.open(f'{ROOT}/episodes/{index:06d}.json.gz'))
    t = ep['unique_tables'][ep['regimes']['common']['tables'][0]]
    board = Board.from_dict(t['board'])
    states = replay(board, t['tables'][0]['actions'])
    am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
    sc, ok = caches(board, am, scorer)
    for ply in range(24, 48):
        st = states[ply]; o = st['o']
        if len(o.legal) < 2:
            continue
        v = ClassView(o, st); a, b = v.hidden
        mult = np.rint(np.exp(v.logmult)).astype(int)
        # 1. every layout of every class, against brute force over the unseen cards
        mine = {v.world(i, j, st) for i in range(len(v.idx)) for j in range(mult[i])}
        assert len(mine) == mult.sum()
        unseen = sorted(st['rem'][a] + st['rem'][b]); hist = o.history
        voids = {(seat, hist[i - i % 4][1] // 13) for i, (seat, c) in enumerate(hist) if c // 13 != hist[i - i % 4][1] // 13 and seat in (a, b)}
        brute = set()
        for ha in itertools.combinations(unseen, len(st['rem'][a])):
            hb = tuple(c for c in unseen if c not in ha)
            if any(c // 13 == s for c in ha for (seat, s) in voids if seat == a) or any(c // 13 == s for c in hb for (seat, s) in voids if seat == b):
                continue
            hands = [st['rem'][s] for s in range(4)]; hands[a], hands[b] = ha, hb
            brute.add(tuple(hands))
        assert mine == brute, (index, ply, len(mine), len(brute))
        assert st['rem'][a] in {w[a] for w in mine}
        n_views += 1
        # 2. weights
        lw = v.logmult + sc[a].get(v.len_a, v.hon_a) + sc[b].get(v.len_b, v.hon_b)
        p = np.exp(lw - lw.max()); p /= p.sum()
        target = {v.world(i, j, st): p[i] / mult[i] for i in range(len(v.idx)) for j in range(mult[i])}
        if mult.sum() <= 32:
            worlds, w = v.spaced_layouts(lw, 32, rng.random(), st)
            assert len(worlds) == mult.sum() and abs(w.sum() - 1) < 1e-9
            assert max(abs(target[x] - y) for x, y in zip(worlds, w)) < 1e-9
            n_small += 1
        else:
            acc = {x: 0.0 for x in target}
            reps = 400
            for _ in range(reps):
                worlds, w = v.spaced_layouts(lw, 32, rng.random(), st)
                assert abs(w.sum() - 1) < 1e-9 and len(set(worlds)) == len(worlds)
                for x, y in zip(worlds, w):
                    acc[x] += y / reps
            # each layout's mean weight equals its probability; a layout never gets more than ceil(32 p)/32
            worst = max(worst, max(abs(acc[x] - target[x]) for x in target))
            n_big += 1
print(f'{n_views} views: classes expand to exactly the brute-force layouts; {n_small} small posteriors returned in full with exact weights; '
      f'{n_big} larger ones: largest |mean pick weight - probability| over 400 repeats {worst:.4f}')
