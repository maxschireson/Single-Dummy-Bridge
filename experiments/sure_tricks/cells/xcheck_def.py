"""--def ends against --def all on recorded positions: the outright question, a search for each of the heaviest shapes
(uniform weights), and one joint question on the shapes the first card wins alone.
usage: xcheck_def.py POSITIONS.jsonl CARDS COUNT [SHAPES]"""
import json, sys, time
from celllib import Solver, enumerate_cells
from pipeline import runs_of

src, cards, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
top = int(sys.argv[4]) if len(sys.argv) > 4 else 12
P = [p for p in map(json.loads, open(src)) if p['cards'] == cards]
P = P[::max(1, len(P) // count)][:count]
sv = {m: Solver('./cells', ('--def', m, '--maxnodes', '50000000')) for m in ('all', 'ends', 'mid')}
n = dict(outright=0, single=0, joint=0)
bad = {m: dict(outright=0, single=0, joint=0) for m in ('ends', 'mid')}
t0 = time.time()
for p in P:
    pos = dict(p)
    for k in ('hN', 'hS', 'pool'):
        pos[k] = int(p[k], 16)
    cells = sorted(enumerate_cells(pos['pool'], pos['cE'], pos['cW'], pos['vE'], pos['vW'], 0), key=lambda t: -t[2])
    reps = [r[0] for r in runs_of(pos)]
    ans = {}
    for m, s in sv.items():
        s.reset()
        s.position(pos['trump'], pos['leader'], pos['hN'], pos['hS'], pos['pool'], 0, pos['trick'])
        s.cells([(eu, pin) for eu, pin, _ in cells])
        out = s.query(pos['need'])
        singles = [s.query(pos['need'], [i]) for i in range(min(top, len(cells)))]
        if 'capped' in out or any('capped' in x for x in singles):
            ans[m] = None
            continue
        c = reps[0]
        R = [i for i, x in enumerate(singles) if x['cards'][c]]
        joint = s.query(pos['need'], R, [c])['cards'][c] if len(R) > 1 else None
        ans[m] = (tuple(out['cards'][c] for c in reps), tuple(tuple(x['cards'][c] for c in reps) for x in singles), joint)
    if ans['all'] is None:
        continue
    n['outright'] += len(reps); n['single'] += len(reps) * len(ans['all'][1]); n['joint'] += ans['all'][2] is not None
    for m in ('ends', 'mid'):
        if ans[m] is None:
            continue
        bad[m]['outright'] += sum(a != b for a, b in zip(ans[m][0], ans['all'][0]))
        bad[m]['single'] += sum(a != b for x, y in zip(ans[m][1], ans['all'][1]) for a, b in zip(x, y))
        bad[m]['joint'] += ans[m][2] != ans['all'][2]
for s in sv.values():
    s.close()
print('%d-card recorded positions: %d; answers compared with --def all: outright %d, per shape %d, joint %d; %.0f s' % (cards, len(P), n['outright'], n['single'], n['joint'], time.time() - t0))
for m in ('ends', 'mid'):
    print('  --def %-4s differs: outright %d, per shape %d, joint %d' % (m, bad[m]['outright'], bad[m]['single'], bad[m]['joint']))
