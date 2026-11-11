"""How much a scorer's deal-list weights know about the true layout, on recorded Gen 6 tables.

At every decision from --tricks with two hidden hands and at most --max-layouts card-fit layouts,
list every layout (the Gen 6 engine's View.every, as the bot does) and record, in nats:

  uniform   log P(true layout) with equal weights = -log(n)
  <scorer>  log P(true layout) with the scorer's weights (both hidden hands' original thirteen
            cards, as Gen6Player.layout_log_weights), also with the log-weights times each --alphas
  exact     log P(true layout) when the weights are 1 for layouts in which both hidden hands
            reproduce their seats' calls under the bidder (greedy) and 0 otherwise

Information = scorer - uniform. Only the root table of each recorded board is used (forks repeat it).

  python info_test.py --feed DIR --bidder BIDDER.keras --out rows.jsonl --scorers v0=a.npz v1=b.npz
                      [--first 0 --last 400 --tricks 6-12 --max-layouts 20000 --pairs 6-32~6-32 --worker 0 --workers 1]
"""
import argparse
import glob
import gzip
import json
import math
import os
import sys
import time

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('--feed', required=True)
ap.add_argument('--bidder', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--scorers', nargs='+', required=True)
ap.add_argument('--first', type=int, default=0)
ap.add_argument('--last', type=int, default=10 ** 9)
ap.add_argument('--tricks', default='6-12')
ap.add_argument('--max-layouts', type=int, default=20000)
ap.add_argument('--pairs', default='6-32~6-32')
ap.add_argument('--alphas', default='0.5,0.75,1,1.25,1.5,2')
ap.add_argument('--worker', type=int, default=0)
ap.add_argument('--workers', type=int, default=1)
a = ap.parse_args()

sys.path.insert(0, os.path.join(a.feed, 'runtime'))
sys.path.insert(0, os.environ.get('AUCTION_BELIEF', 'analysis/auction_belief'))   # research/joint-auction-belief-20261110's analysis/auction_belief, patched
from bridge_harness.core import Board, Game, card  # noqa: E402
from bridge_harness.gen6 import View  # noqa: E402
from bridge_harness.gen6_nets import FitScorer, hand_types  # noqa: E402
from nbid import NumpyBidder, AuctionModel  # noqa: E402

lo, hi = (int(x) for x in a.tricks.split('-'))
alphas = [float(x) for x in a.alphas.split(',')]
pairs = set(a.pairs.split(','))
names = [s.split('=')[0] for s in a.scorers]
scorers = {s.split('=')[0]: FitScorer(s.split('=', 1)[1]) for s in a.scorers}
bidder = NumpyBidder(a.bidder)


def logsumexp(x):
    m = x.max()
    return m + math.log(np.exp(x - m).sum())


def packed(length, hon):
    return (length * (14 ** np.arange(4))).sum(axis=1) * 32 ** 4 + (hon * (32 ** np.arange(4))).sum(axis=1)


files = sorted(glob.glob(os.path.join(a.feed, 'episodes', '*.json.gz')))
files = [f for f in files if a.first <= int(os.path.basename(f)[:6]) < a.last]
files = files[a.worker::a.workers]
out = open(a.out, 'w')
t0, n_dec = time.time(), 0
for f in files:
    ep = json.load(gzip.open(f))
    if ep.get('pair') not in pairs:
        continue
    for tk, e in ep['unique_tables'].items():
        if 'tables' not in e or not e['tables']:
            continue
        board = Board.from_dict(e['board'])
        if board.contract is None:
            continue
        game = Game(board)
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
        fit_cache = {}
        for k, act in enumerate(e['tables'][0]['actions']):
            o = game.observation()
            trick = len(o.history) // 4 + 1
            if lo <= trick <= hi and len(o.legal) > 1:
                view = View(o)
                if len(view.hidden) == 2 and view.count() <= a.max_layouts:
                    assign = view.every()
                    hid = view.hidden
                    truth = np.array([0 if int(c) in board.hands[hid[0]] else 1 for c in view.unseen], np.int8)
                    true_row = np.flatnonzero((assign == truth).all(axis=1))
                    assert len(true_row) == 1, 'true layout must be listed exactly once'
                    t = int(true_row[0])
                    n = len(assign)
                    rec = dict(ep=int(os.path.basename(f)[:6]), table=tk, ply=k, trick=trick, n=n,
                               decider=o.controller, uniform=-math.log(n))
                    types = []
                    for j in range(2):
                        member = view.original(assign, j)
                        types.append((member, *hand_types(member)))
                    for name in names:
                        sc = scorers[name]
                        logw = sum(sc.type_log_score(types[j][1], types[j][2], hid[j], o.dealer, o.vulnerability, o.auction)
                                   for j in range(2))
                        rec[name] = {str(al): float(al * logw[t] - logsumexp(al * logw)) for al in alphas}
                    fits = np.ones(n, bool)
                    for j in range(2):
                        member, length, hon = types[j]
                        key = packed(length, hon)
                        uniq, first, inv = np.unique(key, return_index=True, return_inverse=True)
                        need = [u for u in uniq if (hid[j], int(u)) not in fit_cache]
                        if need:
                            pos = first[np.searchsorted(uniq, need)]
                            hands = np.argsort(-member[pos], axis=1, kind='stable')[:, :13]
                            ok = am.check(hid[j], hands)
                            for u, v in zip(need, ok):
                                fit_cache[(hid[j], int(u))] = bool(v)
                        fits &= np.array([fit_cache[(hid[j], int(u))] for u in uniq])[inv.ravel()]
                    assert fits[t], 'the true layout must reproduce the auction'
                    rec['exact'] = -math.log(int(fits.sum()))
                    rec['n_fit'] = int(fits.sum())
                    out.write(json.dumps(rec) + '\n')
                    n_dec += 1
            game.play(card(act['card']))
    out.flush()
print(f'worker {a.worker}: {n_dec} decisions from {len(files)} files in {time.time() - t0:.0f}s', flush=True)
