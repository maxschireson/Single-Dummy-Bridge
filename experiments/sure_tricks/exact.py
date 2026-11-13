"""Exact single-dummy value against best defence, for a small set of weighted layouts ("worlds").

Declarer sees his own two hands and the cards played. In each world the defenders see everything
and know declarer's whole strategy. Declarer commits to ONE strategy (a card for every public
history); a world is won if that strategy takes `need` tricks against every defence in that world.

    true value of a card   = max over strategies starting with it of the weight of worlds won
    fused (PIMC) value     = weight of worlds where the card is double-dummy good enough
                             (a different continuation may be assumed in each world)

The difference between the two is the strategy-fusion error of that card.

Method: AND/OR search over public states. A node returns the set of maximal world-sets that a
single strategy can win from there (Pareto front over worlds). DDS prunes: a world that is
double-dummy lost is dropped, and when at most one winnable world is left, double dummy is exact.
This is the same idea as the Pareto fronts of the alpha-mu algorithm, run to the end of the hand.
"""
from functools import lru_cache

from fusionlab import DDS, Game, SUITS, symbol, winner


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
    return tuple(out)


def maximal(masks):
    masks = sorted(set(masks), key=lambda m: -bin(m).count('1'))
    out = []
    for m in masks:
        if not any(m & ~k == 0 for k in out):
            out.append(m)
    return tuple(out)


