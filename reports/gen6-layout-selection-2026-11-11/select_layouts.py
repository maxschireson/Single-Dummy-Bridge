"""Which layouts to solve: plain picks, evenly spaced picks, cluster centres, strata, most likely classes.

Copied from the "Bridge bidding and belief net" chat (its select_layouts.py, turn 41).

For every non-forced decision in tricks 1-5 after the lead, layouts are drawn from the
scorer-weighted class posterior (no bidder) and solved double-dummy:
  pool       256 independent draws
  reference  256 further independent draws, held out
Schemes choose a card from part of the pool (or from extra layouts) and are scored by the
reference's mean double-dummy value of that card. All schemes use the same posterior, so this
isolates the choice of layouts from the quality of the belief, with no true-deal noise.

  iid_N      the first N pool layouts, N = 4..256
  sys32      32 classes spaced evenly through the cumulative weight (the play test's method)
  top32      the 32 most likely classes, weighted by their posterior mass
  med_K      pool clustered into K groups; each group's centre solved, weighted by group size
  strat_K    same groups; one random member of each solved, weighted by group size

Usage: python select_layouts.py SCORER.npz OUT.jsonl START STOP STRIDE OFFSET
"""
import gzip
import json
import os
import sys
import time

os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbid import NumpyBidder, AuctionModel  # noqa: E402
from classes import ClassView, systematic  # noqa: E402
from play_classes import caches  # noqa: E402
from late_play import replay, ROOT  # noqa: E402
from bridge_harness.core import Board  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402

N_POOL, N_REF, LAST_PLY = 256, 256, 20
CARD_W = np.array([0.5] * 8 + [1.0, 1.5, 2.0, 3.0, 4.0])       # by rank: 2-9, T, J, Q, K, A


def features(worlds, a, unseen, trump):
    """Weighted description of seat a's hand in each layout: its unseen cards and its suit lengths."""
    x = np.zeros((len(worlds), len(unseen) + 4))
    col = {c: i for i, c in enumerate(unseen)}
    for r, w in enumerate(worlds):
        for c in w[a]:
            x[r, col[c]] = CARD_W[c % 13]
            x[r, len(unseen) + c // 13] += 3.0 if c // 13 == trump else 2.0
    return x


def kmedoids(D, k, rng, iters=20):
    n = len(D)
    med = [int(rng.integers(n))]
    d = D[med[0]].copy()
    while len(med) < k and d.sum() > 0:
        nxt = int(rng.choice(n, p=d / d.sum()))
        med.append(nxt)
        d = np.minimum(d, D[nxt])
    med = np.array(med)
    for _ in range(iters):
        lab = np.argmin(D[:, med], axis=1)
        new = med.copy()
        for j in range(len(med)):
            idx = np.flatnonzero(lab == j)
            if len(idx):
                new[j] = idx[np.argmin(D[np.ix_(idx, idx)].sum(axis=1))]
        if (new == med).all():
            break
        med = new
    return med, np.argmin(D[:, med], axis=1)


def pick(mean):
    best = np.isclose(mean, mean.max(), atol=1e-9)
    return (best / best.sum()).round(6).tolist()


def main():
    scorer_path, out_path, start, stop, stride, offset = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
    scorer = dict(np.load(scorer_path))
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)['index'] for l in open(out_path)}
    bidder = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
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
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)
        sc, _ = caches(board, am, scorer)
        nrng = np.random.default_rng([67, index])
        dummy, trump = board.contract.dummy, board.contract.trump
        rec = dict(index=index, contract=board.contract.text(), declarer=board.contract.declarer, decisions=[])
        for ply in range(1, LAST_PLY):
            st = states[ply]
            o = st['o']
            legal = list(o.legal)
            if len(legal) < 2:
                continue
            k = o.controller
            v = ClassView(o, st)
            a, b = v.hidden
            lw = v.logmult + sc[a].get(v.len_a, v.hon_a) + sc[b].get(v.len_b, v.hon_b)
            p = np.exp(lw - lw.max())
            p /= p.sum()
            draws = v.worlds(nrng.choice(len(p), N_POOL + N_REF, p=p), st, nrng)
            sys_w = v.worlds(systematic(lw, 32, nrng.random()), st, nrng)
            top = np.argsort(-p)[:32]
            top_w = v.worlds(top, st, nrng)
            solved = dds.solve_batch(draws + sys_w + top_w, trump, st['leader'], st['trick'], fixed_seats=[k, dummy])
            mat = np.array([[x[y] for y in legal] for x, _ in solved], float)
            pool, ref = mat[:N_POOL], mat[N_POOL:N_POOL + N_REF]
            truth, _ = dds.solve(st['rem'], trump, st['leader'], st['trick'])
            d = dict(ply=ply, classes=int(len(p)), effective=round(float(np.exp(-(p[p > 0] * np.log(p[p > 0])).sum())), 1),
                     ref=ref.mean(axis=0).round(5).tolist(), true_dd=[int(truth[x]) for x in legal], picks={})
            for n in (4, 8, 16, 32, 64, 128, 256):
                d['picks'][f'iid_{n}'] = pick(pool[:n].mean(axis=0))
            d['picks']['sys32'] = pick(mat[N_POOL + N_REF:N_POOL + N_REF + 32].mean(axis=0))
            d['picks']['top32'] = pick((p[top][:, None] * mat[N_POOL + N_REF + 32:]).sum(axis=0) / p[top].sum())
            d['top32_mass'] = round(float(p[top].sum()), 4)
            unseen = sorted(st['rem'][a] + st['rem'][b])
            x = features(draws[:N_POOL], a, unseen, trump)
            D = np.abs(x[:, None, :] - x[None, :, :]).sum(axis=2)
            for kk in (8, 16, 32, 64):
                med, lab = kmedoids(D, kk, nrng)
                size = np.bincount(lab, minlength=len(med)).astype(float)
                d['picks'][f'med_{kk}'] = pick((size[:, None] * pool[med]).sum(axis=0) / size.sum())
                rnd = np.array([nrng.choice(np.flatnonzero(lab == j)) if size[j] else med[j] for j in range(len(med))])
                d['picks'][f'strat_{kk}'] = pick((size[:, None] * pool[rnd]).sum(axis=0) / size.sum())
                if kk == 32:
                    d['clusters32'] = int(len(med))
            # added 11 Nov 01:50 UTC in the Gen6 package chat: evenly spaced picks at 64 (the package's tricks 3-5 setting)
            extra = dds.solve_batch(v.worlds(systematic(lw, 64, nrng.random()), st, nrng), trump, st['leader'], st['trick'], fixed_seats=[k, dummy])
            d['picks']['sys64'] = pick(np.array([[x[y] for y in legal] for x, _ in extra], float).mean(axis=0))
            rec['decisions'].append(d)
        rec['seconds'] = round(time.time() - t0, 1)
        out.write(json.dumps(rec) + '\n')
        out.flush()
    out.close()


if __name__ == '__main__':
    main()
