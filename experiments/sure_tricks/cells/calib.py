"""cells.cpp with every-shape knowledge against sure_cpp (no table) on the bench positions: answers, nodes, time."""
import json, subprocess, sys, time
from celllib import Solver, enumerate_cells

# usage: calib.py BENCH_LINES.json SURE_BIN [MAX_CARDS]
D = json.load(open(sys.argv[1]))
SURE = sys.argv[2]
maxk = int(sys.argv[3]) if len(sys.argv) > 3 else 9
keys = [k for k in D if int(k.split('_')[1]) <= maxk and (int(D[k]['line'].split()[1]) + len(D[k]['line'].split()[9:])) % 2 == 0]
def sure(flags):
    inp = ''.join('N%d %s\n' % (D[k]['need'], D[k]['line']) for k in keys)
    out = {}
    for k in keys:      # one process per position: fresh tables, like the cells runs below
        r = subprocess.run([SURE, *flags], input='N%d %s\n' % (D[k]['need'], D[k]['line']), capture_output=True, text=True).stdout
        out[k] = json.loads(r.splitlines()[0])
    return out
S = sure([])
S2 = sure(['--nobounds'])
print('%-7s %-28s | %-22s | %s' % ('pos', 'sure_cpp ms / nodes', 'sure_cpp --nobounds', 'cells: all / ends / mid / two  (ms, nodes, same answers as sure_cpp)'))
for k in keys:
    t = D[k]['line'].split()
    trump, leader = int(t[0]), int(t[1])
    hN, hS, pool = int(t[2], 16), int(t[3], 16), int(t[4], 16)
    cE, cW, vE, vW = int(t[5]), int(t[6]), int(t[7]), int(t[8])
    trick = [int(x) for x in t[9:]]
    cells = enumerate_cells(pool, cE, cW, vE, vW, 0)
    ref = {int(c): v for c, v in S[k]['cards'].items()}
    row = []
    for mode in ('all', 'ends', 'mid', 'two'):
        sv = Solver('./cells', ('--def', mode))
        sv.position(trump, leader, hN, hS, pool, 0, trick)
        sv.cells([(eu, pin) for eu, pin, _ in cells])
        r = sv.query(D[k]['need'])
        sv.close()
        got = r['cards']
        same = all(got[c] == ref[c] for c in ref)      # sure_cpp answers one card per run
        row.append('%.1f %d %s' % (1000 * r['sec'], r['nodes'], 'same' if same else 'DIFF'))
    print('%-7s %7.1f %9d %2d shapes | %7.1f %9d | %s' % (k, 1000 * S[k]['seconds'], S[k]['nodes_above'], len(cells), 1000 * S2[k]['seconds'], S2[k]['nodes_above'], ' / '.join(row)))
