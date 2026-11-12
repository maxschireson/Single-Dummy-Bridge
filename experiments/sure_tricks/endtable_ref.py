"""Reference index for the ending table: canonical form, class table, rank, unrank, exact sizes.

An entry is a trick-boundary position of the pooled game (pooled_ref.py) with k cards in each hand:
    who holds each remaining card (North, South or unseen), by relative rank within each suit,
    what is known about East's length in each suit (unknown, or exact),
    the strain (notrump, or a trump suit that still has cards), and the leader.
Positions that play identically share one entry:
    - only the order of the remaining cards within a suit matters, not their actual ranks;
    - the half-turn of the table (swap North/South and East/West) maps South or West on lead to North or East;
    - suits may be permuted (all four at notrump, the three side suits with a trump suit);
    - a trump suit with no cards left is notrump;
    - knowledge is normalized (pooled_ref.normalize), so states that imply one another are one state.

Slot layout:  slot = base[strain] + 2 * (class_offset + rank_in_class) + leader_bit
    base[notrump] = 0, base[trump] = 2 * M_notrump, leader_bit 0 = North, 1 = East.

Suit type: (n, s, x, kn) = North's, South's and unseen cards in the suit and the knowledge code
    (-1 unknown, else East's exact length). Types are ordered as tuples; type id = position in that order.
Pattern rank of a suit, cards numbered 0 (lowest) to L-1:
    rankN = colex rank of North's positions among the L,  rankS = colex rank of South's positions among the
    L - n positions North does not hold (renumbered 0..L-n-1),  rank = rankN * C(L-n, s) + rankS.
Class: the type ids of the four suits in canonical order (trump suit first if any, the others ascending).
    Suits of equal type are ordered by pattern rank. Classes are listed in lexicographic order of their id tuple.
Rank in class: digits, most significant first: the trump suit's pattern rank (radix its pattern count P), then
    for each run of m suits of equal type (pattern count P), in order, the multiset rank of their sorted
    pattern ranks r1 <= ... <= rm,  sum over i of C(r_i + i - 1, i),  radix C(P + m - 1, m).
"""
import sys
from math import comb
from itertools import product, groupby
from pooled_ref import normalize, bits, cards_of, SUIT

UNKNOWN = -1


