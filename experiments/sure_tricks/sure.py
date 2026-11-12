"""Single-dummy sure tricks: what declarer can guarantee against EVERY split of the unseen cards.

The defenders' cards are one pool. Who holds a pool card is settled only when it is played, subject to
each defender's hand size, the suits he has shown out of, and any cards pinned to one defender
(`known`). Declarer sees his own two hands and the cards played, so this pooled game has perfect
information and its minimax value is exactly

    max over declarer strategies of  min over splits and defences  of declarer's tricks.

With nothing pinned it is the plain single-dummy guarantee; pinning cards or voids gives the
guarantee under that much knowledge ("1.x dummy"); pinning everything is double dummy.
"""
import sys
from fusionlab import Game, SEATS, SUITS, card, symbol, winner

SUITMASK = [0x1FFF << (13 * s) for s in range(4)]


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


class Sure:
    def __init__(self, hands, pool, counts, trump, leader, trick=(), side=0, voids=None, known=None):
        """hands: {seat: cards} for declarer and dummy. pool: unseen cards. counts: {defender seat: cards held}.
        voids: {defender: set of suit indices}. known: {defender: cards certainly his}."""
        self.side, self.trump = side, trump
        self.decl = tuple(s for s in range(4) if s % 2 == side)
        self.defs = tuple(s for s in range(4) if s % 2 != side)
        self.h0 = {s: bits(hands[s]) for s in self.decl}
        self.pool0 = bits(pool)
        self.cnt0 = tuple(counts[s] for s in self.defs)
        v = voids or {}
        self.void0 = tuple(sum(1 << x for x in v.get(s, ())) for s in self.defs)
        k = known or {}
        self.known0 = tuple(bits(k.get(s, ())) for s in self.defs)
        self.leader0, self.trick0 = leader, tuple(trick)
        self.memo = {}
        self.nodes = 0
        self.reduce = True          # False: no touching-card reduction for the defenders (for checking)

    @classmethod
    def from_game(cls, board, prefix, known=None):
        """Declarer's view after `prefix` (cards played, ints): hands, pool, counts and show-outs."""
        g = Game(board)
        voids = {}
        for c in prefix:
            o = g.observation()
            if o.trick and c // 13 != o.trick[0][1] // 13:
                voids.setdefault(o.actor, set()).add(o.trick[0][1] // 13)
            g.play(c)
        side = board.contract.declarer % 2
        decl = [s for s in range(4) if s % 2 == side]
        defs = [s for s in range(4) if s % 2 != side]
        pool = [c for s in defs for c in g.hands[s]]
        self = cls({s: tuple(g.hands[s]) for s in decl}, pool, {s: len(g.hands[s]) for s in defs}, board.contract.trump,
                   g.leader, g.trick, side, {s: v for s, v in voids.items() if s in defs}, known)
        self.won = g.declarer_tricks
        return self

    # ---- consistency of the pool with what is known ----------------------------------------
    def feasible(self, pool, cnt, void, known):
        must = [known[0], known[1]]
        for s in range(4):
            cards = pool & SUITMASK[s]
            if not cards:
                continue
            a, b = void[0] >> s & 1, void[1] >> s & 1
            if a and b:
                return False
            if a:
                must[1] |= cards
            if b:
                must[0] |= cards
        if must[0] & must[1]:
            return False
        return bin(must[0]).count('1') <= cnt[0] and bin(must[1]).count('1') <= cnt[1]

    def defender_moves(self, i, pool, cnt, void, known, trick):
        """(card, new void mask for defender i) for every card defender i may turn up with."""
        out = []
        led = trick[0][1] // 13 if trick else None
        for c in cards_of(pool):
            s = c // 13
            if known[1 - i] >> c & 1 or void[i] >> s & 1:
                continue
            v = void[i]
            if led is not None and s != led:
                if void[i] >> led & 1 == 0:
                    if known[i] & SUITMASK[led]:
                        continue
                    v |= 1 << led
            nv = (v, void[1]) if i == 0 else (void[0], v)
            nc = (cnt[0] - 1, cnt[1]) if i == 0 else (cnt[0], cnt[1] - 1)
            nk = (known[0] & ~(1 << c), known[1] & ~(1 << c))
            if self.feasible(pool & ~(1 << c), nc, nv, nk):
                out.append((c, nv, nc, nk))
        return out

    @staticmethod
    def reps(cands, mine, live, top=False):
        """One card per run of touching cards (the lowest, or the highest with top=True): `cands` are the
        cards on offer, `mine` every card the player could equally hold, `live` every card not yet played."""
        out = []
        cands = set(cands)
        for s in range(4):
            run = False
            for r in (range(12, -1, -1) if top else range(13)):
                c = 13 * s + r
                b = 1 << c
                if mine & b:
                    if c in cands and not run:
                        out.append(c)
                        run = True
                    elif c not in cands:
                        run = False
                elif live & b:
                    run = False
        return out

    # ---- search -----------------------------------------------------------------------------
    def can(self, need, state=None):
        """True if declarer can guarantee `need` more tricks from the state (default: the root)."""
        if state is None:
            state = (self.h0[self.decl[0]], self.h0[self.decl[1]], self.pool0, self.cnt0, self.void0, self.known0,
                     self.trick0, self.leader0)
        return self._can(need, *state)

    def _can(self, need, ha, hb, pool, cnt, void, known, trick, leader):
        if need <= 0:
            return True
        seat = (leader + len(trick)) % 4
        left = bin(ha).count('1') if seat == self.decl[0] else bin(hb).count('1') if seat == self.decl[1] else cnt[self.defs.index(seat)]
        if left < need:
            return False
        key = (need, ha, hb, pool, cnt, void, known, trick, leader)
        r = self.memo.get(key)
        if r is not None:
            return r
        self.nodes += 1
        live = ha | hb | pool | bits(c for _, c in trick)
        if seat % 2 == self.side:
            h = ha if seat == self.decl[0] else hb
            legal = h
            if trick and h & SUITMASK[trick[0][1] // 13]:
                legal = h & SUITMASK[trick[0][1] // 13]
            r = False
            for c in sorted(self.reps(cards_of(legal), h, live), key=lambda c: -(c % 13)):
                na, nb = (ha & ~(1 << c), hb) if seat == self.decl[0] else (ha, hb & ~(1 << c))
                if self._next(need, na, nb, pool, cnt, void, known, trick, leader, seat, c):
                    r = True
                    break
        else:
            i = self.defs.index(seat)
            moves = self.defender_moves(i, pool, cnt, void, known, trick)
            # Touching pool cards: once the other defender has played to this trick they are
            # interchangeable, so one per run is enough. Before that the choice decides which defender
            # can win the trick (the lowest of a run leaves partner only higher cards of it, the highest
            # only lower ones), so both ends of each run are kept; a middle card adds nothing to those.
            free = pool & ~known[0] & ~known[1]
            fc = [m[0] for m in moves if free >> m[0] & 1]
            keep = {m[0] for m in moves if not free >> m[0] & 1}
            if not self.reduce:
                keep |= set(fc)
            elif any(x == self.defs[1 - i] for x, _ in trick):
                keep |= set(self.reps(fc, free, live))
            else:
                keep |= set(self.reps(fc, free, live)) | set(self.reps(fc, free, live, top=True))
            r = True
            for c, nv, nc, nk in sorted(moves, key=lambda m: -(m[0] % 13)):
                if c not in keep:
                    continue
                if not self._next(need, ha, hb, pool & ~(1 << c), nc, nv, nk, trick, leader, seat, c):
                    r = False
                    break
        self.memo[key] = r
        return r

    def _next(self, need, ha, hb, pool, cnt, void, known, trick, leader, seat, c):
        trick = trick + ((seat, c),)
        if len(trick) == 4:
            w = winner(trick, self.trump)
            return self._can(need - (w % 2 == self.side), ha, hb, pool, cnt, void, known, (), w)
        return self._can(need, ha, hb, pool, cnt, void, known, trick, leader)

    def root_cards(self, top):
        """For each card of the declaring side at the root: the most tricks it guarantees (<= top)."""
        seat = (self.leader0 + len(self.trick0)) % 4
        ha, hb = self.h0[self.decl[0]], self.h0[self.decl[1]]
        h = ha if seat == self.decl[0] else hb
        legal = h
        if self.trick0 and h & SUITMASK[self.trick0[0][1] // 13]:
            legal = h & SUITMASK[self.trick0[0][1] // 13]
        live = ha | hb | self.pool0 | bits(c for _, c in self.trick0)
        out = {}
        for c in self.reps(cards_of(legal), h, live):
            na, nb = (ha & ~(1 << c), hb) if seat == self.decl[0] else (ha, hb & ~(1 << c))
            n = top
            while n > 0 and not self._next(n, na, nb, self.pool0, self.cnt0, self.void0, self.known0, self.trick0, self.leader0, seat, c):
                n -= 1
            out[symbol(c)] = n
        return out
