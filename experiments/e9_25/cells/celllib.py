"""Driver for the cell-game solver (cells.cpp), cell enumeration, and a brute-force reference over explicit layouts.

Cards are ints 13 * suit + rank (2 = 0 ... A = 12). Seats 0..3 = N, E, S, W; North-South declare. Trump 0..3 or 4.
A cell is (eu, pin): eu[s] = East's unnamed cards in suit s, pin = mask of the named cards East holds.
"""
import json
import math
import subprocess
from itertools import combinations, product

SUIT = [0x1FFF << (13 * s) for s in range(4)]


def bits(cards):
    m = 0
    for c in cards:
        m |= 1 << c
    return m


def cards_of(mask):
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def popcount(x):
    return bin(x).count('1')


class Solver:
    def __init__(self, binary='./cells', flags=()):
        self.proc = subprocess.Popen([binary, *flags], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.ncells = 0

    def _send(self, text):
        self.proc.stdin.write(text + '\n')

    def _ask(self, text):
        self._send(text)
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def position(self, trump, leader, hN, hS, pool, named=0, trick=()):
        self._send('P %d %d %x %x %x %x %s' % (trump, leader, hN, hS, pool, named, ' '.join(str(c) for c in trick)))
        self.ncells = 0

    def cells(self, cells, weights=None):
        for i, (eu, pin) in enumerate(cells):
            self._send('C %d %d %d %d %x %.12g' % (*eu, pin, 1. if weights is None else weights[i]))
        self.ncells += len(cells)

    def winset(self, need, card, cells='*'):
        ct = cells if cells == '*' else ','.join(str(i) for i in cells)
        return self._ask('W %d %d %s' % (need, card, ct))

    def query(self, need, cells='*', cards='*'):
        ct = cells if cells == '*' else ','.join(str(i) for i in cells)
        kt = cards if cards == '*' else ','.join(str(c) for c in cards)
        r = self._ask('Q %d %s %s' % (need, kt, ct))
        if 'cards' in r:
            r['cards'] = {int(k): v for k, v in r['cards'].items()}
        return r

    def value(self, cells='*'):
        ct = cells if cells == '*' else ','.join(str(i) for i in cells)
        return self._ask('V %s' % ct)

    def reset(self):
        self._send('R')

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def enumerate_cells(pool, cE, cW, voidE=0, voidW=0, named=0):
    """Every cell consistent with the hand sizes and show-outs: list of ((eu0..eu3), pin, layouts in the cell).
    voidE / voidW: suits (bit per suit) East / West is known to hold none of."""
    assert cE + cW == popcount(pool)
    un = [popcount(pool & ~named & SUIT[s]) for s in range(4)]
    nm = cards_of(named & pool)
    out = []
    for r in range(len(nm) + 1):
        for east_named in combinations(nm, r):
            pin = bits(east_named)
            ok = True
            for s in range(4):
                ns = named & pool & SUIT[s]
                if voidE >> s & 1 and pin & SUIT[s]:
                    ok = False
                if voidW >> s & 1 and (ns & ~pin):
                    ok = False
            if not ok:
                continue
            rest = cE - r
            if rest < 0 or cW - (len(nm) - r) < 0:
                continue
            ranges = []
            for s in range(4):
                if voidE >> s & 1:
                    ranges.append([0])
                elif voidW >> s & 1:
                    ranges.append([un[s]])
                else:
                    ranges.append(range(un[s] + 1))
            for eu in product(*ranges):
                if sum(eu) != rest:
                    continue
                w = 1
                for s in range(4):
                    w *= math.comb(un[s], eu[s])
                out.append((eu, pin, w))
    return out


def cell_of(east_hand, pool, named=0):
    """The cell an explicit layout (East's hand as a mask) belongs to."""
    return tuple(popcount(east_hand & ~named & SUIT[s]) for s in range(4)), east_hand & named


def layouts_of(cells, pool, named=0):
    """Every explicit layout (East's hand mask) in the given cells [(eu, pin), ...]."""
    out = set()
    un = [cards_of(pool & ~named & SUIT[s]) for s in range(4)]
    for eu, pin in cells:
        per_suit = [[bits(c) for c in combinations(un[s], eu[s])] for s in range(4)]
        for parts in product(*per_suit):
            out.add(pin | parts[0] | parts[1] | parts[2] | parts[3])
    return frozenset(out)


def trick_winner(leader, cards, trump):
    best = 0
    for i in range(1, 4):
        sb, si = cards[best] // 13, cards[i] // 13
        if si == sb:
            if cards[i] > cards[best]:
                best = i
        elif si == trump:
            best = i
    return (leader + best) & 3


class Brute:
    """Tricks North-South can guarantee with one line against every layout in an explicit set, defenders seeing all.
    A layout is East's hand at the root (a mask); West holds the rest of the root pool. Knowledge is the set of layouts
    still consistent with the cards the defenders have played. No pruning, no equivalences."""

    def __init__(self, trump):
        self.trump = trump
        self.memo = {}

    def value(self, hN, hS, pool, layouts, leader, trick=()):
        return self._v(hN, hS, pool, frozenset(layouts), leader, tuple(trick))

    def _v(self, hN, hS, pool, lays, leader, trick):
        if not (hN or hS or pool or trick):
            return 0
        key = (hN, hS, pool, lays, leader, trick)
        if key in self.memo:
            return self.memo[key]
        seat = (leader + len(trick)) & 3
        led = trick[0] // 13 if trick else None
        if seat in (0, 2):
            h = hN if seat == 0 else hS
            legal = h & SUIT[led] if led is not None and h & SUIT[led] else h
            v = -1
            for c in cards_of(legal):
                nN, nS = (hN ^ (1 << c), hS) if seat == 0 else (hN, hS ^ (1 << c))
                v = max(v, self._after(nN, nS, pool, lays, leader, trick + (c,)))
        else:
            v = 99
            for c in cards_of(pool):
                keep = []
                for e in lays:
                    hand = (e & pool) if seat == 1 else (pool & ~e)
                    if not hand >> c & 1:
                        continue
                    if led is not None and c // 13 != led and hand & SUIT[led]:
                        continue
                    keep.append(e)
                if keep:
                    v = min(v, self._after(hN, hS, pool ^ (1 << c), frozenset(keep), leader, trick + (c,)))
            assert v != 99, 'a defender has no legal card in any layout'
        self.memo[key] = v
        return v

    def _after(self, hN, hS, pool, lays, leader, trick):
        if len(trick) < 4:
            return self._v(hN, hS, pool, lays, leader, trick)
        w = trick_winner(leader, trick, self.trump)
        return (w % 2 == 0) + self._v(hN, hS, pool, lays, w, ())
