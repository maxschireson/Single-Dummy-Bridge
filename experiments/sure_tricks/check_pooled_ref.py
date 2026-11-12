"""Checks on pooled_ref.py (the game with shape knowledge).
 A. Show-out states only: against sure.py, the validated reference without shape knowledge.
 B. Shape knowledge: against exact.py run over every split consistent with the knowledge (needs the repo's DDS).
usage: check_pooled_ref.py A|B cards trials"""
import itertools, random, sys, time
from pooled_ref import Pooled, bits, normalize, SUIT

def ending(rng, n):
    k = rng.choice([2, 3, 4])
    per = min(13, -(-4 * n // k) + rng.choice([0, 1, 2]))
    universe = [13 * s + r for s in rng.sample(range(4), k) for r in range(13 - per, 13)]
    deck = rng.sample(universe, 4 * n)
    return deck[:n], deck[n:2 * n], deck[2 * n:], rng.choice([0, 1, 2, 3, 4]), rng.choice([0, 1, 2, 3])

mode, n, trials = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rng = random.Random(5)
bad = done = 0
t0 = time.time()
if mode == 'A':
    from sure import Sure
    while done < trials:
        N, S, pool, trump, leader = ending(rng, n)
        voids = {}
        if rng.random() < 0.6:
            voids[rng.choice([1, 3])] = {rng.randrange(4)}
            if rng.random() < 0.4:
                voids.setdefault(rng.choice([1, 3]), set()).add(rng.randrange(4))
        s = Sure({0: N, 2: S}, pool, {1: n, 3: n}, trump, leader, voids=voids)
        if not s.feasible(s.pool0, s.cnt0, s.void0, s.known0):
            continue
        x = [sum(1 for c in pool if c // 13 == t) for t in range(4)]
        el = [None] * 4
        for t in voids.get(1, ()):
            el[t] = 0
        for t in voids.get(3, ()):
            el[t] = x[t]
        ref = max(v for v in range(n + 1) if s.can(v))
        got = Pooled(trump).value(bits(N), bits(S), bits(pool), n, n, tuple(el), leader)
        done += 1
        if got != ref:
            bad += 1
            print('MISMATCH', N, S, pool, trump, leader, voids, 'sure.py', ref, 'pooled_ref', got)
    print('A: %d-card endings with show-outs, %d trials: %d mismatches against sure.py (%.0f s)' % (n, trials, bad, time.time() - t0))
else:
    from exact import Exact
    from fusionlab import DDS
    dds = DDS(cache_path='')
    kinds = [0, 0, 0]
    while done < trials:
        N, S, pool, trump, leader = ending(rng, n)
        east = rng.sample(pool, n)
        el = [sum(1 for c in east if c // 13 == t) if rng.random() < 0.6 else None for t in range(4)]
        norm = normalize(bits(pool), n, n, tuple(el))
        worlds = []
        for e in itertools.combinations(pool, n):
            if all(norm[t] is None or sum(1 for c in e if c // 13 == t) == norm[t] for t in range(4)):
                worlds.append([tuple(N), tuple(e), tuple(S), tuple(c for c in pool if c not in e)])
        full = (1 << len(worlds)) - 1
        ref = 0
        for v in range(n, 0, -1):
            ex = Exact(worlds, trump, leader, (), v, 0, dds=dds)
            if full in ex.front(0, (), leader, v, full):
                ref = v
                break
        got = Pooled(trump).value(bits(N), bits(S), bits(pool), n, n, tuple(el), leader)
        done += 1
        nk = sum(1 for t in range(4) if norm[t] is not None and bits(pool) & SUIT[t])
        kinds[0 if nk == 0 else 2 if all(norm[t] is not None for t in range(4)) else 1] += 1
        if got != ref:
            bad += 1
            print('MISMATCH', N, S, pool, trump, leader, el, 'exact', ref, 'pooled_ref', got, 'worlds', len(worlds))
    print('B: %d-card endings with shape knowledge, %d trials (%d nothing known, %d partly, %d whole shape): %d mismatches against exact.py (%.0f s)'
          % (n, trials, kinds[0], kinds[1], kinds[2], bad, time.time() - t0))
