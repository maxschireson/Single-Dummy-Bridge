import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Exactness test of the two-level sampler on a toy that can be enumerated."""
import itertools, sys, time
import numpy as np
sys.path.insert(0, HERE)
from exact import exact_posterior

cards = np.arange(9)
def chk_a(h): return (h.sum(1) % 2 == 0)
def chk_b(h): return (h.min(1) < 4) & (h.max(1) != 7)
def chk_c(h): return ((h == 8).any(1)) | (h.sum(1) % 3 == 0)
checks = [chk_a, chk_b, chk_c]
layouts = []
for A in itertools.combinations(range(9), 3):
    rest = [c for c in range(9) if c not in A]
    for B in itertools.combinations(rest, 3):
        C = tuple(c for c in rest if c not in B)
        if chk_a(np.array([A]))[0] and chk_b(np.array([B]))[0] and chk_c(np.array([C]))[0]:
            layouts.append((A, B))
index = {l: i for i, l in enumerate(layouts)}
per_a = {}
for A, B in layouts: per_a[A] = per_a.get(A, 0) + 1
print('consistent layouts', len(layouts), 'of 1680; consistent A hands', len(per_a), 'completions per A: min', min(per_a.values()), 'max', max(per_a.values()))

def trial(n_target, k_mult, pilot, batch, reps, seed):
    rng = np.random.default_rng(seed)
    counts = np.zeros(len(layouts)); rounds = 0; total = 0
    for _ in range(reps):
        s, st = exact_posterior(cards, checks, n_target, rng, sizes=(3, 3, 3), k_mult=k_mult, pilot=pilot, batch=batch)
        rounds += st['rounds'] > 0
        for row in s:
            counts[index[(tuple(sorted(row[0])), tuple(sorted(row[1])))]] += 1; total += 1
    expected = total / len(layouts)
    chi2 = ((counts - expected) ** 2 / expected).sum(); dof = len(layouts) - 1
    z = (chi2 - dof) / np.sqrt(2 * dof)
    # A-marginal check: share of samples per A hand versus completions per A
    a_counts = {}
    for (A, B), c in zip(layouts, counts): a_counts[A] = a_counts.get(A, 0) + c
    A_keys = sorted(per_a); obs = np.array([a_counts[k] for k in A_keys]); exp = np.array([per_a[k] for k in A_keys]) * total / len(layouts)
    chi2a = ((obs - exp) ** 2 / exp).sum(); za = (chi2a - (len(A_keys) - 1)) / np.sqrt(2 * (len(A_keys) - 1))
    tv = 0.5 * np.abs(counts / total - 1 / len(layouts)).sum()
    print(f'n={n_target} k_mult={k_mult} pilot={pilot} batch={batch} reps={reps}: samples {total}, runs using later rounds {rounds}/{reps}, layout chi2 z={z:+.2f}, block-hand chi2 z={za:+.2f}, TV {tv:.4f} (noise floor ~{0.5*np.sqrt(2/np.pi)*np.sqrt(len(layouts)/total):.4f})')

t = time.time()
trial(16, 8, 4, 4, 6000, 1)     # production-like ratio, later rounds forced by tiny pilot/batch
trial(8, 1, 2, 2, 12000, 2)     # harsh: tiny block pool, heavy reuse
trial(16, 10**6, 4, 16, 6000, 3) # plain rejection only (reference)
print('time %.0fs' % (time.time() - t))
