"""Conditional guarantees on recorded positions: outright, by shape, and with 1 to 3 named honours, under two
weightings of the layouts: 'b' the arena's hand-fit scorer (auction only), 'u' uniform over card-fit layouts.

usage: study.py POSITIONS.jsonl OUT.jsonl CARDS [--def ends] [--limit N] [--skip N] [--honours 3] [--maxnodes N]
                [--stride K] [--offset J] [--repo DIR --scorer FILE]

Appends one JSON line per position; positions already in OUT are skipped. Levels: `shape` (no named card); `h1` (one
named card, for each of up to three candidate runs, each refining `shape`); `h2` (the two best of those by the first
weighting, refining the better one); `h3` (all three, refining `h2`). The scorer weighting is searched first, so its
node counts are what it costs alone; the uniform weighting then reuses the solver's table.
"""
import json
import os
import sys
import time

from celllib import Solver, cards_of
from pipeline import Level, honour_runs, name, runs_of


def arg(flag, default, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


def load(p):
    q = dict(p)
    for k in ('hN', 'hS', 'pool', 'east'):
        q[k] = int(p[k], 16)
    return q


def evaluate(lv, pos, played_rep, keys, belief=None, do_outright=False):
    res = dict(named=[name(c) for c in cards_of(lv.named)], cells=len(lv.cells))
    if belief is not None:
        lv.add_weights('b', belief.cell_weights(lv.named))
    if do_outright:
        out = lv.outright()
        res['outright'] = None if out is None else {name(c): v for c, v in out.items()}
        res['outright_sec'], res['outright_nodes'] = lv.jstats['outright']['sec'], lv.jstats['outright']['nodes']
    lv.singles()
    true_i = lv.cell_index(pos['east'])
    res['true_cell'] = true_i
    res['true_single'] = {name(c): (lv.wins[true_i][c] if true_i is not None and lv.wins[true_i] is not None else None) for c in lv.reps}
    for key in keys:
        w = lv.weights[key]
        ceil = lv.ceiling(key)
        fl = lv.floors(key, must=[played_rep])
        best = max(fl, key=lambda c: fl[c]['floor']) if fl else None
        order = sorted(w, reverse=True)
        cum, t = [], 0.
        for x in order:
            t += x
            cum.append(t)
        js = lv.jstats.get(key, dict(sec=0., nodes=0, queries=0))
        res[key] = dict(dropped=lv.dropped[key],
                        mass_cells=[next((i + 1 for i in range(len(cum)) if cum[i] >= q - 1e-9), len(cum)) for q in (.5, .9, .95, .99)],
                        ceiling={name(c): round(v, 6) for c, v in ceil.items()},
                        floor={name(c): round(v['floor'], 6) for c, v in fl.items()},
                        whole={name(c): v['whole'] for c, v in fl.items()}, questions={name(c): v['questions'] for c, v in fl.items()},
                        set_size={name(c): len(v['set']) for c, v in fl.items()},
                        best=None if best is None else name(best), best_floor=0. if best is None else fl[best]['floor'],
                        best_ceiling=max(ceil.values()) if ceil else 0.,
                        best_set=[] if best is None else sorted(fl[best]['set']),
                        true_weight=None if true_i is None else w[true_i],
                        true_in_best=None if best is None or true_i is None else true_i in fl[best]['set'],
                        true_in_played=None if played_rep not in fl or true_i is None else true_i in fl[played_rep]['set'],
                        joint_sec=js['sec'], joint_nodes=js['nodes'], joint_queries=js['queries'])
    res.update({k: lv.stats[k] for k in ('single_sec', 'single_nodes', 'single_asked', 'capped', 'seed_failed')})
    return res


def main():
    src, out, cards = sys.argv[1], sys.argv[2], int(sys.argv[3])
    mode = arg('--def', 'ends')
    limit, skip = arg('--limit', 10 ** 9, int), arg('--skip', 0, int)
    stride, offset = arg('--stride', 1, int), arg('--offset', 0, int)
    max_h = arg('--honours', 3, int)
    maxnodes = arg('--maxnodes', 20000000, int)
    belief = None
    keys = ['u']
    if '--scorer' in sys.argv:
        from belief import Belief
        belief = Belief(arg('--repo', '.'), arg('--scorer', ''))
        keys = ['b', 'u']
    P = [json.loads(l) for l in open(src)]
    P = [p for p in P if p['cards'] == cards][skip:skip + limit]
    P = [p for i, p in enumerate(P) if i % stride == offset]
    seen = set()
    if os.path.exists(out):
        seen = {(r['table'], r['cards']) for r in map(json.loads, open(out))}
    f = open(out, 'a')
    sv = Solver('./cells', ('--def', mode, '--maxnodes', str(maxnodes)))
    for p in P:
        if (p['table'], p['cards']) in seen:
            continue
        pos = load(p)
        t0 = time.time()
        runs = runs_of(pos)
        played_rep = [r[0] for r in runs if pos['played'] in r][0]
        sv.reset()
        rec = {k: p[k] for k in ('table', 'board', 'contract', 'bot', 'game', 'cards', 'trick_no', 'need', 'made', 'declarer_tricks')}
        rec['played'] = name(played_rep)
        rec['trick_len'] = len(pos['trick'])
        rec['legal_runs'] = len(runs)
        if belief is not None:
            belief.prepare(p, pos)
            rec['layouts'], rec['effective_layouts'] = len(belief.east), belief.effective
            rec['true_layout_rel'] = belief.layout_weight(pos['east']) * len(belief.east)
        L0 = Level(sv, pos, 0)
        rec['shape'] = evaluate(L0, pos, played_rep, keys, belief, do_outright=True)
        cand = honour_runs(pos)
        rec['honour_runs'] = [dict(r, card=name(r['card'])) for r in cand]
        rec['h1'] = []
        any_out = rec['shape']['outright'] is not None and any(rec['shape']['outright'].values())
        if not any_out and max_h >= 1 and cand:
            L1 = []
            for r in cand[:3]:
                lv = Level(sv, pos, 1 << r['card'], parent=L0)
                rec['h1'].append(evaluate(lv, pos, played_rep, keys, belief))
                L1.append(lv)
            order = sorted(range(len(L1)), key=lambda i: -rec['h1'][i][keys[0]]['best_floor'])
            if max_h >= 2 and len(order) >= 2:
                L2 = Level(sv, pos, (1 << cand[order[0]]['card']) | (1 << cand[order[1]]['card']), parent=L1[order[0]])
                rec['h2'] = evaluate(L2, pos, played_rep, keys, belief)
                if max_h >= 3 and len(order) >= 3:
                    L3 = Level(sv, pos, sum(1 << cand[i]['card'] for i in order[:3]), parent=L2)
                    rec['h3'] = evaluate(L3, pos, played_rep, keys, belief)
        rec['seconds'] = time.time() - t0
        f.write(json.dumps(rec) + '\n')
        f.flush()
    sv.close()


if __name__ == '__main__':
    main()
