import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
import gzip, json, sys, time, glob
import numpy as np
sys.path.insert(0, HERE)
from nbid import NumpyBidder
from gen import simulate, examples, deal, VUL_NAMES, COMP, types
from bridge_harness.core import Board, SEATS
from bridge_harness.bidding_env import CALLS
ROOT = FEED
b = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
files = sorted(glob.glob(ROOT + '/episodes/*.json.gz'))[:300]
boards = [Board.from_dict(json.load(gzip.open(f))['board']) for f in files]
hands = np.array([[list(h) for h in bd.hands] for bd in boards]); dealer = np.array([bd.dealer for bd in boards]); vul = np.array([VUL_NAMES.index(bd.vulnerability) for bd in boards])
t = time.time(); sim = simulate(b, hands, dealer, vul); dt = time.time() - t
same = 0; dec_ok = 0
for i, bd in enumerate(boards):
    got = tuple(CALLS[c] for c in sim['calls'][i] if c >= 0)
    same += got == tuple(bd.auction)
    dec_ok += (bd.contract is None and not sim['contract'][i]) or (bd.contract is not None and sim['declarer'][i] == bd.contract.declarer)
print('recorded auctions reproduced by the batched simulator: %d of %d; declarer matches %d; %.0f deals/s' % (same, len(boards), dec_ok, len(boards) / dt))
ex = examples(sim, hands, dealer, vul)
i = 0; k = ex['index'][0]; bd = boards[k]
print('example', bd.auction, 'declarer', SEATS[bd.contract.declarer], 'leader hand n', ex['n'][0], 'avail', ex['avail'][0], 'low', ex['low'][0])
print(' D_len', ex['D_len'][0], 'D_hon', ex['D_hon'][0], 'M_len', ex['M_len'][0], 'M_hon', ex['M_hon'][0], 'slots', ex['slots'][0][:12])
rng = np.random.default_rng(1); h, d, v = deal(rng, 4096)
t = time.time(); sim = simulate(b, h, d, v); dt = time.time() - t
print('random deals: %.0f deals/s single thread; contract share %.3f; mean calls %.1f; max calls %d; unfinished %d' % (4096 / dt, sim['contract'].mean(), sim['length'].mean(), sim['length'].max(), (~sim['finished']).sum()))
