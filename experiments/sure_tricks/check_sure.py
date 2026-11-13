"""Cross-check the pooled solver against the layout-by-layout exact solver on random small endings."""
import random, itertools, sys, time
from sure import Sure
from exact import Exact
from fusionlab import DDS
rng = random.Random(7)
dds = DDS(cache_path='')
n_cards = int(sys.argv[1]) if len(sys.argv) > 1 else 3
trials = int(sys.argv[2]) if len(sys.argv) > 2 else 150
bad = 0
t0 = time.time()
for t in range(trials):
    # dense universe: the top cards of a few suits, so that runs of touching cards are common
    k = rng.choice([2, 3, 4])
    per = -(-4 * n_cards // k) + rng.choice([0, 1])
    universe = [13 * s + r for s in rng.sample(range(4), k) for r in range(13 - per, 13)]
    deck = rng.sample(universe, 4 * n_cards)
    N, S, pool = deck[:n_cards], deck[n_cards:2 * n_cards], deck[2 * n_cards:]
    trump = rng.choice([0, 1, 2, 3, 4])
    leader = rng.choice([0, 1, 2, 3])
    s = Sure({0: N, 2: S}, pool, {1: n_cards, 3: n_cards}, trump, leader)
    sure = max(k for k in range(n_cards + 1) if s.can(k))
    worlds = []
    for e in itertools.combinations(pool, n_cards):
        w = tuple(c for c in pool if c not in e)
        worlds.append([tuple(N), tuple(e), tuple(S), w])
    full = (1 << len(worlds)) - 1
    ex_val = 0
    for k in range(n_cards, 0, -1):
        ex = Exact(worlds, trump, leader, (), k, 0, dds=dds)
        if full in ex.front(0, (), leader, k, full):
            ex_val = k
            break
    if sure != ex_val:
        bad += 1
        print('MISMATCH', t, 'N', N, 'S', S, 'pool', pool, 'trump', trump, 'leader', leader, 'pooled', sure, 'exact', ex_val)
print('%d-card endings: %d trials, %d mismatches, %.0f s' % (n_cards, trials, bad, time.time() - t0))
