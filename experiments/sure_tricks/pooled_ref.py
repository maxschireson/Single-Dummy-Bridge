"""Reference for the pooled-defender game with shape knowledge. Plain minimax, no pruning, no card
equivalences: slow and meant to be obviously right. It defines the value an ending-table entry must hold.

The game. North and South are the declaring side and their cards are known. The defenders' cards are one
pool; who holds a pool card is settled only when it is played. What is known about the split:

    cE, cW   how many cards East and West hold (cE + cW = pool size)
    el[s]    None if East's length in suit s is unknown, else East's exact number of pool cards in suit s
             (West then holds the rest). A show-out is the special case el[s] = 0 (East void) or
             el[s] = x[s] (West void), where x[s] is the number of pool cards in suit s.

A split of the pool is consistent if the hand sizes and every exact length hold. A defender may play a pool
card exactly when some consistent split gives him that card and makes the play legal (he follows suit unless
he holds none of the suit led). Playing it updates the knowledge: the card leaves the pool, his count drops,
an exact length drops when East plays from that suit, and failing to follow fixes the suit led at 0 for him.
Declarer sees his two hands and every card played, so the game has perfect information and its minimax value
is  max over declarer strategies of min over consistent splits and defences  of declarer's tricks.

Cards are ints 13 * suit + rank, rank 0 (the two) to 12 (the ace). Seats 0..3 = N, E, S, W. trump 0..3, or 4 = notrump.
"""
from functools import lru_cache

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


def normalize(pool, cE, cW, el):
    """Canonical knowledge for this pool, or None if no split is consistent.
    Lengths that are forced become exact: a suit with no pool cards, the unknown suits when East (or West) has
    no cards left for them, and a single remaining unknown suit."""
    x = [bin(pool & SUIT[s]).count('1') for s in range(4)]
    if cE < 0 or cW < 0 or cE + cW != sum(x):
        return None
    el = list(el)
    for s in range(4):
        if x[s] == 0:
            el[s] = 0
        elif el[s] is not None and not 0 <= el[s] <= x[s]:
            return None
    while True:
        unknown = [s for s in range(4) if el[s] is None]
        eK = sum(el[s] for s in range(4) if el[s] is not None)
        wK = sum(x[s] - el[s] for s in range(4) if el[s] is not None)
        if eK > cE or wK > cW:
            return None
        if not unknown:
            return tuple(el)            # eK == cE follows from the totals
        eu, u = cE - eK, sum(x[s] for s in unknown)
        if eu == 0:
            for s in unknown:
                el[s] = 0
        elif eu == u:
            for s in unknown:
                el[s] = x[s]
        elif len(unknown) == 1:
            el[unknown[0]] = eu
        else:
            return tuple(el)


def defender_plays(seat, pool, cE, cW, el, led):
    """Every card the defender in `seat` (1 East, 3 West) may play, with the state after it:
    list of (card, pool, cE, cW, el). `led` is the suit led, or None when he is on lead."""
    east = seat == 1
    x = [bin(pool & SUIT[s]).count('1') for s in range(4)]
    out = []
    for c in cards_of(pool):
        s = c // 13
        e2 = list(el)
        if led is not None and s != led:            # not following: he must hold none of the suit led
            void_value = 0 if east else x[led]
            if e2[led] is None:
                e2[led] = void_value
            elif e2[led] != void_value:
                continue
        if e2[s] is not None:
            if east:
                if e2[s] < 1:
                    continue
                e2[s] -= 1
            elif x[s] - e2[s] < 1:
                continue
        n = normalize(pool ^ (1 << c), cE - east, cW - (not east), e2)
        if n is not None:
            out.append((c, pool ^ (1 << c), cE - east, cW - (not east), n))
    return out


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


class Pooled:
    def __init__(self, trump):
        self.trump = trump
        self.memo = {}

    def value(self, hN, hS, pool, cE, cW, el, leader, trick=()):
        """Tricks North-South can guarantee from here on. hN, hS, pool are bit masks; el a 4-tuple (None or int)."""
        el = normalize(pool, cE, cW, el)
        assert el is not None, 'no consistent split'
        return self._v(hN, hS, pool, cE, cW, el, leader, tuple(trick))

    def _v(self, hN, hS, pool, cE, cW, el, leader, trick):
        if not (hN or hS or pool or trick):
            return 0
        key = (hN, hS, pool, cE, cW, el, leader, trick)
        if key in self.memo:
            return self.memo[key]
        seat = (leader + len(trick)) & 3
        led = trick[0] // 13 if trick else None
        results = []
        if seat in (0, 2):
            h = hN if seat == 0 else hS
            legal = h & SUIT[led] if led is not None and h & SUIT[led] else h
            for c in cards_of(legal):
                nN, nS = (hN ^ (1 << c), hS) if seat == 0 else (hN, hS ^ (1 << c))
                results.append(self._after(nN, nS, pool, cE, cW, el, leader, trick + (c,)))
            v = max(results)
        else:
            for c, p2, e2, w2, el2 in defender_plays(seat, pool, cE, cW, el, led):
                results.append(self._after(hN, hS, p2, e2, w2, el2, leader, trick + (c,)))
            v = min(results)
        self.memo[key] = v
        return v

    def _after(self, hN, hS, pool, cE, cW, el, leader, trick):
        if len(trick) < 4:
            return self._v(hN, hS, pool, cE, cW, el, leader, trick)
        w = trick_winner(leader, trick, self.trump)
        return (w % 2 == 0) + self._v(hN, hS, pool, cE, cW, el, w, ())


def solve(N, S, pool, cE, cW, el, trump, leader, trick=()):
    """Convenience: card lists in, guaranteed tricks out."""
    return Pooled(trump).value(bits(N), bits(S), bits(pool), cE, cW, tuple(el), leader, trick)
