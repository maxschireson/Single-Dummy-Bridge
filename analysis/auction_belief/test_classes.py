import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Checks for classes.py against layout listing (late_net.py records) and against gen.types.

Usage: python test_classes.py SCORER.npz [TABLES]
"""
import gzip
import json
import math
import os
import sys
import time

os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbid import NumpyBidder, AuctionModel, CALL_ID  # noqa: E402
import fit  # noqa: E402
from gen import types  # noqa: E402
from classes import ClassView, TypeCache, rep_hands, logsumexp, pack, unpack  # noqa: E402
from late_play import replay, ROOT  # noqa: E402
from analyze_late import load  # noqa: E402
from bridge_harness.core import Board, card, vulnerable  # noqa: E402


def caches(board, am, scorer):
    calls = np.array([[CALL_ID[c] for c in am.calls]])
    sc, ok = {}, {}
    for seat in range(4):
        own, opp = vulnerable(board.vulnerability, seat), vulnerable(board.vulnerability, (seat + 1) % 4)
        auc = fit.auction_onehot(calls, [board.dealer], [seat])[0]

        def score(length, hon, own=own, opp=opp, auc=auc):
            return np.concatenate([fit.log_score(scorer, length[s:s + 32768], hon[s:s + 32768], own, opp, auc)
                                   for s in range(0, len(length), 32768)])
        sc[seat] = TypeCache(score, np.float64)
        ok[seat] = TypeCache(lambda length, hon, seat=seat: am.check(seat, rep_hands(length, hon)), bool)
    return sc, ok


def main():
    scorer = dict(np.load(sys.argv[1]))
    bidder = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
    ref = {r['index']: r for r in load(os.path.dirname(os.path.abspath(__file__)) + '/out/net_[01].jsonl*')}
    # 1. rep_hands and pack/unpack round trip through gen.types
    rng = np.random.default_rng(0)
    deck = rng.permuted(np.broadcast_to(np.arange(52), (2000, 52)), axis=1)[:, :13]
    mem = np.zeros((2000, 52), np.float32)
    np.put_along_axis(mem, deck, 1.0, axis=1)
    ln, hon, _ = types(mem)
    l2, h2 = unpack(pack(ln, hon))
    assert (l2 == ln).all() and (h2 == hon).all()
    mem2 = np.zeros((2000, 52), np.float32)
    np.put_along_axis(mem2, rep_hands(ln, hon), 1.0, axis=1)
    ln3, hon3, _ = types(mem2)
    assert (ln3 == ln).all() and (hon3 == hon).all()
    print('types round trip ok')
    # 2. class sums against layout listing at plies >= 20
    worst = 0.0
    n_checked = 0
    for index in sorted(ref)[:int(sys.argv[2]) if len(sys.argv) > 2 else 6]:
        ep = json.load(gzip.open(f'{ROOT}/episodes/{index:06d}.json.gz'))
        t = ep['unique_tables'][ep['regimes']['common']['tables'][0]]
        board = Board.from_dict(t['board'])
        acts = t['tables'][0]['actions']
        states = replay(board, acts)
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
        sc, ok = caches(board, am, scorer)
        for d in ref[index]['decisions']:
            st = states[d['ply']]
            o = st['o']
            v = ClassView(o, st)
            a, b = v.hidden
            n_cards = round(math.exp(logsumexp(v.logmult)))
            good = ok[a].get(v.len_a, v.hon_a) & ok[b].get(v.len_b, v.hon_b)
            n_bid = round(math.exp(logsumexp(v.logmult[good]))) if good.any() else 0
            lw = sc[a].get(v.len_a, v.hon_a) + sc[b].get(v.len_b, v.hon_b)
            lp_net = lw[v.true] - logsumexp(v.logmult + lw)
            assert n_cards == d['n_cards'], (index, d['ply'], n_cards, d['n_cards'])
            assert n_bid == d['n_bidder'], (index, d['ply'], n_bid, d['n_bidder'])
            assert good[v.true]
            worst = max(worst, abs(lp_net - d['lp_net']))
            n_checked += 1
            # worlds: drawn layouts match their class and the cards
            w = v.worlds([v.true, 0, len(v.idx) - 1], st, rng)
            for hands in w:
                assert sorted(hands[a] + hands[b]) == sorted(st['rem'][a] + st['rem'][b]) and len(hands[a]) == len(st['rem'][a])
    print(f'{n_checked} late decisions: layout counts (cards, bidder) equal; largest |lp_net difference| {worst:.5f}')
    # 3. timing and sizes at early plies
    for index in (1400, 1401, 1402, 1403, 1404, 1405):
        ep = json.load(gzip.open(f'{ROOT}/episodes/{index:06d}.json.gz'))
        t = ep['unique_tables'][ep['regimes']['common']['tables'][0]]
        board = Board.from_dict(t['board'])
        acts = t['tables'][0]['actions'] if board.contract is not None else []
        if len(acts) != 52:
            continue
        states = replay(board, acts)
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
        sc, ok = caches(board, am, scorer)
        line = []
        for ply in range(1, 20):
            st = states[ply]
            o = st['o']
            if len(o.legal) < 2:
                continue
            t0 = time.time()
            v = ClassView(o, st)
            a, b = v.hidden
            t1 = time.time()
            lw = sc[a].get(v.len_a, v.hon_a) + sc[b].get(v.len_b, v.hon_b)
            t2 = time.time()
            ga = ok[a].get(v.len_a, v.hon_a)
            good = ga.copy()
            good[ga] = ok[b].get(v.len_b[ga], v.hon_b[ga])
            t3 = time.time()
            line.append(f'ply {ply}: classes {len(v.idx)}, layouts e^{logsumexp(v.logmult):.1f}, bidder e^{logsumexp(v.logmult[good]):.1f}, '
                        f'build {t1-t0:.2f}s score {t2-t1:.2f}s bidder {t3-t2:.2f}s; nats bidder {-logsumexp(v.logmult[good]) + logsumexp(v.logmult):.2f} '
                        f'scorer {lw[v.true] - logsumexp(v.logmult + lw) + logsumexp(v.logmult):.2f}')
        print(index, board.contract.text(), ' '.join(board.auction))
        for x in line[:6]:
            print('   ', x)


if __name__ == '__main__':
    main()
