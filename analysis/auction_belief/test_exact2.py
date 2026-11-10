import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Exactness test where later rounds are actually used (low completion acceptance)."""
import itertools, sys, time
import numpy as np
sys.path.insert(0, HERE)
from exact import exact_posterior

N = 12
cards = np.arange(N)
def chk_a(h): return (h.sum(1) % 3 == 0)
def chk_b(h): return ((h % 2 == 0).sum(1) == 2) & (h.max(1) >= 9) & (h.min(1) <= 1)
def chk_c(h): return (h.sum(1) % 4 == 1)
checks = [chk_a, chk_b, chk_c]
layouts = []
for A in itertools.combinations(range(N), 4):
    if not chk_a(np.array([A]))[0]: continue
    rest = [c for c in range(N) if c not in A]
    for B in itertools.combinations(rest, 4):
        C = tuple(c for c in rest if c not in B)
        if chk_b(np.array([B]))[0] and chk_c(np.array([C]))[0]:
            layouts.append((A, B))
index = {l: i for i, l in enumerate(layouts)}
per_a = {}
for A, B in layouts: per_a[A] = per_a.get(A, 0) + 1
nA = sum(1 for A in itertools.combinations(range(N), 4) if chk_a(np.array([A]))[0])
print('consistent layouts', len(layouts), 'of 34650 (%.3f%%); consistent A hands %d of 495, of which %d have a completion; completions per such A: min %d max %d; mean completion acceptance %.4f' % (
    100 * len(layouts) / 34650, nA, len(per_a), min(per_a.values()), max(per_a.values()), len(layouts) / (nA * 70)))

def trial(n_target, k_mult, pilot, batch, reps, seed):
    rng = np.random.default_rng(seed)
    counts = np.zeros(len(layouts)); later = 0; total = 0; rsum = 0; distinct = 0
    for _ in range(reps):
        s, st = exact_posterior(cards, checks, n_target, rng, sizes=(4, 4, 4), k_mult=k_mult, pilot=pilot, batch=batch)
        later += st['rounds'] > 0; rsum += st['rounds']; distinct += st['distinct_blocks']
        for row in s:
            counts[index[(tuple(sorted(row[0])), tuple(sorted(row[1])))]] += 1; total += 1
    expected = total / len(layouts)
    chi2 = ((counts - expected) ** 2 / expected).sum(); dof = len(layouts) - 1
    z = (chi2 - dof) / np.sqrt(2 * dof)
    a_counts = {}
    for (A, B), c in zip(layouts, counts): a_counts[A] = a_counts.get(A, 0) + c
    keys = sorted(per_a); obs = np.array([a_counts[k] for k in keys]); exp = np.array([per_a[k] for k in keys]) * total / len(layouts)
    chi2a = ((obs - exp) ** 2 / exp).sum(); za = (chi2a - (len(keys) - 1)) / np.sqrt(2 * (len(keys) - 1))
    # regression of observed/expected share on completions per A: slope 0 means correct weighting of block hands
    ratio = obs / exp; w = np.array([per_a[k] for k in keys], float)
    slope = np.polyfit(np.log(w), ratio, 1)[0]
    print(f'n={n_target} k_mult={k_mult}: samples {total}, runs using later rounds {later}/{reps} (mean rounds {rsum/reps:.2f}), mean distinct block hands {distinct/reps:.1f} of {n_target}; layout chi2 z={z:+.2f}; block-hand chi2 z={za:+.2f}; slope of obs/exp on log(completions) {slope:+.4f}')

t = time.time()
trial(16, 8, 8, 16, 8000, 1)
trial(32, 8, 8, 16, 4000, 2)
trial(16, 2, 8, 16, 8000, 3)
trial(16, 10**6, 8, 64, 8000, 4)
print('time %.0fs' % (time.time() - t))
