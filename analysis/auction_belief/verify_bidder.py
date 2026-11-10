import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
import gzip, json, sys, time, glob
import numpy as np
sys.path.insert(0, HERE)
from nbid import NumpyBidder, AuctionModel, RUNTIME
from bridge_harness.core import Board
ROOT = FEED
b = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
files = sorted(glob.glob(ROOT + '/episodes/*.json.gz'))[:int(sys.argv[1])]
ok = bad = passed_out = 0; seat_checks = 0
t0 = time.time()
for f in files:
    ep = json.load(gzip.open(f)); board = Board.from_dict(ep['board'])
    if board.contract is None: passed_out += 1
    am = AuctionModel(b, board.dealer, board.vulnerability, board.auction)
    good = all(am.check(s, np.array([board.hands[s]]))[0] for s in range(4)); seat_checks += 4
    ok += good; bad += not good
    if not good: print('MISMATCH', f, board.auction)
print('episodes', len(files), 'auctions reproduced by numpy bidder', ok, 'mismatch', bad, 'passed out', passed_out, 'time %.1fs' % (time.time() - t0))
# speed: first-call checks on random hands
ep = json.load(gzip.open(files[0])); board = Board.from_dict(ep['board'])
am = AuctionModel(b, board.dealer, board.vulnerability, board.auction)
rng = np.random.default_rng(0)
hands = np.argsort(rng.random((32768, 52)), axis=1)[:, :13]
for seat in range(4):
    t = time.time(); r = am.check(seat, hands); dt = time.time() - t
    print('seat', seat, 'calls', [am.calls[k] for k in range((seat - board.dealer) % 4, len(am.calls), 4)], 'accept %.4f' % r.mean(), 'steps', am.last_steps, '%.0f hands/s' % (len(hands) / dt), '%.0f steps/s' % (am.last_steps / dt))
