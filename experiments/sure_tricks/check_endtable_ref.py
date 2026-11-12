"""Checks on endtable_ref.py.
 1. Entry counts for k = 1, 2 against a brute-force count of distinct canonical forms (strings and sorted tuples,
    no class table, no ranks).
 2. unrank -> rank returns the slot: every slot for k = 1, 2; random slots for larger k.
 3. Positions that must share an entry do: random suit permutation, half-turn, re-spread ranks, knowledge
    with forced lengths removed.
usage: check_endtable_ref.py k [samples]"""
import itertools, random, sys, time
from endtable_ref import Index
from pooled_ref import normalize, SUIT, cards_of

def brute_count(k):
    labels = 'N' * k + 'S' * k + 'X' * 2 * k
    strings = sorted(set(itertools.permutations(labels)))
    forms = {'N': set(), 'T': set()}
    n = 4 * k
    for cut in itertools.combinations(range(n + 3), 3):
        parts = [cut[0], cut[1] - cut[0] - 1, cut[2] - cut[1] - 1, n + 2 - cut[2]]
        if max(parts) > 13:
            continue
        for st in strings:
            suits, i = [], 0
            for L in parts:
                suits.append(''.join(st[i:i + L])); i += L
            pool = 0
            for s, seg in enumerate(suits):
                for r, a in enumerate(seg):
                    if a == 'X':
                        pool |= 1 << (13 * s + r)
            xs = [seg.count('X') for seg in suits]
            seen = set()
            for raw in itertools.product(*[[None] + list(range(x + 1)) for x in xs]):
                el = normalize(pool, k, k, raw)
                if el is None or el in seen:
                    continue
                seen.add(el)
                rec = [(seg, -1 if e is None else e) for seg, e in zip(suits, el)]
                forms['N'].add(tuple(sorted(rec)))
                for t in range(4):
                    if suits[t]:
                        forms['T'].add((rec[t],) + tuple(sorted(rec[:t] + rec[t + 1:])))
    return len(forms['N']), len(forms['T'])

def transform(rng, pos):
    hN, hS, pool, el, trump, leader = pos
    el = list(el)
    # forced lengths removed: with every length exact, any one suit can be left unknown
    if all(e is not None for e in el) and rng.random() < 0.5:
        cand = [s for s in range(4) if pool & SUIT[s]]
        if cand:
            el[rng.choice(cand)] = None
    # half-turn
    if rng.random() < 0.5:
        hN, hS = hS, hN
        el = [None if e is None else bin(pool & SUIT[s]).count('1') - e for s, e in enumerate(el)]
        leader += 2
    # suit permutation (the trump suit keeps its role) and new ranks
    perm = list(range(4)); rng.shuffle(perm)
    def move(mask):
        out = 0
        for s in range(4):
            live = cards_of((hN | hS | pool) & SUIT[s])
            new = sorted(rng2.sample(range(13), len(live)))
            for c, r in zip(live, new):
                if mask >> c & 1:
                    out |= 1 << (13 * perm[s] + r)
        return out
    seed = rng.random()
    outs = []
    for m in (hN, hS, pool):
        rng2 = random.Random(seed)          # same new ranks for the three masks
        outs.append(move(m))
    el2 = [None] * 4
    for s in range(4):
        el2[perm[s]] = el[s]
    return outs[0], outs[1], outs[2], tuple(el2), (perm[trump] if trump < 4 else 4), leader

k = int(sys.argv[1]); samples = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
t0 = time.time()
ix = Index(k)
rng = random.Random(9)
if k <= 2:
    bn, bt = brute_count(k)
    print('k=%d counts: class table notrump %d trump %d, brute force notrump %d trump %d: %s' % (k, ix.M['N'], ix.M['T'], bn, bt, 'agree' if (bn, bt) == (ix.M['N'], ix.M['T']) else 'DIFFER'))
    slots = range(ix.entries)
else:
    slots = [rng.randrange(ix.entries) for _ in range(samples)]
bad = badt = 0
for i, slot in enumerate(slots):
    pos = ix.unrank(slot)
    if ix.rank(*pos) != slot:
        bad += 1
    if i % 3 == 0 or k > 2:
        if ix.rank(*transform(rng, pos)) != slot:
            badt += 1
print('k=%d: %d slots, unrank->rank failures %d, transformed-position failures %d (%.0f s)' % (k, len(slots), bad, badt, time.time() - t0))
