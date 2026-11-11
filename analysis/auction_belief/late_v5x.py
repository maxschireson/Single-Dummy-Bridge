import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Tricks 6-12 for the tables of play_classes.py: v5 and cards-only beliefs with layout-level picks.

The bot's sampler draws 32 layouts with replacement from the v5 belief. Here every layout that fits
the cards is listed (at most 12,870 from trick 6), given its exact v5 probability, and 32 picks are
taken evenly spaced through the cumulative weight, or every layout with its exact weight when 32 or
fewer remain. That is the same selection late_classes.py uses for the scorer and bidder arms, so the
comparison between beliefs no longer mixes in how the layouts were picked.
  v5x    v5 belief, layout-level picks
  unix   cards and show-outs only, layout-level picks
Stored: lp_v5_list, the listed v5 log-probability of the true layout (must equal the sampler's own).

Usage: python late_v5x.py OUT.jsonl START STOP STRIDE OFFSET
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
import nbid  # noqa: F401,E402  (puts the runtime on the path)
from late_play import combos, replay, ROOT  # noqa: E402
from late_classes import weighted_pick  # noqa: E402
from bridge_harness.core import Board  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402
from bridge_harness.belief_capacity import Weights  # noqa: E402
from bridge_harness.bidding_sampling import WeightedSampler  # noqa: E402

N_LAYOUTS = 32


def spaced_rows(logw, m, u):
    p = np.exp(logw - logw.max())
    p /= p.sum()
    if len(p) <= m:
        return np.arange(len(p)), p
    picks = np.searchsorted(np.cumsum(p), (u + np.arange(m)) / m, side='right').clip(max=len(p) - 1)
    rows, counts = np.unique(picks, return_counts=True)
    return rows, counts / m


def main():
    out_path, start, stop, stride, offset = sys.argv[1], *map(int, sys.argv[2:6])
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)['index'] for l in open(out_path)}
    belief = Weights(ROOT + '/artifacts/v5/belief.npz')
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
        nrng = np.random.default_rng([73, index])
        dummy, trump = board.contract.dummy, board.contract.trump
        rec = dict(index=index, decisions=[])
        for ply in range(20, 48):
            st = states[ply]
            o = st['o']
            legal = list(o.legal)
            if len(legal) < 2:
                continue
            k = o.controller
            a, b = [s for s in range(4) if o.known_hands[s] is None]
            U = np.array(sorted(st['rem'][a] + st['rem'][b]))
            ka = len(st['rem'][a])
            idx = combos(len(U), ka)
            M = np.zeros((len(idx), len(U)), bool)
            np.put_along_axis(M, idx, True, axis=1)
            hist = o.history
            keep = np.ones(len(M), bool)
            for i, (seat, c) in enumerate(hist):
                led = hist[i - i % 4][1] // 13
                if c // 13 != led and seat in (a, b):
                    cols = U // 13 == led
                    keep &= ~(M[:, cols].any(axis=1) if seat == a else (~M[:, cols]).any(axis=1))
            M = M[keep]
            ws = WeightedSampler(o, belief.logits(o), 1.)
            assert set(ws.cards) == set(U.tolist()) and set(ws.unknown) == {a, b}
            pos = {c: i for i, c in enumerate(ws.cards)}
            wa = np.array([ws.weights[pos[c]][ws.unknown.index(a)] for c in U.tolist()])
            wb = np.array([ws.weights[pos[c]][ws.unknown.index(b)] for c in U.tolist()])
            logw = np.where(M, wa, wb).sum(axis=1)
            truth = np.isin(U, st['rem'][a])
            true_row = int(np.flatnonzero((M == truth).all(axis=1))[0])
            mx = logw.max()
            lp = float(logw[true_row] - (mx + math.log(np.exp(logw - mx).sum())))

            def choose(lw):
                rows, w = spaced_rows(lw, N_LAYOUTS, nrng.random())
                worlds = []
                for r in rows:
                    hands = [st['rem'][s] for s in range(4)]
                    hands[a] = tuple(int(c) for c in U[M[r]])
                    hands[b] = tuple(int(c) for c in U[~M[r]])
                    worlds.append(tuple(hands))
                solved = dds.solve_batch(worlds, trump, st['leader'], st['trick'], fixed_seats=[k, dummy])
                return weighted_pick(np.array([[x[y] for y in legal] for x, _ in solved], float), w)
            rec['decisions'].append(dict(ply=ply, layouts=int(len(M)), lp_v5_list=round(lp, 4),
                                         v5x=choose(logw), unix=choose(np.zeros(len(M)))))
        rec['seconds'] = round(time.time() - t0, 1)
        out.write(json.dumps(rec) + '\n')
        out.flush()
    out.close()


if __name__ == '__main__':
    main()
