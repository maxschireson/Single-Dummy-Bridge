"""Size of a table of k-card endings for the pooled (single-dummy sure-trick) game.

A position: each remaining card is North's, South's or unseen (X); only relative rank within a suit
matters, so a suit is a string over {N,S,X} of length <= 13. k cards each in N and S, 2k unseen.
Counted up to permutation of the suits (all four at notrump, the three side suits with a trump suit),
exactly, by Burnside. Leader: the declaring side (canonically North) or a defender (canonically East);
the 180-degree turn of the table maps South/West on lead onto those.
Show-out variants: every suit with unseen cards is free, or known to lie wholly with East, or wholly
with West, subject to the two hand sizes.
"""
import sys
from math import factorial
from functools import lru_cache
from itertools import product


def f(t):
    n, s, x = t
    L = n + s + x
    return factorial(L) // (factorial(n) * factorial(s) * factorial(x)) if L <= 13 else 0


def size(k):
    tot = (k, k, 2 * k)
    triples = [t for t in product(range(k + 1), range(k + 1), range(2 * k + 1)) if sum(t) <= 13]
    sub = lambda a, b, m=1: tuple(x - m * y for x, y in zip(a, b))
    ok = lambda r: all(x >= 0 for x in r)

    @lru_cache(None)
    def ordered(m, r):          # ordered m-tuples of suit patterns with counts summing to r
        if m == 0:
            return int(r == (0, 0, 0))
        return sum(f(t) * ordered(m - 1, sub(r, t)) for t in triples if ok(sub(r, t)))

    A = ordered(4, tot)
    T = sum(f(t) * ordered(2, sub(tot, t, 2)) for t in triples if ok(sub(tot, t, 2)))          # two equal suits
    D = sum(f(t) * f(u) for t in triples for u in triples if tuple(2 * a + 2 * b for a, b in zip(t, u)) == tot)
    C = sum(f(t) * f(sub(tot, t, 3)) for t in triples if ok(sub(tot, t, 3)) and sum(sub(tot, t, 3)) <= 13)
    Q = sum(f(t) for t in triples if tuple(4 * a for a in t) == tot)
    nt = (A + 6 * T + 3 * D + 8 * C + 6 * Q) // 24
    trump = 0
    for t0 in triples:
        r = sub(tot, t0)
        if not ok(r):
            continue
        a3 = ordered(3, r)
        t3 = sum(f(t) * f(sub(r, t, 2)) for t in triples if ok(sub(r, t, 2)) and sum(sub(r, t, 2)) <= 13)
        c3 = sum(f(t) for t in triples if tuple(3 * a for a in t) == r)
        trump += f(t0) * (a3 + 3 * t3 + 2 * c3) // 6

    @lru_cache(None)
    def voids(m, r, e, w):      # ordered tuples times feasible show-out states
        if m == 0:
            return int(r == (0, 0, 0))
        out = 0
        for t in triples:
            r2 = sub(r, t)
            if not ok(r2):
                continue
            x = t[2]
            ways = voids(m - 1, r2, e, w)
            if x:
                if e + x <= k:
                    ways += voids(m - 1, r2, e + x, w)
                if w + x <= k:
                    ways += voids(m - 1, r2, e, w + x)
            out += f(t) * ways
        return out

    mult = voids(4, tot, 0, 0) / A
    return dict(k=k, ordered=A, notrump=nt, trump=trump, both_strains_two_leaders=2 * (nt + trump), showout_multiplier=mult)


if __name__ == '__main__':
    for k in (int(a) for a in sys.argv[1:]):
        r = size(k)
        n = r['both_strains_two_leaders']
        bits = 2 if k <= 3 else 3
        print('%d-card: notrump %.3e, trump %.3e, both x 2 leader classes = %.3e positions; at %d bits %.2f GB; '
              'show-out variants x%.1f -> %.3e entries, %.1f GB' % (k, r['notrump'], r['trump'], n, bits, n * bits / 8 / 1e9,
              r['showout_multiplier'], n * r['showout_multiplier'], n * r['showout_multiplier'] * bits / 8 / 1e9))
        print('   ordered suits, no symmetry: %.3e per strain and leader' % r['ordered'])
