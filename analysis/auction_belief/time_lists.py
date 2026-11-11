import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
import gzip, json, os, random, sys, time
os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np
sys.path.insert(0, HERE)
import late_play
from late_play import Lister, replay, ROOT
from nbid import NumpyBidder, AuctionModel
from bridge_harness.core import Board
bidder = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
res = {}
for index in range(1400, 1416):
    ep = json.load(gzip.open(f'{ROOT}/episodes/{index:06d}.json.gz')); t = ep['unique_tables'][ep['regimes']['common']['tables'][0]]
    board = Board.from_dict(t['board']); acts = t['tables'][0]['actions'] if board.contract is not None else []
    if len(acts) != 52: continue
    states = replay(board, acts); am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
    for start in (16, 20, 24):
        late_play.START_PLY = start
        for k in range(4):
            if k == board.contract.dummy: continue
            t0 = time.process_time(); L = Lister(k, board, states, am, random.Random(1), 256); dt = time.process_time() - t0
            res.setdefault(start, []).append((dt, L.n_cards, len(L.M)))
for start, rows in sorted(res.items()):
    a = np.array(rows)
    print(f'list built at start of trick {start//4+1}: CPU seconds per player mean {a[:,0].mean():.2f}, median {np.median(a[:,0]):.2f}, max {a[:,0].max():.2f}; candidate layouts median {np.median(a[:,1]):.0f} (max {a[:,1].max():.0f}); layouts kept after bidding median {np.median(a[:,2]):.0f}, mean {a[:,2].mean():.0f}, 90th pct {np.percentile(a[:,2], 90):.0f} (n={len(a)})')
