"""Run-dense random endings (as check_cpp.py draws them: the top ranks of two to four suits, random show-outs), as
sure_cpp input lines, optionally with 0 to 3 cards already played to the trick (random legal cards).
usage: gen_dense.py SURE_DIR N COUNT SEED [--trick]"""
import random
import sys

sys.path.insert(0, sys.argv[1])
from sure import Sure  # noqa: E402

n, count, seed = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
with_trick = '--trick' in sys.argv
rng = random.Random(seed)
out = []
while len(out) < count:
    k = rng.choice([x for x in (2, 3, 4) if 13 * x >= 4 * n])
    per = min(13, -(-4 * n // k) + rng.choice([0, 1, 2]))
    universe = [13 * s + r for s in rng.sample(range(4), k) for r in range(13 - per, 13)]
    deck = rng.sample(universe, 4 * n)
    N, S, E, W = deck[:n], deck[n:2 * n], deck[2 * n:3 * n], deck[3 * n:]
    trump, leader = rng.choice([0, 1, 2, 3, 4]), rng.choice([0, 1, 2, 3])
    voids = {1: set(), 3: set()}
    for d, h in ((1, E), (3, W)):
        for s in range(4):
            if not any(c // 13 == s for c in h) and rng.random() < 0.5:
                voids[d].add(s)
    hands = {0: list(N), 1: list(E), 2: list(S), 3: list(W)}
    trick = []
    if with_trick:
        for j in range(rng.randrange(4)):
            seat = (leader + j) % 4
            h = hands[seat]
            legal = [c for c in h if trick and c // 13 == trick[0] // 13] or h
            c = rng.choice(legal)
            if trick and c // 13 != trick[0] // 13 and seat % 2:
                voids[seat].add(trick[0] // 13)
            h.remove(c)
            trick.append(c)
    s = Sure({0: hands[0], 2: hands[2]}, hands[1] + hands[3], {1: len(hands[1]), 3: len(hands[3])}, trump, leader,
             voids=voids)
    if not s.feasible(s.pool0, s.cnt0, s.void0, s.known0):
        continue
    m = {x: sum(1 << c for c in hands[x]) for x in range(4)}
    vE = sum(1 << x for x in voids[1])
    vW = sum(1 << x for x in voids[3])
    line = '%d %d %x %x %x %d %d %d %d' % (trump, leader, m[0], m[2], m[1] | m[3], len(hands[1]), len(hands[3]), vE, vW)
    if trick:
        line += ' ' + ' '.join(str(c) for c in trick)
    out.append(line)
print('\n'.join(out))
