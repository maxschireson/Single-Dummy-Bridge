"""Other targets than the contract, shape level: one trick fewer (down one) and one trick more (an overtrick).

usage: targets.py POSITIONS.jsonl OUT.jsonl CARDS --repo DIR --scorer FILE [--stride K --offset J] [--limit N]

For each position and each target (contract - 1, contract, contract + 1): whether some card guarantees it outright, and
the best card's certified probability by shape (scorer weights). Each target is searched on its own, so the three
answers may come from three different lines.
"""
import json, os, sys, time
from belief import Belief
from celllib import Solver
from pipeline import Level, name

def arg(flag, default, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default

src, out, cards = sys.argv[1], sys.argv[2], int(sys.argv[3])
stride, offset, limit = arg('--stride', 1, int), arg('--offset', 0, int), arg('--limit', 10 ** 9, int)
B = Belief(arg('--repo', '.'), arg('--scorer', ''))
P = [p for p in map(json.loads, open(src)) if p['cards'] == cards]
P = [p for i, p in enumerate(P) if i % stride == offset][:limit]
seen = {json.loads(l)['table'] for l in open(out)} if os.path.exists(out) else set()
f = open(out, 'a')
sv = Solver('./cells', ('--def', 'ends', '--maxnodes', '20000000'))
for p in P:
    if p['table'] in seen:
        continue
    base = dict(p)
    for k in ('hN', 'hS', 'pool', 'east'):
        base[k] = int(p[k], 16)
    B.prepare(p, base)
    cw = B.cell_weights(0)
    sv.reset()
    rec = dict(table=p['table'], board=p['board'], cards=cards, game=p['game'], made=p['made'], need=p['need'], declarer_tricks=p['declarer_tricks'],
               level=p['level'], targets={})
    for d in (-1, 0, 1):
        need = p['need'] + d
        if need <= 0:
            rec['targets'][str(d)] = dict(outright=True, floor=1., best=None, true_in=True, trivial=True)
            continue
        if need > cards:
            rec['targets'][str(d)] = dict(outright=False, floor=0., best=None, true_in=False, trivial=True)
            continue
        pos = dict(base, need=need)
        lv = Level(sv, pos, 0)
        o = lv.outright()
        if o is None:
            rec['targets'][str(d)] = None
            continue
        if any(o.values()):
            rec['targets'][str(d)] = dict(outright=True, floor=1., best=None, true_in=True, cards=[name(c) for c, v in o.items() if v])
            continue
        lv.add_weights('b', cw)
        lv.singles()
        fl = lv.floors('b')
        best = max(fl, key=lambda c: fl[c]['floor']) if fl else None
        ti = lv.cell_index(base['east'])
        rec['targets'][str(d)] = dict(outright=False, floor=fl[best]['floor'] if best is not None else 0., best=None if best is None else name(best),
                                      true_in=best is not None and ti in fl[best]['set'],
                                      nodes=lv.stats['single_nodes'] + lv.jstats.get('b', dict(nodes=0))['nodes'] + lv.jstats['outright']['nodes'])
    f.write(json.dumps(rec) + '\n'); f.flush()
sv.close()
