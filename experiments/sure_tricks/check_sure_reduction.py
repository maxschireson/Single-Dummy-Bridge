"""The defenders' touching-card reduction against the unreduced search, on random endings dense in runs."""
import random, sys, time
from sure import Sure
rng = random.Random(5)
n, trials = int(sys.argv[1]), int(sys.argv[2])
bad = 0
t0 = time.time()
for t in range(trials):
    k = rng.choice([2, 3])
    per = -(-4 * n // k) + rng.choice([0, 1, 2])
    universe = [13 * s + r for s in rng.sample(range(4), k) for r in range(13 - per, 13)]
    deck = rng.sample(universe, 4 * n)
    N, S, pool = deck[:n], deck[n:2 * n], deck[2 * n:]
    trump, leader = rng.choice([0, 1, 2, 3, 4]), rng.choice([0, 1, 2, 3])
    a = Sure({0: N, 2: S}, pool, {1: n, 3: n}, trump, leader)
    b = Sure({0: N, 2: S}, pool, {1: n, 3: n}, trump, leader); b.reduce = False
    va = max(x for x in range(n + 1) if a.can(x))
    vb = max(x for x in range(n + 1) if b.can(x))
    if va != vb:
        bad += 1
        print('MISMATCH', N, S, pool, trump, leader, va, vb)
print('%d-card endings: %d trials, %d mismatches between reduced and unreduced, %.0f s' % (n, trials, bad, time.time() - t0))
