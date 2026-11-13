"""Defender-card reductions (--def ends, mid, two) against --def all on random endings: position values under random
knowledge (every shape; a random subset of cells with 0-2 named cards; one cell).
usage: stress_def.py K COUNT [--seed N]"""
import random
import sys
import time
from celllib import Solver, bits, cards_of, enumerate_cells
from check_cells import random_ending, shown_voids

k, count = int(sys.argv[1]), int(sys.argv[2])
seed = int(sys.argv[sys.argv.index('--seed') + 1]) if '--seed' in sys.argv else 1
rng = random.Random(seed)
modes = ['all', 'ends', 'mid', 'two']
sv = {m: Solver('./cells', ('--def', m)) for m in modes}
bad = {m: 0 for m in modes}
ex = {m: [] for m in modes}
n = 0
t0 = time.time()
for it in range(count):
    hands = random_ending(k, rng)
    hN, hE, hS, hW = hands
    pool = hE | hW
    trump, leader = rng.randrange(5), rng.randrange(4)
    vE, vW = shown_voids(hands, rng)
    named = bits(rng.sample(cards_of(pool), rng.choice((0, 0, 1, 2))))
    cells = enumerate_cells(pool, k, k, vE, vW, named)
    picks = ['*', [rng.randrange(len(cells))], [i for i in range(len(cells)) if rng.random() < .5] or [0]]
    for m in modes:
        sv[m].position(trump, leader, hN, hS, pool, named)
        sv[m].cells([(eu, pin) for eu, pin, _ in cells])
    for pick in picks:
        vals = {m: sv[m].value(pick)['value'] for m in modes}
        n += 1
        for m in modes[1:]:
            if vals[m] != vals['all']:
                bad[m] += 1
                if len(ex[m]) < 3:
                    ex[m].append((trump, leader, hex(hN), hex(hS), hex(pool), hex(named), vE, vW, pick if pick == '*' else len(pick), vals))
for s in sv.values():
    s.close()
print('%d-card endings, seed %d: %d values compared with --def all in %.0f s' % (k, seed, n, time.time() - t0))
for m in modes[1:]:
    print('  --def %-4s differs in %d' % (m, bad[m]), ex[m][:2] if bad[m] else '')