class Index:
    def __init__(self, k):
        self.k = k
        self.triples = sorted(t for t in product(range(k + 1), range(k + 1), range(2 * k + 1)) if sum(t) <= 13)
        self.types = sorted((n, s, x, kn) for n, s, x in self.triples for kn in ([0] if x == 0 else range(-1, x + 1)))
        self.type_id = {t: i for i, t in enumerate(self.types)}
        self.P = [comb(n + s + x, n) * comb(s + x, s) for n, s, x, kn in self.types]
        self.classes = {}       # strain -> list of (ids, offset, size)
        self.offset = {}        # strain -> {ids: offset}
        self.M = {}             # strain -> positions
        for strain in ('N', 'T'):
            rows, off = [], 0
            for ids in self._class_ids(strain):
                size = self.class_size(strain, ids)
                rows.append((ids, off, size))
                off += size
            self.classes[strain] = rows
            self.offset[strain] = {ids: o for ids, o, _ in rows}
            self.M[strain] = off
        self.base = {'N': 0, 'T': 2 * self.M['N']}
        self.entries = 2 * (self.M['N'] + self.M['T'])

    # ------------------------------------------------------------------ classes
    def knowledge_ok(self, suits):
        """Is this (n, s, x, kn) x 4 a normalized, consistent knowledge state for hand size k?"""
        k = self.k
        unknown = [t for t in suits if t[3] == UNKNOWN]
        eK = sum(t[3] for t in suits if t[3] != UNKNOWN)
        wK = sum(t[2] - t[3] for t in suits if t[3] != UNKNOWN)
        if not unknown:
            return eK == k and wK == k
        return len(unknown) >= 2 and eK < k and wK < k

    def _class_ids(self, strain):
        k = self.k
        tot = (k, k, 2 * k)
        out = []
        tri = self.triples

        def rest(first, chosen, left):          # ascending triples from index `first` filling `left` suits
            if left == 0:
                if all(sum(t[j] for t in chosen) == tot[j] for j in range(3)):
                    yield tuple(chosen)
                return
            for i in range(first, len(tri)):
                t = tri[i]
                if all(sum(c[j] for c in chosen) + t[j] <= tot[j] for j in range(3)):
                    yield from rest(i, chosen + [t], left - 1)

        if strain == 'N':
            shapes = ((None, sh) for sh in rest(0, [], 4))
        else:
            shapes = ((t0, sh[1:]) for t0 in tri if sum(t0) > 0 for sh in rest(0, [t0], 3))
        for t0, side in shapes:
            opts = lambda t: [0] if t[2] == 0 else range(-1, t[2] + 1)
            for k0 in ([None] if t0 is None else opts(t0)):
                for kns in product(*[opts(t) for t in side]):
                    suits = [t + (kn,) for t, kn in zip(side, kns)]
                    if any(a > b for a, b in zip(suits, suits[1:])):
                        continue            # side suits must ascend as types
                    allsuits = suits if t0 is None else [t0 + (k0,)] + suits
                    if self.knowledge_ok(allsuits):
                        out.append(tuple(self.type_id[t] for t in allsuits))
        out.sort()
        return out

    def _digits(self, strain, ids):
        """[(radix, m, P)] for the trump suit (m = 0 marks it) and each run of equal side types."""
        d = []
        side = ids
        if strain == 'T':
            d.append((self.P[ids[0]], 0, self.P[ids[0]]))
            side = ids[1:]
        for t, g in groupby(side):
            m = len(list(g))
            d.append((comb(self.P[t] + m - 1, m), m, self.P[t]))
        return d

    def class_size(self, strain, ids):
        size = 1
        for radix, _, _ in self._digits(strain, ids):
            size *= radix
        return size

    # ------------------------------------------------------------------ patterns
    @staticmethod
    def pattern_rank(nmask, smask, L):
        """Masks over positions 0..L-1 (bit i = the i-th lowest remaining card of the suit)."""
        rn, i = 0, 0
        for p in range(L):
            if nmask >> p & 1:
                i += 1
                rn += comb(p, i)
        rs, j, q = 0, 0, 0
        for p in range(L):
            if nmask >> p & 1:
                continue
            if smask >> p & 1:
                j += 1
                rs += comb(q, j)
            q += 1
        n, s = bin(nmask).count('1'), bin(smask).count('1')
        return rn * comb(L - n, s) + rs

    @staticmethod
    def pattern_unrank(r, n, s, x):
        L = n + s + x
        rn, rs = divmod(r, comb(L - n, s))

        def subset(rank, size, universe):       # colex unrank: positions, highest first
            pos = []
            for i in range(size, 0, -1):
                c = i - 1
                while comb(c + 1, i) <= rank:
                    c += 1
                pos.append(c)
                rank -= comb(c, i)
            return pos
        npos = set(subset(rn, n, L))
        free = [p for p in range(L) if p not in npos]
        spos = {free[q] for q in subset(rs, s, L - n)}
        nmask = sum(1 << p for p in npos)
        smask = sum(1 << p for p in spos)
        return nmask, smask

    # ------------------------------------------------------------------ rank
    def canonical(self, hN, hS, pool, el, trump, leader):
        """Raw position at a trick boundary (bit masks; el a 4-sequence of None or int; trump 0..3 or 4; leader 0..3)
        -> (strain, leader_bit, suits) with suits = [(type id, pattern rank)] in canonical order."""
        k = bin(hN).count('1')
        assert k == self.k and bin(hS).count('1') == k and bin(pool).count('1') == 2 * k
        el = normalize(pool, k, k, tuple(el))
        assert el is not None, 'inconsistent knowledge'
        el = list(el)
        if leader >= 2:                          # half-turn
            hN, hS = hS, hN
            for s in range(4):
                if el[s] is not None:
                    el[s] = bin(pool & SUIT[s]).count('1') - el[s]
            leader -= 2
        suits = []
        for s in range(4):
            live = (hN | hS | pool) >> (13 * s) & 0x1FFF
            n = s_ = x = 0
            nmask = smask = 0
            pos = 0
            for r in range(13):
                if not live >> r & 1:
                    continue
                c = 13 * s + r
                if hN >> c & 1:
                    nmask |= 1 << pos
                    n += 1
                elif hS >> c & 1:
                    smask |= 1 << pos
                    s_ += 1
                else:
                    x += 1
                pos += 1
            t = self.type_id[(n, s_, x, UNKNOWN if el[s] is None else el[s])]
            suits.append((t, self.pattern_rank(nmask, smask, pos)))
        if trump < 4 and (hN | hS | pool) & SUIT[trump]:
            return 'T', leader, [suits[trump]] + sorted(suits[:trump] + suits[trump + 1:])
        return 'N', leader, sorted(suits)

    def rank(self, hN, hS, pool, el, trump, leader):
        strain, lead, suits = self.canonical(hN, hS, pool, el, trump, leader)
        ids = tuple(t for t, _ in suits)
        ranks = [r for _, r in suits]
        r, i = 0, 0
        for radix, m, P in self._digits(strain, ids):
            if m == 0:
                d = ranks[i]
                i += 1
            else:
                d = sum(comb(ranks[i + j] + j, j + 1) for j in range(m))
                i += m
            r = r * radix + d
        return self.base[strain] + 2 * (self.offset[strain][ids] + r) + lead

    # ------------------------------------------------------------------ unrank
    def unrank(self, slot):
        """slot -> (hN, hS, pool, el, trump, leader): the canonical concrete position.
        Suits are laid out in canonical order (trump suit, if any, is suit 0) on the lowest ranks."""
        strain = 'T' if slot >= self.base['T'] else 'N'
        pos, lead = divmod(slot - self.base[strain], 2)
        rows = self.classes[strain]
        lo, hi = 0, len(rows) - 1
        while lo < hi:                           # last class with offset <= pos
            mid = (lo + hi + 1) // 2
            if rows[mid][1] <= pos:
                lo = mid
            else:
                hi = mid - 1
        ids, off, size = rows[lo]
        r = pos - off
        digs = self._digits(strain, ids)
        vals = []
        for radix, m, P in reversed(digs):
            r, d = divmod(r, radix)
            vals.append(d)
        vals.reverse()
        ranks = []
        for (radix, m, P), d in zip(digs, vals):
            if m == 0:
                ranks.append(d)
                continue
            group = []
            for i in range(m, 0, -1):            # multiset unrank, highest first
                c = i - 1
                while comb(c + 1, i) <= d:
                    c += 1
                group.append(c - (i - 1))
                d -= comb(c, i)
            ranks += reversed(group)
        hN = hS = pool = 0
        el = []
        for s, (t, pr) in enumerate(zip(ids, ranks)):
            n, s_, x, kn = self.types[t]
            nmask, smask = self.pattern_unrank(pr, n, s_, x)
            for p in range(n + s_ + x):
                c = 1 << (13 * s + p)
                if nmask >> p & 1:
                    hN |= c
                elif smask >> p & 1:
                    hS |= c
                else:
                    pool |= c
            el.append(None if kn == UNKNOWN else kn)
        return hN, hS, pool, tuple(el), (0 if strain == 'T' else 4), lead


def line(hN, hS, pool, el, trump, leader):
    """One text line per position: trump leader hN hS pool cE cW el0 el1 el2 el3   (masks in hex, el '-' = unknown)."""
    k = bin(hN).count('1')
    return '%d %d %x %x %x %d %d %s' % (trump, leader, hN, hS, pool, k, k, ' '.join('-' if e is None else str(e) for e in el))


if __name__ == '__main__':
    for k in (int(a) for a in sys.argv[1:]):
        ix = Index(k)
        print('k=%d: %d suit types; notrump %d classes, %d positions; trump %d classes, %d positions; entries %d'
              % (k, len(ix.types), len(ix.classes['N']), ix.M['N'], len(ix.classes['T']), ix.M['T'], ix.entries), flush=True)
