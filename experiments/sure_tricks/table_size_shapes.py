"""Table size when the key carries the defenders' shapes instead of (or as well as) show-outs.

Same position count as table_size.py (cards as N / S / unseen in relative rank order, up to suit permutation,
two leader classes, notrump + trump). Multipliers, counted on ordered suits:
  voids  : every suit with unseen cards is free, or wholly East's, or wholly West's (table_size.py's count)
  shapes : East's length in every suit is known exactly (so West's is too)
  mixed  : each suit is either unknown or known exactly; states whose unknown suits are forced are merged
           into the exact ones. Contains both of the above.
"""
import json, sys
from functools import lru_cache
from itertools import product
from table_size import f, size


def multipliers(k):
    tot = (k, k, 2 * k)
    triples = [t for t in product(range(k + 1), range(k + 1), range(2 * k + 1)) if sum(t) <= 13]
    sub = lambda a, b: tuple(x - y for x, y in zip(a, b))
    ok = lambda r: all(x >= 0 for x in r)

    @lru_cache(None)
    def plain(m, r):
        if m == 0:
            return int(r == (0, 0, 0))
        return sum(f(t) * plain(m - 1, sub(r, t)) for t in triples if ok(sub(r, t)))

    @lru_cache(None)
    def shapes(m, r, e):            # East's count so far
        if m == 0:
            return int(r == (0, 0, 0) and e == k)
        out = 0
        for t in triples:
            r2 = sub(r, t)
            if ok(r2):
                out += f(t) * sum(shapes(m - 1, r2, e + j) for j in range(t[2] + 1) if e + j <= k)
        return out

    @lru_cache(None)
    def mixed(m, r, e, u, nu):      # e = East's known cards, u = unseen cards in unknown suits, nu = unknown suits (capped at 2)
        if m == 0:
            if r != (0, 0, 0):
                return 0
            if nu == 0:
                return int(e == k)
            return int(nu >= 2 and 0 < k - e < u)
        out = 0
        for t in triples:
            r2 = sub(r, t)
            if not ok(r2):
                continue
            x = t[2]
            ways = sum(mixed(m - 1, r2, e + j, u, nu) for j in range(x + 1) if e + j <= k)
            if x:
                ways += mixed(m - 1, r2, e, u + x, min(2, nu + 1))
            out += f(t) * ways
        return out

    A = plain(4, tot)
    return shapes(4, tot, 0) / A, mixed(4, tot, 0, 0, 0) / A


def voids_canonical(k):
    """Show-out states with duplicates merged: a state whose free suits are forced equals a fully flagged one."""
    tot = (k, k, 2 * k)
    triples = [t for t in product(range(k + 1), range(k + 1), range(2 * k + 1)) if sum(t) <= 13]
    sub = lambda a, b: tuple(x - y for x, y in zip(a, b))
    ok = lambda r: all(x >= 0 for x in r)

    @lru_cache(None)
    def plain(m, r):
        if m == 0:
            return int(r == (0, 0, 0))
        return sum(f(t) * plain(m - 1, sub(r, t)) for t in triples if ok(sub(r, t)))

    @lru_cache(None)
    def v(m, r, e, w, u):       # e, w = cards known to be East's, West's; u = unseen cards in free suits
        if m == 0:
            if r != (0, 0, 0):
                return 0
            return int(e == k) if u == 0 else int(0 < k - e < u)
        out = 0
        for t in triples:
            r2 = sub(r, t)
            if not ok(r2):
                continue
            x = t[2]
            ways = v(m - 1, r2, e, w, u + x)
            if x:
                if e + x <= k:
                    ways += v(m - 1, r2, e + x, w, u)
                if w + x <= k:
                    ways += v(m - 1, r2, e, w + x, u)
            out += f(t) * ways
        return out

    return v(4, tot, 0, 0, 0) / plain(4, tot)


if __name__ == '__main__':
    for k in (int(a) for a in sys.argv[1:]):
        r = size(k)
        n = r['both_strains_two_leaders']
        bits = 2 if k <= 3 else 3
        ms, mm = multipliers(k)
        vc = voids_canonical(k)
        gb = lambda m: n * m * bits / 8 / 1e9
        print(json.dumps(dict(cards=k, positions=n, bits=bits,
                              voids_raw=dict(mult=r['showout_multiplier'], entries=n * r['showout_multiplier'], gb=gb(r['showout_multiplier'])),
                              voids=dict(mult=vc, entries=n * vc, gb=gb(vc)),
                              shapes=dict(mult=ms, entries=n * ms, gb=gb(ms)),
                              mixed=dict(mult=mm, entries=n * mm, gb=gb(mm)))))
