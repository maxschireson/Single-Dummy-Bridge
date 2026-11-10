import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Evaluate the joint prototype on the recorded arena leads used in the ceiling test.

Per lead: likelihood of the true layout (nats over uniform), bidder pass rate of
sampled layouts, and double-dummy values of every legal lead in 64 sampled layouts
and in 64 layouts that passed the bidder filter ("net proposes, bidder checks").

Usage: python eval_joint.py MODEL.npz OUT.jsonl STRIDE OFFSET
"""
import glob
import gzip
import json
import os
import sys
import time

os.environ['BRIDGE_DDS_CACHE'] = ''
import numpy as np

sys.path.insert(0, HERE)
import joint  # noqa: E402
from nbid import NumpyBidder, AuctionModel  # noqa: E402
from gen import simulate, examples, VUL_NAMES  # noqa: E402
from analyze_leads import load  # noqa: E402
from bridge_harness.core import Board, Game  # noqa: E402
from bridge_harness.dds import DDS  # noqa: E402

ROOT = FEED


def main():
    model_path, out_path, stride, offset = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    n_dd = int(sys.argv[5]) if len(sys.argv) > 5 else 64
    p = dict(np.load(model_path))
    bidder = NumpyBidder(ROOT + '/artifacts/v5/bidder.keras')
    leads = [r for r in load(HERE + '/out/main_*.jsonl*') if not r.get('passed_out')]
    boards = {r['index']: Board.from_dict(json.load(gzip.open(f"{ROOT}/episodes/{r['index']:06d}.json.gz"))['board']) for r in leads}
    idx = [r['index'] for r in leads]
    hands = np.array([[list(h) for h in boards[i].hands] for i in idx])
    dealer = np.array([boards[i].dealer for i in idx])
    vul = np.array([VUL_NAMES.index(boards[i].vulnerability) for i in idx])
    sim = simulate(bidder, hands, dealer, vul)
    ex = examples(sim, hands, dealer, vul)
    row_of = {idx[k]: j for j, k in enumerate(ex['index'])}
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)['index'] for l in open(out_path)}
    dds = DDS(cache_path='')
    out = open(out_path, 'a')
    for r in leads:
        i = r['index']
        if i % stride != offset or i in done or i not in row_of:
            continue
        j = row_of[i]
        board = boards[i]
        o = Game(board).observation()
        leader = o.actor
        D, M, P = (leader + 3) % 4, (leader + 1) % 4, (leader + 2) % 4
        assert D == board.contract.declarer
        legal = list(o.legal)
        assert legal == r['legal']
        rng = np.random.default_rng([7, i])
        row = {k: v[j] for k, v in ex.items() if k != 'index'}
        b = joint.prepare(ex, np.array([j]))
        nats, (l1, l2, lg) = joint.nats(p, b)
        am = AuctionModel(bidder, board.dealer, board.vulnerability, board.auction)

        def worlds_from(types):
            out_w = []
            for d_, m_, p_ in joint.deal_cards(board.hands[leader], types, rng):
                w = [None] * 4
                w[leader] = tuple(board.hands[leader]); w[D] = tuple(d_); w[M] = tuple(m_); w[P] = tuple(p_)
                out_w.append(tuple(w))
            return out_w

        def passes(ws):
            ok = np.ones(len(ws), bool)
            for s in (D, M, P):
                ok &= am.check(s, np.array([w[s] for w in ws]))
            return ok
        t = time.time()
        ty = joint.sample(p, row, 256, rng)
        plain = worlds_from(ty)
        ok = passes(plain)
        kept = [w for w, good in zip(plain, ok) if good]
        logw = list((ty['log_n'] - ty['logq'])[ok])      # importance weights of consistent proposals: layouts per type / model probability
        proposals, n_pass = 256, int(ok.sum())
        while (len(kept) < n_dd and proposals < 8192) or proposals < 2304:
            ty = joint.sample(p, row, 512, rng)
            more = worlds_from(ty)
            good = passes(more)
            kept += [w for w, g_ in zip(more, good) if g_]
            logw += list((ty['log_n'] - ty['logq'])[good])
            proposals += 512; n_pass += int(good.sum())
        t_sample = time.time() - t
        lw = np.array(logw)
        if len(lw):
            mx = lw.max(); wn = np.exp(lw - mx)
            log_u = float(mx + np.log(wn.sum() / proposals) - joint.LOG_N_TOTAL)   # estimate of log share of uniform layouts that are consistent
            ess = float(wn.sum() ** 2 / (wn ** 2).sum())
        else:
            log_u, ess = None, 0.0
        rec = dict(index=i, nats=float(nats[0]), logp_parts=[float(l1[0]), float(l2[0]), float(lg[0])],
                   pass_first256=float(ok.mean()), proposals=proposals, passed=n_pass, legal=legal,
                   log_u_from_model=log_u, ess=ess)
        t = time.time()
        if n_dd == 0:
            rec['seconds'] = dict(sample=round(t_sample, 2))
            out.write(json.dumps(rec) + '\n'); out.flush()
            continue
        solved = dds.solve_batch(plain[:n_dd], o.contract.trump, o.leader, o.trick, fixed_seats=[leader])
        rec['model_dd'] = [[int(v[c]) for c in legal] for v, _ in solved]
        rec['model_consistent'] = [int(x) for x in ok[:n_dd]]
        if len(kept) >= 32:
            solved = dds.solve_batch(kept[:n_dd], o.contract.trump, o.leader, o.trick, fixed_seats=[leader])
            rec['filtered_dd'] = [[int(v[c]) for c in legal] for v, _ in solved]
        else:
            rec['filtered_dd'] = []
        rec['seconds'] = dict(sample=round(t_sample, 2), dds=round(time.time() - t, 2))
        out.write(json.dumps(rec) + '\n'); out.flush()
    out.close()


if __name__ == '__main__':
    main()
