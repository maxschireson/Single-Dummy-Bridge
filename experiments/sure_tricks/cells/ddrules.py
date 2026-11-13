"""Certified floors against double-dummy values, card by card, on recorded positions without an outright claim.

usage: ddrules.py POSITIONS.jsonl OUT.jsonl CARDS --repo DIR --scorer FILE [--samples 64] [--stride K --offset J] [--named 2] [--limit N]

Per position and per card (one per run of touching cards):
  F0, in0   certified probability at the shape level (scorer weights), and whether the actual layout is in the set
  F2, in2   the same with two named cards (the study's rule), when --named 2
  D         share of SAMPLES layouts, drawn by scorer weight, in which the card makes double dummy
  dd_true   does the card make double dummy on the actual layout
Double dummy here is the same solver with every unseen card named (one cell = one layout).
"""
import json, os, sys, time
import numpy as np
from belief import Belief
from celllib import Solver
from pipeline import Level, honour_runs, name, runs_of

def arg(flag, default, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default

src, out, cards = sys.argv[1], sys.argv[2], int(sys.argv[3])
N = arg('--samples', 64, int)
stride, offset = arg('--stride', 1, int), arg('--offset', 0, int)
named_n = arg('--named', 2, int)
limit = arg('--limit', 10 ** 9, int)
B = Belief(arg('--repo', '.'), arg('--scorer', ''))
P = [p for p in map(json.loads, open(src)) if p['cards'] == cards]
P = [p for i, p in enumerate(P) if i % stride == offset]
seen = {json.loads(l)['table'] for l in open(out)} if os.path.exists(out) else set()
f = open(out, 'a')
sv = Solver('./cells', ('--def', 'ends', '--maxnodes', '20000000'))
rng = np.random.default_rng(12345)
done = 0
for p in P:
    if done >= limit:
        break
    if p['table'] in seen:
        continue
    pos = dict(p)
    for k in ('hN', 'hS', 'pool', 'east'):
        pos[k] = int(p[k], 16)
    t0 = time.time()
    sv.reset()
    L0 = Level(sv, pos, 0)
    o = L0.outright()
    rec = dict(table=p['table'], board=p['board'], cards=cards, game=p['game'], made=p['made'], need=p['need'], contract=p['contract'], bot=p['bot'],
               declarer_tricks=p['declarer_tricks'], level=p['level'])
    if o is None:
        continue
    if any(o.values()):
        rec['claim'] = True
        f.write(json.dumps(rec) + '\n'); f.flush(); done += 1
        continue
    reps = L0.reps
    played = [r[0] for r in L0.runs if pos['played'] in r][0]
    B.prepare(p, pos)
    L0.add_weights('b', B.cell_weights(0))
    L0.singles()
    fl0 = L0.floors('b', must=reps)
    t_true = L0.cell_index(pos['east'])
    F0 = {c: (fl0[c]['floor'] if c in fl0 else 0.) for c in reps}
    in0 = {c: (c in fl0 and t_true in fl0[c]['set']) for c in reps}
    F2 = in2 = named = None
    if named_n >= 2:
        cand = honour_runs(pos)[:3]
        if len(cand) >= 2:
            L1 = []
            for r in cand:
                lv = Level(sv, pos, 1 << r['card'], parent=L0)
                lv.add_weights('b', B.cell_weights(lv.named))
                lv.singles()
                fl = lv.floors('b', must=reps)
                L1.append((max((v['floor'] for v in fl.values()), default=0.), lv))
            order = sorted(range(len(L1)), key=lambda i: -L1[i][0])
            L2 = Level(sv, pos, (1 << cand[order[0]]['card']) | (1 << cand[order[1]]['card']), parent=L1[order[0]][1])
            L2.add_weights('b', B.cell_weights(L2.named))
            L2.singles()
            fl2 = L2.floors('b', must=reps)
            t2 = L2.cell_index(pos['east'])
            F2 = {c: (fl2[c]['floor'] if c in fl2 else 0.) for c in reps}
            in2 = {c: (c in fl2 and t2 in fl2[c]['set']) for c in reps}
            named = [name(cand[order[0]]['card']), name(cand[order[1]]['card'])]
    t1 = time.time()
    # double dummy: every unseen card named, one cell per layout
    cum = np.cumsum(B.w)
    picks = np.minimum(np.searchsorted(cum / cum[-1], (rng.random() + np.arange(N)) / N, side='right'), len(cum) - 1)
    cards_arr = np.array(B.cards)
    masks = [sum(1 << int(c) for c in cards_arr[B.east[i]]) for i in picks] + [pos['east']]
    sv.position(pos['trump'], pos['leader'], pos['hN'], pos['hS'], pos['pool'], pos['pool'], pos['trick'])
    sv.cells([((0, 0, 0, 0), m) for m in masks])
    dd = []
    ok = True
    for i in range(len(masks)):
        r = sv.query(pos['need'], [i])
        if 'capped' in r:
            ok = False
            break
        dd.append(r['cards'])
    if not ok:
        continue
    D = {c: sum(d[c] for d in dd[:N]) / N for c in reps}
    rec.update(claim=False, played=name(played), cards_list=[name(c) for c in reps],
               F0=[round(F0[c], 6) for c in reps], in0=[bool(in0[c]) for c in reps],
               F2=None if F2 is None else [round(F2[c], 6) for c in reps], in2=None if in2 is None else [bool(in2[c]) for c in reps], named=named,
               D=[round(D[c], 6) for c in reps], dd_true=[int(dd[N][c]) for c in reps],
               prove_seconds=t1 - t0, dd_seconds=time.time() - t1)
    f.write(json.dumps(rec) + '\n'); f.flush(); done += 1
sv.close()
