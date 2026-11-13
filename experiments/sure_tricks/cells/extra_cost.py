"""Cost details at the shape level on recorded positions, with the instrumented solver (cells_i).

usage: extra_cost.py POSITIONS.jsonl OUT.jsonl CARDS COUNT --repo DIR --scorer FILE

Per position: the outright question; one search per shape in falling order of scorer weight (nodes per shape, so that
the cost of stopping at 95% or 99% of the weight is measured, not scaled); the same searches asking about one card
only (the card the bot played), from an empty table; the joint step for the best card. `low` counts nodes with four
cards or fewer left, and `b4` the trick-boundary positions searched with exactly four cards left: with a resident
4-card table the first are not searched and the second become lookups.
"""
import json, os, sys, time
from belief import Belief
from celllib import Solver, enumerate_cells
from pipeline import name, runs_of

def arg(flag, default, cast=str):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default

src, out, cards, count = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
B = Belief(arg('--repo', '.'), arg('--scorer', ''))
P = [p for p in map(json.loads, open(src)) if p['cards'] == cards]
P = P[::max(1, len(P) // count)][:count]
seen = {json.loads(l)['table'] for l in open(out)} if os.path.exists(out) else set()
f = open(out, 'a')
for p in P:
    if p['table'] in seen:
        continue
    pos = dict(p)
    for k in ('hN', 'hS', 'pool', 'east'):
        pos[k] = int(p[k], 16)
    t0 = time.time()
    B.prepare(p, pos)
    cw = B.cell_weights(0)
    cells = enumerate_cells(pos['pool'], pos['cE'], pos['cW'], pos['vE'], pos['vW'], 0)
    cells.sort(key=lambda t: -cw[(t[0], t[1])])
    w = [cw[(eu, pin)] for eu, pin, _ in cells]
    reps = [r[0] for r in runs_of(pos)]
    played = [r[0] for r in runs_of(pos) if pos['played'] in r][0]
    sv = Solver('./cells', ('--def', 'ends', '--maxnodes', '30000000'))
    sv.position(pos['trump'], pos['leader'], pos['hN'], pos['hS'], pos['pool'], 0, pos['trick'])
    sv.cells([(eu, pin) for eu, pin, _ in cells])
    o = sv.query(pos['need'])
    rec = dict(table=p['table'], cards=cards, game=p['game'], shapes=len(cells), runs=len(reps), layouts=len(B.east), effective=B.effective)
    if 'capped' in o:
        rec['capped'] = True
        f.write(json.dumps(rec) + '\n'); f.flush(); sv.close()
        continue
    rec['outright'] = dict(nodes=o['nodes'], low=o['low_nodes'], b4=o['boundary4'], sec=o['sec'], claim=any(o['cards'].values()))
    singles, wins, capped = [], [], False
    for i in range(len(cells)):
        r = sv.query(pos['need'], [i])
        if 'capped' in r:
            capped = True
            break
        singles.append((r['nodes'], r['low_nodes'], r['boundary4'], r['sec']))
        wins.append(r['cards'])
    if capped:
        rec['capped'] = True
        f.write(json.dumps(rec) + '\n'); f.flush(); sv.close()
        continue
    rec['weights'] = [round(x, 6) for x in w]
    rec['single_nodes'] = [s[0] for s in singles]
    rec['single_low'] = [s[1] for s in singles]
    rec['single_b4'] = [s[2] for s in singles]
    rec['single_sec'] = sum(s[3] for s in singles)
    # joint for the best card by ceiling order, as pipeline.Level.floors does
    ceil = {c: sum(w[i] for i in range(len(cells)) if wins[i][c]) for c in reps}
    best, jn, jl, jb, jq = 0., 0, 0, 0, 0
    floors = {}
    for c in sorted(reps, key=lambda c: -ceil[c]):
        if ceil[c] <= 0 or ceil[c] <= best + 1e-12:
            continue
        R = [i for i in range(len(cells)) if wins[i][c] and w[i] > 0]
        if len(R) <= 1:
            floors[c] = ceil[c]
            best = max(best, ceil[c])
            continue
        r = sv.query(pos['need'], R, [c]); jq += 1
        jn += r['nodes']; jl += r.get('low_nodes', 0); jb += r.get('boundary4', 0)
        if 'capped' not in r and r['cards'][c]:
            floors[c] = ceil[c]
        else:
            S = [R[0]]
            for i in R[1:]:
                r = sv.query(pos['need'], S + [i], [c]); jq += 1
                jn += r['nodes']; jl += r.get('low_nodes', 0); jb += r.get('boundary4', 0)
                if 'capped' not in r and r['cards'][c]:
                    S.append(i)
            floors[c] = sum(w[i] for i in S)
        best = max(best, floors[c])
    rec['joint'] = dict(nodes=jn, low=jl, b4=jb, questions=jq)
    rec['floor'], rec['ceiling'] = best, max(ceil.values())
    sv.close()
    # the same per-shape searches for one card only, from an empty table
    sv = Solver('./cells', ('--def', 'ends', '--maxnodes', '30000000'))
    sv.position(pos['trump'], pos['leader'], pos['hN'], pos['hS'], pos['pool'], 0, pos['trick'])
    sv.cells([(eu, pin) for eu, pin, _ in cells])
    one = []
    for i in range(len(cells)):
        r = sv.query(pos['need'], [i], [played])
        one.append(r['nodes'])
    sv.close()
    rec['one_card_nodes'] = one
    rec['seconds'] = time.time() - t0
    f.write(json.dumps(rec) + '\n'); f.flush()
