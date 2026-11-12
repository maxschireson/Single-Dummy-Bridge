"""C++ solver against the Python reference on random endings dense in touching cards, with random show-outs."""
import random, sys, time
from sure import Sure
from csure import line, solve

def gen(rng, n):
    k = rng.choice([2, 3, 4])
    per = min(13, -(-4 * n // k) + rng.choice([0, 1, 2]))
    universe = [13 * s + r for s in rng.sample(range(4), k) for r in range(13 - per, 13)]
    deck = rng.sample(universe, 4 * n)
    N, S, pool = deck[:n], deck[n:2 * n], deck[2 * n:]
    trump, leader = rng.choice([0, 1, 2, 3, 4]), rng.choice([0, 1, 2, 3])
    voids = {}
    if rng.random() < 0.4:
        d = rng.choice([1, 3]); voids[d] = {rng.randrange(4)}
        if rng.random() < 0.3:
            voids.setdefault(rng.choice([1, 3]), set()).add(rng.randrange(4))
    s = Sure({0: N, 2: S}, pool, {1: n, 3: n}, trump, leader, voids=voids)
    if not s.feasible(s.pool0, s.cnt0, s.void0, s.known0):
        return None
    return s

n, trials = int(sys.argv[1]), int(sys.argv[2])
args = sys.argv[3:]
rng = random.Random(3)
items = []
while len(items) < trials:
    s = gen(rng, n)
    if s is not None:
        items.append(s)
t0 = time.time()
res = solve([line(s) for s in items], *args)
tc = time.time() - t0
bad = 0
t0 = time.time()
for s, r in zip(items, res):
    ref = max(x for x in range(n + 1) if s.can(x))
    vals = list(r['cards'].values())
    got = (max(vals) if s.leader0 % 2 == 0 else min(vals)) if vals else 0
    if got != ref:
        bad += 1
        if bad <= 3:
            print('MISMATCH', line(s), 'python', ref, 'cpp', got, r['cards'])
print('%d-card endings, %d trials, args %s: %d mismatches (C++ %.2f s, Python %.0f s)' % (n, trials, args, bad, tc, time.time() - t0))
