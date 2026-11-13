"""E9-24: conditional claims' floors under two weightings of the layouts (g9, Gen 9).

'b': the arena's hand-fit scorer for both hidden seats (cells/belief.py, as the cells study).
'g': Gen 9's reading: a hidden seat played by 8c-32 is read by replaying 8c-32's own rule bidder (the Gen 8 launch
     source at 792c4cb, identity f50e95de checked) on each layout's hand type, P(call) = (1 - eps) [the bidder makes
     it] + eps / (legal calls), eps 0.02 (as bridge_harness/cards/replay.py RuleReplay on feature/gen9); any other
     seat by the scorer, as Gen 9 reads a house bot.

Shape level only (no named cards). One JSON line per position, resumable.

usage: python3 e924_study.py POSITIONS.jsonl OUT.jsonl CARDS KIND --cells CELLS_DIR --repo REPO --g8 G8_LAUNCH_DIR
                             --scorer SCORER.npz --manifest FEED_MANIFEST.json [--limit N] [--stride K] [--offset J]
"""
import json
import os
import sys
import time

import numpy as np


def arg(flag, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


CELLS, REPO, G8 = arg('--cells'), arg('--repo'), arg('--g8')
sys.path.insert(0, CELLS)
from belief import Belief                     # noqa: E402
from celllib import Solver, cards_of          # noqa: E402
from pipeline import Level, name, runs_of     # noqa: E402
from study import evaluate, load              # noqa: E402

VULS = ('None', 'NS', 'EW', 'Both')
EPS = 0.02


def type_hand(length, hon):
    """bridge_harness/cards/rb_meanings.type_hand (feature/gen9): lengths and A K Q J T bits, spots from the two up."""
    cards = []
    for s in range(4):
        h, n = int(hon[s]), int(length[s])
        top = [12 - j for j in range(5) if h >> j & 1]
        cards += [13 * s + r for r in top]
        cards += [13 * s + r for r in range(n - len(top))]
    return cards


class Replay:
    """8c-32's own bidder replayed on hand types (RuleReplay of feature/gen9, on the Gen 8 launch bidder)."""

    def __init__(self, g8, settings, expect_sha):
        sys.path.insert(0, g8)
        from bridge_harness import rule_bidder as rb
        from bridge_harness.bidding_env import CALL_ID, legal_mask
        self.b = rb.from_package(settings=settings)
        assert self.b.sha256 == expect_sha, (self.b.sha256, expect_sha)
        self.CALL_ID, self.legal_mask = CALL_ID, legal_mask
        self.cache = {}

    def type_log_score(self, length, hon, seat, dealer, vul, auction):
        calls = tuple(auction)
        turns = [(t, c) for t, c in enumerate(calls) if (dealer + t) % 4 == seat]
        legal = {t: int(self.legal_mask(dealer, calls[:t]).sum()) for t, _ in turns}
        toks = [self.CALL_ID[c] for c in calls]
        vi = VULS.index(vul)
        length = np.asarray(length, np.int64).reshape(-1, 4)
        hon = np.asarray(hon, np.int64).reshape(-1, 4)
        packed = (length * (14 ** np.arange(4))).sum(1) * 32 ** 4 + (hon * (32 ** np.arange(4))).sum(1)
        uniq, first, inverse = np.unique(packed, return_index=True, return_inverse=True)
        key0 = (calls, dealer, vul, seat)
        known = self.cache.setdefault(key0, {})
        for k, i in zip(uniq, first):
            if int(k) in known:
                continue
            hand = type_hand(length[i], hon[i])
            v = 0.
            for t, c in turns:
                hit = int(self.b.call(hand, int(seat), int(dealer), vi, toks[:t])) == self.CALL_ID[c]
                v += np.log((1 - EPS) * hit + EPS / legal[t])
            known[int(k)] = float(v)
        if len(self.cache) > 64:
            self.cache = {key0: known}
        return np.array([known[int(k)] for k in uniq])[inverse.ravel()]


class Gen9Belief(Belief):
    """Belief with each hidden seat read by its own model: 8c-32 by replay, others by the scorer."""

    def __init__(self, repo, scorer_path, replay):
        super().__init__(repo, scorer_path)
        self.replay = replay

    def prepare(self, p, pos):
        sc = self.scorer
        d = '8c-32' if p['kind'] == 'precision_defends' else 'house'
        bots = {str(p['e_real']): d, str(p['w_real']): d}
        replay = self.replay

        class Mixed:
            def type_log_score(self_, length, hon, seat, dealer, vul, auction):
                if bots.get(str(seat)) == '8c-32':
                    return replay.type_log_score(length, hon, seat, dealer, vul, auction)
                return sc.type_log_score(length, hon, seat, dealer, vul, auction)
        self.scorer = Mixed()
        try:
            return super().prepare(p, pos)
        finally:
            self.scorer = sc


def main():
    src, out, cards, kind = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    limit, stride, offset = arg('--limit', 10 ** 9, int), arg('--stride', 1, int), arg('--offset', 0, int)
    manifest = json.load(open(arg('--manifest')))
    bidder = manifest['bots']['8c-32']['bidder']
    replay = Replay(G8, bidder['options']['settings'], bidder['sha256'])
    b_belief = Belief(REPO, arg('--scorer'))
    g_belief = Gen9Belief(REPO, arg('--scorer'), replay)
    P = [json.loads(l) for l in open(src)]
    P = [p for p in P if p['cards'] == cards and p['kind'] == kind]
    P = [p for i, p in enumerate(P) if i % stride == offset][:limit]
    seen = set()
    if os.path.exists(out):
        seen = {(r['table'], r['cards']) for r in map(json.loads, open(out))}
    f = open(out, 'a')
    here = os.getcwd()
    os.chdir(CELLS)
    sv = Solver('./cells', ('--def', 'ends', '--maxnodes', '20000000'))
    os.chdir(here)
    for p in P:
        if (p['table'], p['cards']) in seen:
            continue
        pos = load(p)
        t0 = time.time()
        runs = runs_of(pos)
        played_rep = [r[0] for r in runs if pos['played'] in r][0]
        sv.reset()
        rec = {k: p[k] for k in ('table', 'board', 'contract', 'bot', 'game', 'cards', 'trick_no', 'need', 'made', 'kind', 'defenders')}
        b_belief.prepare(p, pos)
        g_belief.prepare(p, pos)
        rec['layouts'] = len(b_belief.east)
        rec['eff_b'], rec['eff_g'] = b_belief.effective, g_belief.effective
        rec['true_w_b'] = b_belief.layout_weight(pos['east'])
        rec['true_w_g'] = g_belief.layout_weight(pos['east'])
        t1 = time.time()
        lv = Level(sv, pos, 0)
        lv.add_weights('b', b_belief.cell_weights(0))
        lv.add_weights('g', g_belief.cell_weights(0))
        rec['shape'] = evaluate(lv, pos, played_rep, ['b', 'g'], None, do_outright=True)
        out_any = rec['shape']['outright'] is not None and any(rec['shape']['outright'].values())
        if '--named' in sys.argv and not out_any:
            from pipeline import honour_runs
            cand = honour_runs(pos)[:3]
            L1, h1 = [], []
            for r in cand:
                l1 = Level(sv, pos, 1 << r['card'], parent=lv)
                l1.add_weights('b', b_belief.cell_weights(1 << r['card']))
                l1.add_weights('g', g_belief.cell_weights(1 << r['card']))
                h1.append(evaluate(l1, pos, played_rep, ['b', 'g'], None))
                L1.append(l1)
            rec['h1'] = h1
            for key in ('b', 'g'):
                order = sorted(range(len(L1)), key=lambda i: -h1[i][key]['best_floor'])
                if len(order) >= 2:
                    named = (1 << cand[order[0]]['card']) | (1 << cand[order[1]]['card'])
                    l2 = Level(sv, pos, named, parent=L1[order[0]])
                    l2.add_weights(key, (b_belief if key == 'b' else g_belief).cell_weights(named))
                    rec['h2_' + key] = evaluate(l2, pos, played_rep, [key], None)
                elif len(order) == 1:
                    rec['h2_' + key] = {key: h1[order[0]][key]}
        rec['sec_weights'], rec['sec_solver'] = t1 - t0, time.time() - t1
        f.write(json.dumps(rec) + '\n')
        f.flush()
    sv.close()


if __name__ == '__main__':
    main()
