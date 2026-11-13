"""E9-25: conditional claims' floors under two weightings of the layouts, BEN 64 defending (g9, Gen 9).

'b': the arena's hand-fit scorer for both hidden seats (cells/belief.py, as the cells study and E9-24).
'g': Gen 9's reading: a hidden seat played by ben64 is read by replaying BEN's own bidding net
     (bridge_harness/cards/replay.py ReplayReader on feature/gen9, BenLstmBidder on --ben, eps 0.02) on each
     layout's hand type; any other seat by the scorer, as Gen 9 reads a house bot. Without --ben (a dry run) both
     weightings are the scorer's.

Shape level only (no named cards). One JSON line per position, resumable.

usage: python3 e925_study.py POSITIONS.jsonl OUT.jsonl CARDS KIND --cells CELLS_DIR --repo REPO --scorer SCORER.npz
                             [--ben BEN_BIDDER.keras --ben-sha SHA256] [--limit N] [--stride K] [--offset J]
"""
import json
import os
import sys
import time

import numpy as np


def arg(flag, default=None, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


CELLS, REPO = arg('--cells'), arg('--repo')
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


def ben_replay(path, expect_sha):
    """BEN's bidding net replayed on hand types (ReplayReader of feature/gen9), identity checked."""
    sys.path.insert(0, REPO)
    from bridge_harness.cards.replay import ReplayReader
    r = ReplayReader(path, eps=EPS)
    if expect_sha:
        assert r.sha256 == expect_sha, (r.sha256, expect_sha)
    return r


class Gen9Belief(Belief):
    """Belief with each hidden seat read by its own model: ben64 by replay, others by the scorer."""

    def __init__(self, repo, scorer_path, replay):
        super().__init__(repo, scorer_path)
        self.replay = replay

    def prepare(self, p, pos):
        sc = self.scorer
        d = 'ben64' if p['kind'] == 'ben_defends' else 'house'
        bots = {str(p['e_real']): d, str(p['w_real']): d}
        replay = self.replay

        class Mixed:
            def type_log_score(self_, length, hon, seat, dealer, vul, auction):
                if bots.get(str(seat)) == 'ben64' and replay is not None:
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
    replay = ben_replay(arg('--ben'), arg('--ben-sha')) if arg('--ben') else None
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
        rec['g_reader'] = 'ben-replay' if replay is not None else 'scorer (dry run)'
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
