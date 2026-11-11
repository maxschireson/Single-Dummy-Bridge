"""Cost of weighting the Gen 6 deal list exactly with the bidder instead of the scorer.

For every deal-list decision (as info_test.py) time: listing the layouts, the scorer weights
(Gen 6's FitScorer with its per-deal type cache) and the exact bidder check (hand types
deduplicated per seat, verdicts cached per deal and seat). One core, NumPy.

  python time_exact.py --feed DIR --bidder B.keras --scorer S.npz --out rows.jsonl [--first 0 --last 400 --worker 0 --workers 1]
"""
import argparse, glob, gzip, json, os, sys, time
import numpy as np

ap = argparse.ArgumentParser()
for k in ('--feed', '--bidder', '--scorer', '--out'):
    ap.add_argument(k, required=True)
ap.add_argument('--first', type=int, default=0)
ap.add_argument('--last', type=int, default=10 ** 9)
ap.add_argument('--tricks', default='6-12')
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
bidder = NumpyBidder(a.bidder)
files = sorted(glob.glob(os.path.join(a.feed, 'episodes', '*.json.gz')))
files = [f for f in files if a.first <= int(os.path.basename(f)[:6]) < a.last][a.worker::a.workers]
out = open(a.out, 'w')
for f in files:
    ep = json.load(gzip.open(f))
    if ep.get('pair') != '6-32~6-32':
        continue
    e = ep['unique_tables']['table-0']
    board = Board.from_dict(e['board'])
    if board.contract is None:
        continue
    game = Game(board)
    scorers = {}                                      # one scorer (and type cache) per deciding player, as at the table
    t = time.perf_counter()
    am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
    setup = time.perf_counter() - t
    cache, seen_seats = {}, set()
    for k, act in enumerate(e['tables'][0]['actions']):
        o = game.observation()
        trick = len(o.history) // 4 + 1
        if lo <= trick <= hi and len(o.legal) > 1:
            view = View(o)
            if len(view.hidden) == 2 and view.count() <= 20000:
                t0 = time.perf_counter()
                assign = view.every()
                types = [hand_types(view.original(assign, j)) + (view.original(assign, j),) for j in range(2)]
                t1 = time.perf_counter()
                sc = scorers.setdefault(o.controller, FitScorer(a.scorer))
                logw = sum(sc.type_log_score(types[j][0], types[j][1], view.hidden[j], o.dealer, o.vulnerability, o.auction) for j in range(2))
                t2 = time.perf_counter()
                fits, checked, uniq_n = np.ones(len(assign), bool), 0, 0
                for j in range(2):
                    length, hon, member = types[j]
                    key = (length * (14 ** np.arange(4))).sum(axis=1) * 32 ** 4 + (hon * (32 ** np.arange(4))).sum(axis=1)
                    uniq, first, inv = np.unique(key, return_index=True, return_inverse=True)
                    uniq_n += len(uniq)
                    need = [i for i, u in enumerate(uniq) if (o.controller, view.hidden[j], int(u)) not in cache]
                    if need:
                        hands = np.argsort(-member[first[need]], axis=1, kind='stable')[:, :13]
                        ok = am.check(view.hidden[j], hands)
                        checked += len(need)
                        for i, v in zip(need, ok):
                            cache[(o.controller, view.hidden[j], int(uniq[i]))] = bool(v)
                    fits &= np.array([cache[(o.controller, view.hidden[j], int(u))] for u in uniq])[inv.ravel()]
                t3 = time.perf_counter()
                first_for_seat = o.controller not in seen_seats
                seen_seats.add(o.controller)
                out.write(json.dumps(dict(ep=ep['index'], trick=trick, n=len(assign), uniq=uniq_n, checked=checked,
                                          first=first_for_seat, t_list=t1 - t0, t_scorer=t2 - t1, t_exact=t3 - t2)) + '\n')
        game.play(card(act['card']))
    out.flush()