class Exact:
    def __init__(self, hands, trump, leader, trick, need, side, weights=None, dds=None):
        """hands[world][seat] = cards still held (current-trick cards excluded); identical for the
        declaring side (seats with seat % 2 == side) in every world. need = tricks declarer must still
        take, the current trick included."""
        self.dds = dds or DDS(cache_path='')
        self.trump, self.side, self.k = trump, side, len(hands)
        self.weights = list(weights or [1.] * self.k)
        self.root_hands = [tuple(bits(h) for h in w) for w in hands]
        self.root_trick, self.root_leader, self.root_need = tuple(trick), leader, need
        for w in self.root_hands[1:]:
            if any(w[s] != self.root_hands[0][s] for s in range(4) if s % 2 == side):
                raise ValueError('declaring side differs across worlds')
            if w[0] | w[1] | w[2] | w[3] != self.all_cards(0):
                raise ValueError('worlds hold different cards')
        self.memo, self.ddmemo, self.nodes, self.dd_calls = {}, {}, 0, 0

    def all_cards(self, world):
        w = self.root_hands[world]
        return w[0] | w[1] | w[2] | w[3]

    @classmethod
    def from_boards(cls, boards, prefix=(), weights=None, dds=None, need=None):
        """Worlds as Board objects with the same declaring hands and contract; `prefix` = cards already
        played (ints), which must be legal and play out identically in every world."""
        games = []
        for b in boards:
            g = Game(b)
            for c in prefix:
                g.play(c)
            games.append(g)
        g0, c0 = games[0], boards[0].contract
        for g in games[1:]:
            if g.leader != g0.leader or g.trick != g0.trick or g.declarer_tricks != g0.declarer_tricks:
                raise ValueError('prefix plays out differently across worlds')
        need = (need if need is not None else c0.level + 6) - g0.declarer_tricks
        return cls([[tuple(h) for h in g.hands] for g in games], c0.trump, g0.leader, g0.trick, need,
                   c0.declarer % 2, weights, dds)

    # ---- helpers -------------------------------------------------------------------------
    def hand(self, world, seat, played):
        return self.root_hands[world][seat] & ~played

    def dd(self, world, played, trick, leader):
        key = (world, played, trick, leader)
        v = self.ddmemo.get(key)
        if v is None:
            hands = tuple(cards_of(self.hand(world, s, played)) for s in range(4))
            v = self.dds.solve(hands, self.trump, leader, trick)[0]
            self.ddmemo[key] = v
            self.dd_calls += 1
        return v

    def legal(self, hand_mask, trick):
        if trick:
            led = trick[0][1] // 13
            follow = hand_mask & (0x1FFF << (13 * led))
            if follow:
                return follow
        return hand_mask

    def groups(self, hand_mask, legal_mask, live):
        """Representatives of legal cards up to touching-card equivalence. `live` = every unplayed card
        of all four hands. Two cards of one hand are equivalent when no live card of another hand
        lies between them."""
        reps = []
        for s in range(4):
            prev_in_hand = False
            for r in range(13):
                c = 13 * s + r
                bit = 1 << c
                if hand_mask & bit:
                    if legal_mask & bit and not prev_in_hand:
                        reps.append(c)
                    prev_in_hand = True
                elif live & bit:
                    prev_in_hand = False
        return reps

    def step(self, played, trick, leader, need, seat, c):
        played |= 1 << c
        trick = trick + ((seat, c),)
        if len(trick) == 4:
            w = winner(trick, self.trump)
            return played, (), w, need - (w % 2 == self.side)
        return played, trick, leader, need

    def differ(self, worlds, played):
        """Bitmask of suits in which the hidden hands differ between these worlds."""
        d = 0
        first = worlds[0]
        for s in range(4):
            if s % 2 == self.side:
                continue
            a = self.hand(first, s, played)
            for i in worlds[1:]:
                x = a ^ self.hand(i, s, played)
                for suit in range(4):
                    if x & (0x1FFF << (13 * suit)):
                        d |= 1 << suit
        return d

    def weight(self, mask):
        return sum(w for i, w in enumerate(self.weights) if mask >> i & 1)

    # ---- search --------------------------------------------------------------------------
    def front(self, played, trick, leader, need, alive):
        """Maximal sets of worlds (subsets of `alive`) one strategy can win from here."""
        if need <= 0:
            return (alive,)
        key = (played, trick, leader, need, alive)
        r = self.memo.get(key)
        if r is not None:
            return r
        self.nodes += 1
        seat = (leader + len(trick)) % 4
        declaring = seat % 2 == self.side
        worlds = [i for i in range(self.k) if alive >> i & 1]
        left = bin(self.hand(worlds[0], seat, played)).count('1')       # tricks left, this one included
        if left < need:
            self.memo[key] = (0,)
            return (0,)
        vals = {i: self.dd(i, played, trick, leader) for i in worlds}
        if declaring:
            win = 0
            for i in worlds:
                if max(vals[i].values()) >= need:
                    win |= 1 << i
        else:
            win = 0
            for i in worlds:
                if left - max(vals[i].values()) >= need:
                    win |= 1 << i
        if win & (win - 1) == 0:                # zero or one winnable world: double dummy is exact
            self.memo[key] = (win,)
            return (win,)
        live = self.all_cards(0) & ~played | bits(c for _, c in trick)
        # Each winnable world can always be won on its own (play double dummy for it), so the
        # singletons are a floor; only strategies that win two or more worlds need searching for.
        singles = tuple(1 << i for i in worlds if win >> i & 1)
        if declaring:
            h = self.hand(worlds[0], seat, played)
            reps = self.groups(h, self.legal(h, trick), live)
            cand = []
            for c in reps:
                u = 0
                for i in worlds:
                    if win >> i & 1 and vals[i][c] >= need:
                        u |= 1 << i
                if u & (u - 1):
                    cand.append((c, u))
            differ = self.differ(worlds, played)
            cand.sort(key=lambda cu: (-bin(cu[1]).count('1'), differ >> (cu[0] // 13) & 1, -(cu[0] % 13)))
            best = singles
            for c, u in cand:
                if any(u & ~m == 0 for m in best):
                    continue
                best = maximal(best + self.front(*self.step(played, trick, leader, need, seat, c), u))
                if win in best:
                    break
            r = best
        else:
            hands = {i: self.hand(i, seat, played) for i in worlds if win >> i & 1}
            same = len(set(hands.values())) == 1
            options = {}                                    # card -> worlds where the defender can play it
            for i, h in hands.items():
                lg = self.legal(h, trick)
                for c in (self.groups(h, lg, live) if same else cards_of(lg)):
                    options[c] = options.get(c, 0) | 1 << i
            fronts = (win,)
            # A card held in one world only tells declarer which world it is, and that world is
            # winnable: it cannot hurt him. Only cards playable in two or more worlds matter.
            for c, a in sorted(options.items(), key=lambda ca: (-bin(ca[1]).count('1'), ca[0] % 13)):
                if a & (a - 1) == 0:
                    continue
                sub = self.front(*self.step(played, trick, leader, need, seat, c), a)
                fronts = maximal([(m & ~a) | (m & x) for m in fronts for x in sub])
                if all(m & (m - 1) == 0 for m in fronts):
                    fronts = singles
                    break
            r = fronts
        self.memo[key] = r
        return r

    def root(self):
        """Per legal card of the declaring side at the root: fused value, true value (both as weight
        fractions) and the best world-set. Only for a root where declarer or dummy is to play."""
        played, trick, leader, need = 0, self.root_trick, self.root_leader, self.root_need
        seat = (leader + len(trick)) % 4
        if seat % 2 != self.side:
            raise ValueError('root must be a declaring-side decision')
        total = sum(self.weights)
        alive = (1 << self.k) - 1
        h = self.hand(0, seat, played)
        live = self.all_cards(0) | bits(c for _, c in trick)
        out = {}
        for c in self.groups(h, self.legal(h, trick), live):
            u = 0
            for i in range(self.k):
                if self.dd(i, played, trick, leader)[c] >= need:
                    u |= 1 << i
            fr = self.front(*self.step(played, trick, leader, need, seat, c), u) if u else (0,)
            bestm = max(fr, key=self.weight)
            out[symbol(c)] = dict(fused=self.weight(u) / total, true=self.weight(bestm) / total, wins=bestm, dd=u)
        return out
