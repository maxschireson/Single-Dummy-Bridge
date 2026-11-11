"""Does the arena's BEN bid as its base network does? Replays every seat's calls in native
6-32~ben tables with the NumPy bidder: BEN seats with BEN's base net, Gen 6 seats with the Gen 6 bidder.

  SDB_FEED=FEED/recovery AUCTION_BELIEF=path/to/analysis/auction_belief python ben_check.py
"""
import glob
import gzip
import json
import os
import sys

import numpy as np

F = os.environ['SDB_FEED']
sys.path.insert(0, os.path.join(F, 'runtime'))
sys.path.insert(0, os.environ.get('AUCTION_BELIEF', 'analysis/auction_belief'))
from bridge_harness.core import Board  # noqa: E402
from nbid import NumpyBidder, AuctionModel  # noqa: E402

nets = {'ben': NumpyBidder(F + '/assets/bidding/ben.keras'), 'g6': NumpyBidder(F + '/artifacts/gen6/bidder.keras')}
ok, tot, tables = dict(ben=0, g6=0), dict(ben=0, g6=0), 0
for f in sorted(glob.glob(F + '/episodes/*.json.gz')):
    ep = json.load(gzip.open(f))
    if ep['pair'] != '6-32~ben':
        continue
    board = Board.from_dict(ep['board'])
    for bd in ep['bidding'].values():
        if 'ben' not in bd['bidders']:
            continue
        tables += 1
        calls = [d['call'] for d in bd['decisions']]
        for s in range(4):
            who = 'ben' if bd['bidders'][s] == 'ben' else 'g6'
            am = AuctionModel(nets[who], board.dealer, board.vulnerability, calls)
            tot[who] += 1
            ok[who] += bool(am.check(s, np.array([board.hands[s]]))[0])
print(f'tables with BEN seats: {tables}; seats whose calls the network reproduces: '
      + ', '.join(f'{k} {ok[k]}/{tot[k]}' for k in ok))
