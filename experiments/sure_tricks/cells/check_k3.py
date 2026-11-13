"""The 114 three-card positions where the two-ends defender rule is wrong (table build, k3 counterexamples):
each --def mode of cells.cpp against the listed plain value."""
import sys
from itertools import product
from celllib import SUIT, Solver, popcount

rows = []
for l in open(sys.argv[1]):
    if l.startswith('#') or not l.strip():
        continue
    left, vals = l.split(' : ')
    t = left.split()
    trump, leader = int(t[1]), int(t[2])
    hN, hS, pool = int(t[3], 16), int(t[4], 16), int(t[5], 16)
    cE, cW = int(t[6]), int(t[7])
    el = [None if e == '-' else int(e) for e in t[8:12]]
    spec, plain = (int(x) for x in vals.replace('vs', ' ').split())
    rows.append((trump, leader, hN, hS, pool, cE, cW, el, spec, plain))
print(len(rows), 'positions')
for mode in ('all', 'ends', 'mid', 'two'):
    sv = Solver('./cells', ('--def', mode))
    right = spec_like = 0
    for trump, leader, hN, hS, pool, cE, cW, el, spec, plain in rows:
        x = [popcount(pool & SUIT[s]) for s in range(4)]
        cells = [(eu, 0) for eu in product(*[range(x[s] + 1) if el[s] is None else [el[s]] for s in range(4)]) if sum(eu) == cE]
        sv.position(trump, leader, hN, hS, pool, 0)
        sv.cells(cells)
        v = sv.value()['value']
        right += v == plain
        spec_like += v == spec
    sv.close()
    print('--def %-4s equals the plain value in %d, the two-ends value in %d' % (mode, right, spec_like))
