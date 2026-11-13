"""Which unseen card's place matters: every run of unseen touching cards named in turn, refining the shape level.

usage: allruns.py POSITIONS.jsonl OUT.jsonl CARDS COUNT --repo DIR --scorer FILE

Positions without an outright claim only. A run is a maximal set of unseen cards of a suit with no North-South card
between them; one card of the run is named (its cards are interchangeable). Classes: top (no North-South card of the
suit above it), middle (North-South cards on both sides), bottom (none below it), free (North-South hold none of the suit).
"""
import json, os, sys, time
from belief import Belief
from celllib import SUIT, Solver, cards_of
from pipeline import Level, honour_runs, name, runs_of

def arg(flag, default, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default

def all_runs(pos):
    ns = pos['hN'] | pos['hS']
    out = []
    for s in range(4):
        mine, theirs = cards_of(ns & SUIT[s]), cards_of(pos['pool'] & SUIT[s])
        if not theirs:
            continue
        runs = []
        for c in theirs:
            if runs and not any(runs[-1][-1] < x < c for x in mine):
                runs[-1].append(c)
            else:
                runs.append([c])
        for run in runs:
            below = sum(1 for x in mine if x < run[0])
            above = sum(1 for x in mine if x > run[-1])
            kind = 'free' if not mine else 'top' if not above else 'bottom' if not below else 'middle'
            out.append(dict(card=run[-1], length=len(run), kind=kind, trump=s == pos['trump']))
    return out

src, out, cards, count = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
B = Belief(arg('--repo', '.'), arg('--scorer', ''))
P = [p for p in map(json.loads, open(src)) if p['cards'] == cards]
seen = {json.loads(l)['table'] for l in open(out)} if os.path.exists(out) else set()
f = open(out, 'a')
sv = Solver('./cells', ('--def', 'ends', '--maxnodes', '20000000'))
done = len(seen)
for p in P:
    if done >= count:
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
    if o is None or any(o.values()):
        continue
    B.prepare(p, pos)
    L0.add_weights('b', B.cell_weights(0))
    L0.singles()
    played = [r[0] for r in runs_of(pos) if pos['played'] in r][0]
    fl0 = L0.floors('b', must=[played])
    base = max((v['floor'] for v in fl0.values()), default=0.)
    n0 = L0.stats['single_nodes'] + L0.jstats.get('b', dict(nodes=0))['nodes']
    static = {r['card'] for r in honour_runs(pos)[:3]}
    rec = dict(table=p['table'], cards=cards, game=p['game'], made=p['made'], base=base, base_nodes=n0, runs=[])
    true0 = L0.cell_index(pos['east'])
    b0 = max(fl0, key=lambda c: fl0[c]['floor']) if fl0 else None
    rec['true_in_base'] = b0 is not None and true0 in fl0[b0]['set']
    for r in all_runs(pos):
        lv = Level(sv, pos, 1 << r['card'], parent=L0)
        lv.add_weights('b', B.cell_weights(lv.named))
        lv.singles()
        fl = lv.floors('b', must=[played])
        best = max(fl, key=lambda c: fl[c]['floor']) if fl else None
        ti = lv.cell_index(pos['east'])
        rec['runs'].append(dict(card=name(r['card']), length=r['length'], kind=r['kind'], trump=r['trump'], static=r['card'] in static,
                                floor=fl[best]['floor'] if best is not None else 0., true_in=best is not None and ti in fl[best]['set'],
                                nodes=lv.stats['single_nodes'] + lv.jstats.get('b', dict(nodes=0))['nodes'], capped=lv.stats['capped']))
    rec['seconds'] = time.time() - t0
    f.write(json.dumps(rec) + '\n'); f.flush()
    done += 1
sv.close()
