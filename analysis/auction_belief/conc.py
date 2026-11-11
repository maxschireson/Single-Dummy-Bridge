import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""How concentrated is the scorer-weighted posterior over hand-type classes, by trick?

Usage: python conc.py SCORER.npz START STOP
"""
import gzip, json, os, sys
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
rows = {}
tables = 0
for index in range(int(sys.argv[2]), int(sys.argv[3])):
    ep = json.load(gzip.open(f'{ROOT}/episodes/{index:06d}.json.gz'))
    t = ep['unique_tables'][ep['regimes']['common']['tables'][0]]
    board = Board.from_dict(t['board'])
    acts = t['tables'][0]['actions'] if board.contract is not None else []
    if len(acts) != 52:
        continue
    tables += 1
    states = replay(board, acts)
    am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
    sc, _ = caches(board, am, scorer)
    for ply in range(1, 48):
        st = states[ply]; o = st['o']
        if len(o.legal) < 2:
            continue
        v = ClassView(o, st); a, b = v.hidden
        lw = v.logmult + sc[a].get(v.len_a, v.hon_a) + sc[b].get(v.len_b, v.hon_b)
        p = np.exp(lw - lw.max()); p /= p.sum()
        q = np.sort(p)[::-1]; c = np.cumsum(q)
        ent = -(p[p > 0] * np.log(p[p > 0])).sum()
        rows.setdefault(ply // 4 + 1, []).append((len(p), np.exp(ent), c[min(31, len(c) - 1)], c[min(255, len(c) - 1)],
                                                  int(np.searchsorted(c, 0.5) + 1), int(np.searchsorted(c, 0.9) + 1), int(np.searchsorted(c, 0.99) + 1)))
print(f'{tables} tables')
print('trick     n  classes  effective  top-32 mass  top-256 mass  classes for 50%   90%   99%  (medians)')
for t in sorted(rows):
    a = np.array(rows[t])
    m = np.median(a, axis=0)
    print(f'{t:5d} {len(a):5d} {m[0]:8.0f} {m[1]:10.0f} {m[2]:12.2f} {m[3]:13.2f} {m[4]:16.0f} {m[5]:5.0f} {m[6]:5.0f}')
