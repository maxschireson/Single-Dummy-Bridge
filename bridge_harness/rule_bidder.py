"""A rule-based, configurable bidder: a Precision-style strong club, or a plain natural system.

Work in progress (Gen 8 prototype). The project's own code and rules: nothing here comes from
another program. It is meant to be a second bidding system whose meanings are known exactly, not
a strong bidder.

How it works. Every call that the rules define in a situation has a *meaning*: a range of high
card points, ranges of suit lengths, whether it forces partner, and sometimes a private test on
the hand (suit quality and the like). The bidder makes the first defined call whose meaning its
hand fits. The same tables explain every call made at the table, so each seat's shown ranges are
tracked through the auction, for partner and opponents alike. Where the tables stop, a general
procedure places the contract from the two hands' combined ranges and fits: game with enough for
game, an invitation when game is possible, a sign-off or a pass otherwise, and competition up to
the level the combined trump length supports.

Every range and threshold is a field of `Settings`, so a system is a small dictionary and can be
tuned (scripts/tune_rule_bidder.py tunes it for double-dummy IMPs).

Card ids are 13 * suit + rank with suits spades, hearts, diamonds, clubs and rank 0 = the two.
Calls are bidding_env tokens: 2 pass, 3 double, 4 redouble, 5 + 5 * (level - 1) + strain with
strains clubs, diamonds, hearts, spades, no trump = 0..4.
"""
from dataclasses import asdict, dataclass, fields

import numpy as np

from .system_bidders import RuleBidder, options_sha256

PASS, DOUBLE, REDOUBLE = 2, 3, 4
STRICT = False                      # tests and the tuner set this: a failing rule raises instead of passing
RULES = 'r2'                        # raised whenever a rule changes what the bidder calls: part of a system's identity
C, D, H, S, N = range(5)
MAJORS, MINORS, SUITS = (H, S), (C, D), (C, D, H, S)
BALANCED = ((4, 3, 3, 3), (4, 4, 3, 2), (5, 3, 3, 2))


def bid(level, strain):
    return 5 + 5 * (level - 1) + strain


def level_of(token):
    return (token - 5) // 5 + 1


def strain_of(token):
    return (token - 5) % 5


@dataclass(frozen=True)
class Settings:
    style: str = 'precision'        # 'precision': strong club, limited openings | 'standard': natural openings
    club_min: int = 16              # precision: 1C shows this many points or more
    open_min: int = 11              # one-level openings start here
    open_light: int = 1             # one point lighter with a six-card suit or two five-card suits
    limited_max: int = 15           # precision: top of the limited openings
    nt_lo: int = 14                 # 1NT opening range
    nt_hi: int = 16
    nt_five_major: bool = False     # 1NT may hold a five-card major
    two_clubs_len: int = 6          # precision 2C: this many clubs
    two_diamonds: bool = True       # precision 2D: three-suited, short diamonds
    weak_lo: int = 5                # weak two bids and three-level preempts
    weak_hi: int = 10
    weak_quality: int = 2           # of the five top honours in the suit
    preempt_len: int = 7
    neg_max: int = 7                # precision 1C - 1D shows at most this
    resp_min: int = 6               # least to respond to a one-level suit opening
    two_over_one: int = 11          # least for a new suit at the two level
    game: int = 25                  # combined points for 3NT or four of a major
    game_minor: int = 28
    slam: int = 33
    grand: int = 37
    invite_width: int = 2           # invite when the minimum is this close to game
    overcall_min1: int = 8          # overcalls at the one and two level
    overcall_min2: int = 11
    overcall_max: int = 17
    overcall_quality: int = 2
    takeout_min: int = 12
    nt_overcall_lo: int = 15
    nt_overcall_hi: int = 18
    jump_overcalls: bool = True     # weak jump overcalls
    balance: int = 3                # points borrowed in the pass-out seat
    compete: int = 0                # extra levels beyond combined trumps minus six
    penalty: int = 25               # combined minimum to double the opponents for penalty
    stayman: bool = True
    transfers: bool = True

    def __post_init__(self):
        if self.style not in ('precision', 'standard'):
            raise ValueError("style is 'precision' or 'standard'")
        if not 0 <= self.nt_lo <= self.nt_hi <= 40 or not 0 <= self.weak_lo <= self.weak_hi:
            raise ValueError('a range has its ends the wrong way round')

    @property
    def top(self):                  # top of a one-level suit opening
        return self.limited_max if self.style == 'precision' else 21


STANDARD = Settings(style='standard', nt_lo=15, nt_hi=17, two_diamonds=False)


class Hand:
    """What the rules look at: points, lengths and honours by strain (clubs, diamonds, hearts, spades)."""
    __slots__ = ('len', 'hcp', 'hcp_in', 'top3', 'top5', 'aces', 'shape', 'balanced', 'longest', 'stop')

    def __init__(self, cards):
        ranks = [[], [], [], []]
        for c in cards:
            ranks[3 - int(c) // 13].append(int(c) % 13)
        self.len = [len(r) for r in ranks]
        self.hcp_in = [sum(max(0, r - 8) for r in rs) for rs in ranks]
        self.hcp = sum(self.hcp_in)
        self.top3 = [sum(r >= 10 for r in rs) for rs in ranks]
        self.top5 = [sum(r >= 8 for r in rs) for rs in ranks]
        self.aces = sum(12 in rs for rs in ranks)
        self.shape = tuple(sorted(self.len, reverse=True))
        self.balanced = self.shape in BALANCED
        self.longest = max(SUITS, key=lambda s: (self.len[s], s))          # the higher of equal lengths
        self.stop = [12 in rs or (11 in rs and len(rs) >= 2) or (10 in rs and len(rs) >= 3) or (9 in rs and len(rs) >= 4) for rs in ranks]

    def light(self):
        return self.shape[0] >= 6 or self.shape[1] >= 5

    def support(self, trump):
        """Points as dummy for a suit contract: high cards plus shortness, more with four trumps."""
        scale = (5, 3, 1) if self.len[trump] >= 4 else (3, 2, 1)
        return self.hcp + sum(scale[n] for s, n in enumerate(self.len) if s != trump and n <= 2)

    def playing(self):
        """Points as declarer: high cards plus length beyond four in each suit."""
        return self.hcp + sum(max(0, n - 4) for n in self.len)


class M:
    """What a call shows. hcp and len are public ranges; test is a private condition on the hand."""
    __slots__ = ('hcp', 'len', 'force', 'kind', 'test')

    def __init__(self, hcp=(0, 40), force=0, kind='', test=None, **lengths):
        self.hcp, self.force, self.kind, self.test = hcp, force, kind, test
        self.len = {'CDHS'.index(k): v for k, v in lengths.items()}

    def fits(self, h):
        if not self.hcp[0] <= h.hcp <= self.hcp[1]:
            return False
        for s, (lo, hi) in self.len.items():
            if not lo <= h.len[s] <= hi:
                return False
        return self.test is None or bool(self.test(h))


NOTHING = M()
BAL = dict(C=(2, 5), D=(2, 5), H=(2, 5), S=(2, 5))     # the lengths a balanced no-trump bid shows


class Shown:
    """One seat's public picture so far."""
    __slots__ = ('hcp', 'len')

    def __init__(self):
        self.hcp, self.len = [0, 40], [[0, 13] for _ in SUITS]

    def apply(self, m):
        self.hcp[0], self.hcp[1] = max(self.hcp[0], m.hcp[0]), min(self.hcp[1], m.hcp[1])
        if self.hcp[0] > self.hcp[1]:                   # a call outside the expected range: believe the newer bound
            self.hcp[0] = self.hcp[1] = min(max(m.hcp[0], 0), 40) if m.hcp[0] > self.hcp[1] else self.hcp[1]
        for s, (lo, hi) in m.len.items():
            self.len[s][0], self.len[s][1] = max(self.len[s][0], lo), min(self.len[s][1], hi)
            if self.len[s][0] > self.len[s][1]:
                self.len[s][1] = self.len[s][0]


class State:
    """The public auction: who has shown what, what is forcing, where the contract stands."""

    def __init__(self, dealer, vul, systems):
        self.dealer, self.vul, self.systems = dealer, vul, systems     # systems: (North-South settings, East-West settings)
        self.calls = []                                 # (seat, token, meaning)
        self.shown = [Shown() for _ in range(4)]
        self.acts = [[] for _ in range(4)]              # each seat's calls other than pass: (token, kind)
        self.turns = [0, 0, 0, 0]
        self.last = None                                # (seat, token) of the last bid
        self.doubled = 0
        self.opening = None                             # (seat, token, meaning)
        self.game_force = [False, False]
        self.natural = [set(), set()]                   # strains each side has bid naturally

    def seat(self):
        return (self.dealer + len(self.calls)) % 4

    def vulnerable(self, seat):
        return self.vul == 3 or self.vul == 1 + seat % 2

    def legal(self, token):
        if token == PASS:
            return True
        if token == DOUBLE:
            return self.last is not None and self.doubled == 0 and self.last[0] % 2 != self.seat() % 2
        if token == REDOUBLE:
            return False
        return self.last is None or token > self.last[1]

    def forced(self, me):
        """Must `me` keep the auction open? Partner's last call was forcing and the next hand passed, or the side
        is forced to game and is below it."""
        if len(self.calls) < 2:
            return False
        (ps, pt, pm), (rs, rt, _) = self.calls[-2], self.calls[-1]
        if ps != (me + 2) % 4 or rt >= 5:                # a double or redouble on the right does not lift the force
            return False
        if pm.force == 1:
            return True
        return self.game_force[me % 2] and self.last is not None and not below_game_is_enough(self.last[1])

    def push(self, token):
        seat = self.seat()
        m = explain(self, seat, token)
        self.calls.append((seat, token, m))
        self.turns[seat] += 1
        if token == PASS:
            self.shown[seat].apply(m)
            return
        if token == DOUBLE:
            self.doubled = 1
        elif token == REDOUBLE:
            self.doubled = 2
        else:
            if self.opening is None:
                self.opening = (seat, token, m)
            self.last, self.doubled = (seat, token), 0
            if strain_of(token) != N and m.len.get(strain_of(token), (0, 0))[0] >= 3:
                self.natural[seat % 2].add(strain_of(token))
        self.acts[seat].append((token, m.kind))
        self.shown[seat].apply(m)
        if m.force == 2:
            self.game_force[seat % 2] = True


def below_game_is_enough(token):
    """Is this contract game or higher?"""
    level, strain = level_of(token), strain_of(token)
    return level >= (3 if strain == N else 4 if strain in MAJORS else 5)


# ---- the tables --------------------------------------------------------------------------

def opening_table(st, me, g):
    lo, hi, light = g.open_min, g.top, g.open_light
    seat_no = len(st.calls) + 1
    opens = lambda h: h.hcp >= lo or (h.hcp >= lo - light and h.light())
    t = []
    if g.style == 'precision':
        t.append((bid(1, C), M((g.club_min, 40), force=1, kind='strong')))
        cap = 5 if g.nt_five_major else 4
        t.append((bid(1, N), M((g.nt_lo, g.nt_hi), kind='nt', test=lambda h: h.balanced, C=(2, 5), D=(2, 5), H=(2, cap), S=(2, cap))))
        t.append((bid(1, S), M((lo - light, hi), test=lambda h: opens(h) and h.len[S] >= h.len[H], S=(5, 13))))
        t.append((bid(1, H), M((lo - light, hi), test=opens, H=(5, 13))))
        t.append((bid(2, C), M((lo, hi), kind='clubs', C=(g.two_clubs_len, 13), H=(0, 4), S=(0, 4))))
        if g.two_diamonds:
            t.append((bid(2, D), M((lo, hi), kind='three-suiter', D=(0, 1), C=(4, 5), H=(3, 4), S=(3, 4))))
        t.append((bid(1, D), M((lo - light, hi), test=lambda h: opens(h) and not (h.len[C] >= g.two_clubs_len and h.len[C] > h.len[D]),
                               D=(1, 13), H=(0, 4), S=(0, 4))))
    else:
        t.append((bid(2, C), M((22, 40), force=2, kind='strong')))
        t.append((bid(2, N), M((20, 21), kind='nt', test=lambda h: h.balanced, C=(2, 5), D=(2, 5), H=(2, 5), S=(2, 5))))
        cap = 5 if g.nt_five_major else 4
        t.append((bid(1, N), M((g.nt_lo, g.nt_hi), kind='nt', test=lambda h: h.balanced, C=(2, 5), D=(2, 5), H=(2, cap), S=(2, cap))))
        t.append((bid(1, S), M((lo - light, hi), test=lambda h: opens(h) and h.len[S] >= h.len[H], S=(5, 13))))
        t.append((bid(1, H), M((lo - light, hi), test=opens, H=(5, 13))))
        t.append((bid(1, D), M((lo - light, hi), test=lambda h: opens(h) and (h.len[D] > h.len[C] or h.len[D] == h.len[C] >= 4), D=(3, 13), H=(0, 4), S=(0, 4))))
        t.append((bid(1, C), M((lo - light, hi), test=opens, C=(3, 13), H=(0, 4), S=(0, 4))))
    if seat_no <= 3:
        weak = (g.weak_lo, g.weak_hi)
        twos = (S, H) if g.style == 'precision' else (S, H, D)
        for s in twos:
            t.append((bid(2, s), M(weak, kind='preempt', test=lambda h, s=s: h.top5[s] >= g.weak_quality, **{'CDHS'[s]: (6, 6)})))
        for s in (S, H):
            t.append((bid(4, s), M((g.weak_lo, 12), kind='preempt', test=lambda h, s=s: h.top5[s] >= g.weak_quality, **{'CDHS'[s]: (8, 13)})))
        for s in (S, H, D, C):
            t.append((bid(3, s), M((max(0, g.weak_lo - 1), g.weak_hi), kind='preempt', test=lambda h, s=s: h.top5[s] >= g.weak_quality,
                                   **{'CDHS'[s]: (g.preempt_len, 13)})))
    t.append((PASS, M((0, max(lo, g.weak_hi + 1)))))
    return t


def nt_responses(st, me, g, base, lo, hi):
    """Responses to a no-trump bid at level `base` showing lo..hi balanced."""
    game, invite = g.game - lo, g.game - hi             # points for game opposite a minimum, and to invite
    if base >= 2:
        game = g.game - (lo + hi) // 2                   # no room to ask: go by the middle of the range
    t = [(bid(6, N), M((g.slam - lo, 40), test=lambda h: h.balanced))]
    if g.transfers:
        t.append((bid(base + 1, H), M((0, 40), force=1, kind='transfer', S=(5, 13), test=lambda h: h.len[S] >= h.len[H])))
        t.append((bid(base + 1, D), M((0, 40), force=1, kind='transfer', H=(5, 13))))
    if g.stayman:
        t.append((bid(base + 1, C), M((invite if base == 1 else game, 40), force=1, kind='stayman', test=lambda h: max(h.len[H], h.len[S]) == 4)))
    t.append((bid(3, N), M((game, 40), kind='signoff')))
    if base == 1:
        t.append((bid(2, N), M((invite, game - 1), kind='invite')))
    t.append((PASS, M((0, max(0, invite - 1 if base == 1 else game - 1)))))
    return t


def response_table(st, me, g):
    """First response to partner's opening when the next hand passed or doubled."""
    seat, token, om = st.opening
    lvl, s = level_of(token), strain_of(token)
    plo, phi = st.shown[seat].hcp
    game = g.game - plo                                 # points for game opposite a minimum
    t = []
    if om.kind == 'strong' and lvl == 1:                # precision 1C
        t.append((bid(1, S), M((g.neg_max + 1, 40), force=2, S=(5, 13), test=lambda h: h.len[S] >= h.len[H])))
        t.append((bid(1, H), M((g.neg_max + 1, 40), force=2, H=(5, 13))))
        t.append((bid(2, D), M((g.neg_max + 1, 40), force=2, D=(5, 13), test=lambda h: h.len[D] >= h.len[C])))
        t.append((bid(2, C), M((g.neg_max + 1, 40), force=2, C=(5, 13))))
        t.append((bid(2, N), M((14, 40), force=2, kind='nt')))
        t.append((bid(1, N), M((g.neg_max + 1, 13), force=2, kind='nt')))
        t.append((bid(1, D), M((0, g.neg_max), force=1, kind='negative')))
        return t
    if om.kind == 'strong':                             # standard 2C
        for x in (S, H):
            t.append((bid(2, x), M((8, 40), force=2, test=lambda h, x=x: h.top3[x] >= 2, **{'CDHS'[x]: (5, 13)})))
        t.append((bid(2, D), M((0, 40), force=2, kind='negative')))
        return t
    if om.kind == 'nt':
        return nt_responses(st, me, g, lvl, plo, phi)
    if om.kind == 'preempt':
        if s in MAJORS:
            t.append((bid(4, s), M((0, 40), kind='signoff', test=lambda h: h.support(s) >= 16 or h.len[s] >= 4, **{'CDHS'[s]: (2, 13)})))
        t.append((bid(3, N), M((17, 40), kind='signoff', test=lambda h: h.len[s] >= 2 and sum(h.stop) >= 3)))
        if lvl == 2:
            t.append((bid(3, s), M((0, 13), kind='preempt', **{'CDHS'[s]: (3, 13)})))
        t.append((PASS, M((0, 16))))
        return t
    if om.kind == 'three-suiter':                       # precision 2D: place the contract
        t.append((bid(4, S), M((game, 40), kind='signoff', S=(4, 13), test=lambda h: h.len[S] >= h.len[H])))
        t.append((bid(4, H), M((game, 40), kind='signoff', H=(4, 13))))
        t.append((bid(3, N), M((game + 1, 40), kind='signoff', test=lambda h: h.stop[D])))
        t.append((bid(2, N), M((game - 2, game), kind='invite', test=lambda h: h.stop[D] and max(h.len[H], h.len[S]) < 4)))
        t.append((bid(3, S), M((game - 3, game - 1), kind='invite', S=(4, 13), test=lambda h: h.len[S] >= h.len[H])))
        t.append((bid(3, H), M((game - 3, game - 1), kind='invite', H=(4, 13))))
        t.append((PASS, M((0, game - 1), D=(6, 13))))
        t.append((bid(2, S), M((0, game - 1), kind='signoff', S=(3, 13), test=lambda h: h.len[S] >= h.len[H])))
        t.append((bid(2, H), M((0, game - 1), kind='signoff', H=(3, 13))))
        t.append((bid(3, C), M((0, game - 1), kind='signoff')))
        return t
    if om.kind == 'clubs':                              # precision 2C
        t.append((bid(3, N), M((game, 40), kind='signoff', test=lambda h: h.balanced)))
        t.append((bid(2, D), M((game - 3, 40), force=1, kind='ask')))
        t.append((bid(2, S), M((8, game - 4), S=(5, 13), test=lambda h: h.len[S] >= h.len[H])))
        t.append((bid(2, H), M((8, game - 4), H=(5, 13))))
        t.append((bid(3, C), M((6, game - 4), kind='preempt', C=(3, 13))))
        t.append((PASS, M((0, game - 4))))
        return t
    if lvl != 1 or s == N:                              # an opening the tables do not define: the general procedure
        return []
    # a one-level suit opening, limited (precision) or wide (standard)
    if s in MAJORS:
        fit = lambda h: h.len[s] >= 3
        t.append((bid(4, s), M((0, 9), kind='preempt', test=lambda h: h.len[s] >= 5 and h.shape[3] <= 1, **{'CDHS'[s]: (3, 13)})))
        t.append((bid(4, s), M((0, 40), kind='signoff', test=lambda h: fit(h) and h.support(s) >= game and h.support(s) < g.slam - phi, **{'CDHS'[s]: (3, 13)})))
        t.append((bid(3, s), M((game - 8, game - 1), kind='invite', test=lambda h: game - 3 <= h.support(s) < game, **{'CDHS'[s]: (4, 13)})))
        if s == H:
            t.append((bid(1, S), M((g.resp_min, 40), force=1, S=(4, 13), test=lambda h: not (fit(h) and h.support(s) < game - 3) or h.len[S] >= 5)))
        t.append((bid(2, s), M((g.resp_min - 1, game - 4), test=lambda h: g.resp_min <= h.support(s) < game - 3 or (g.resp_min <= h.support(s) < game and h.len[s] == 3), **{'CDHS'[s]: (3, 13)})))
        gf = 2 if g.two_over_one >= 12 else 1           # a two-over-one on twelve or more is forcing to game
        for x in (D, C):
            t.append((bid(2, x), M((g.two_over_one, 40), force=gf, **{'CDHS'[x]: (4, 13)}, test=lambda h, x=x: h.len[x] >= 5 or h.len[x] == h.shape[0])))
        if s == S:
            t.append((bid(2, H), M((g.two_over_one, 40), force=gf, H=(5, 13))))
        t.append((bid(3, N), M((game, game + 3), kind='signoff', test=lambda h: h.balanced and not fit(h))))
        t.append((bid(2, N), M((game - 3, game - 1), kind='invite', test=lambda h: h.balanced and not fit(h))))
        t.append((bid(1, N), M((g.resp_min, g.two_over_one), kind='nt-response')))
        t.append((PASS, M((0, g.resp_min - 1))))
        return t
    # a one-level minor opening (precision 1D may be short)
    real = st.shown[seat].len[s][0]
    t.append((bid(1, H), M((g.resp_min, 40), force=1, H=(4, 13), test=lambda h: h.len[H] >= h.len[S] or h.len[S] < 4 or (h.len[H] == 4 and h.len[S] == 4))))
    t.append((bid(1, S), M((g.resp_min, 40), force=1, S=(4, 13))))
    t.append((bid(3, N), M((game, game + 3), kind='signoff', test=lambda h: h.balanced)))
    t.append((bid(2, N), M((game - 3, game - 1), kind='invite', test=lambda h: h.balanced)))
    other = C if s == D else D
    if other == C or True:
        t.append((bid(2, C) if s == D else bid(1, D), M((g.two_over_one if s == D else g.resp_min, 40), force=1,
                                                         **{'CDHS'[other]: (5 if s == D else 4, 13)})))
    need = max(3, 8 - real)
    t.append((bid(3, s), M((game - 4, game - 1), kind='invite', **{'CDHS'[s]: (need, 13)})))
    t.append((bid(2, s), M((g.resp_min, game - 4), **{'CDHS'[s]: (need, 13)})))
    t.append((bid(1, N), M((g.resp_min, max(g.resp_min + 3, game - 5)), kind='nt-response')))
    t.append((PASS, M((0, g.resp_min - 1))))
    return t


def competitive_response_table(st, me, g):
    """First response to partner's opening after an overcall on the right."""
    seat, token, om = st.opening
    s = strain_of(token)
    theirs = strain_of(st.last[1])
    over = st.last[1]
    plo, phi = st.shown[seat].hcp
    game = g.game - plo
    cheapest = lambda x: next((bid(l, x) for l in range(1, 8) if bid(l, x) > over), None)
    t = []
    strong = om.kind == 'strong'
    if strong:
        for x in (S, H, D, C):
            if x != theirs and cheapest(x) and level_of(cheapest(x)) <= 3:
                t.append((cheapest(x), M((g.neg_max + 1, 40), force=2, **{'CDHS'[x]: (5, 13)}, test=lambda h, x=x: h.len[x] == h.shape[0])))
        if theirs != N and cheapest(N) and level_of(cheapest(N)) <= 2:
            t.append((cheapest(N), M((g.neg_max + 1, 40), force=2, kind='nt', test=lambda h: h.stop[theirs])))
        t.append((DOUBLE, M((max(0, g.neg_max - 2), 40), force=1, kind='values')))
        t.append((PASS, M((0, g.neg_max))))
        return t
    natural = s != N and st.shown[seat].len[s][0] >= 3
    if natural and s in MAJORS:
        if bid(4, s) > over:
            t.append((bid(4, s), M((0, 40), kind='signoff', test=lambda h: h.len[s] + st.shown[seat].len[s][0] >= 10, **{'CDHS'[s]: (3, 13)})))
            t.append((bid(4, s), M((0, 40), kind='signoff', test=lambda h: h.support(s) >= game, **{'CDHS'[s]: (3, 13)})))
        if bid(3, s) > over:
            t.append((bid(3, s), M((game - 8, game - 1), kind='invite', test=lambda h: h.support(s) >= game - 4, **{'CDHS'[s]: (4, 13)})))
        if bid(2, s) > over:
            t.append((bid(2, s), M((g.resp_min - 2, game - 2), test=lambda h: h.support(s) >= g.resp_min, **{'CDHS'[s]: (3, 13)})))
    if theirs != N:
        for level, rng in ((3, (game, game + 4)), (2, (game - 3, game - 1)), (1, (g.resp_min + 1, game - 4))):
            if bid(level, N) > over and level_of(over) <= level:
                t.append((bid(level, N), M(rng, kind='signoff' if level == 3 else 'invite' if level == 2 else 'nt-response',
                                           test=lambda h: h.stop[theirs] and h.shape[3] >= 2 and h.shape[0] <= 6)))
    for x in (S, H, D, C):                              # a suit of one's own with values comes before the double
        c = cheapest(x)
        if x not in (s, theirs) and c and level_of(c) <= 2:
            t.append((c, M((g.resp_min + 2 if level_of(c) == 1 else g.two_over_one - 1, 40), force=1, **{'CDHS'[x]: (5, 13)})))
    if om.kind in ('', 'clubs') and level_of(over) <= 2 and theirs != N:
        unbid = [x for x in MAJORS if x not in (s, theirs)]
        if unbid:
            t.append((DOUBLE, M((g.resp_min + 1, 40), force=1, kind='takeout', **{'CDHS'[x]: (4, 13) for x in unbid})))
    if natural and s in MINORS and cheapest(s) and level_of(cheapest(s)) <= 3:
        t.append((cheapest(s), M((g.resp_min, game - 2), **{'CDHS'[s]: (max(4, 8 - st.shown[seat].len[s][0]), 13)})))
    if not natural and s in MINORS and om.kind == '' and cheapest(s) and level_of(cheapest(s)) <= 3:      # a short minor opening: real length raises it
        t.append((cheapest(s), M((g.resp_min - 1, game - 2), **{'CDHS'[s]: (5 if level_of(cheapest(s)) <= 2 else 6, 13)})))
    for x in (S, H, D, C):                              # a long suit of one's own, to play
        c = cheapest(x)
        if x not in (s, theirs) and c and level_of(c) <= 3:
            t.append((c, M((4, g.two_over_one - 2), kind='signoff', **{'CDHS'[x]: (6 if level_of(c) <= 2 else 7, 13)})))
    t.append((PASS, M((0, max(game - 1, g.resp_min + 3)))))
    return t


def rebid_table(st, me, g):
    """The opener's second call: forced replies and the strong-club rebids. Everything else is general."""
    token, _ = st.acts[me][0]
    partner = (me + 2) % 4
    if not st.acts[partner]:
        return []
    ptoken, pkind = st.acts[partner][-1]
    base = level_of(token)
    t = []
    if pkind == 'negative' and st.acts[me][0][1] == 'strong' and base == 1:        # 1C - 1D
        top = g.club_min + 5
        t.append((bid(3, N), M((g.club_min + 7, 40), kind='signoff', test=lambda h: h.balanced, **BAL)))
        t.append((bid(2, N), M((g.club_min + 4, g.club_min + 6), kind='nt', test=lambda h: h.balanced, **BAL)))
        t.append((bid(1, N), M((g.club_min, g.club_min + 3), kind='nt', test=lambda h: h.balanced, **BAL)))
        for x in (S, H):
            t.append((bid(2, x), M((top + 1, 40), force=1, **{'CDHS'[x]: (5, 13)}, test=lambda h, x=x: h.len[x] == h.shape[0])))
        t.append((bid(1, S), M((g.club_min, top), S=(5, 13), test=lambda h: h.len[S] >= h.len[H])))
        t.append((bid(1, H), M((g.club_min, top), H=(5, 13))))
        t.append((bid(3, D), M((top + 1, 40), force=1, D=(5, 13))))
        t.append((bid(3, C), M((top + 1, 40), force=1, C=(5, 13))))
        t.append((bid(2, D), M((g.club_min, top), D=(5, 13), test=lambda h: h.len[D] >= h.len[C])))
        t.append((bid(2, C), M((g.club_min, top), C=(5, 13))))
        t.append((bid(1, S), M((g.club_min, top), S=(4, 13))))
        t.append((bid(1, H), M((g.club_min, top), H=(4, 13))))
        t.append((bid(1, N), M((g.club_min, g.club_min + 3), kind='nt')))
        return t
    if pkind == 'ask' and st.acts[me][0][1] == 'clubs':                              # precision 2C - 2D
        mid = (g.open_min + g.top) // 2
        t.append((bid(2, H), M(H=(4, 4))))
        t.append((bid(2, S), M(S=(4, 4))))
        t.append((bid(2, N), M((mid + 1, g.top), kind='nt')))
        t.append((bid(3, C), M((g.open_min, mid))))
        return t
    return t


def defensive_table(st, me, g):
    """First action over the opponents' opening when our side has not yet bid."""
    seat, token, om = st.opening
    over = st.last[1]
    lvl, their = level_of(over), strain_of(token)
    suits = [strain_of(tok) for s2, tok, m in st.calls if tok >= 5 and s2 % 2 != me % 2 and m.len.get(strain_of(tok), (0, 0))[0] >= 3]
    balancing = len(st.calls) >= 2 and st.calls[-1][1] == PASS and st.calls[-2][1] == PASS
    late = sum(1 for s2, tok, _ in st.calls if tok >= 5) >= 2 and not balancing
    b = g.balance if balancing else (-2 if late else 0)
    cheapest = lambda x: next((bid(l, x) for l in range(1, 8) if bid(l, x) > over), None)
    short = lambda h: all(h.len[x] <= 2 for x in suits) and all(h.len[x] >= 3 for x in SUITS if x not in suits) if suits else h.balanced
    t = []
    if om.kind == 'nt' and level_of(token) == 1:
        t.append((DOUBLE, M((max(16, st.shown[seat].hcp[1]) - b, 40), kind='penalty')))
        for x in (S, H, D, C):
            t.append((bid(2, x), M((9 - b, 15), **{'CDHS'[x]: (6, 13)}, test=lambda h, x=x: h.top5[x] >= g.overcall_quality)))
        t.append((PASS, M((0, 17))))
        return t
    if lvl <= 1 and (not suits or all(h_ != N for h_ in suits)):
        stops = lambda h: all(h.stop[x] for x in suits) if suits else True
        c = cheapest(N)
        if c and level_of(c) == 1:
            t.append((c, M((g.nt_overcall_lo - b, g.nt_overcall_hi - b), kind='nt', test=lambda h: h.balanced and stops(h), **BAL)))
    if lvl == 2 and om.kind == 'preempt' and over == token and their != N:      # over a weak two: a strong no-trump
        t.append((bid(2, N), M((g.nt_overcall_lo - b, g.nt_overcall_hi + 1 - b), kind='nt',
                               test=lambda h: h.shape[0] <= 5 and h.shape[3] >= 2 and h.stop[their] and not short(h), **BAL)))
    if lvl <= 3 and om.kind != 'nt':
        need = g.takeout_min - b + 2 * max(0, lvl - 2)
        t.append((DOUBLE, M((max(g.overcall_max + 1, g.takeout_min + 6) - (1 if balancing else 0), 40), force=1, kind='takeout')))
    for x in (S, H, None, D, C):
        if x is None:                                    # the shape double comes before an overcall in a minor
            if lvl <= 3 and om.kind != 'nt':
                t.append((DOUBLE, M((g.takeout_min - b + 2 * max(0, lvl - 2), 40), force=1, kind='takeout', test=short)))
            continue
        if x in suits:
            continue
        c = cheapest(x)
        if not c or level_of(c) > 3:
            continue
        need = (g.overcall_min1 if level_of(c) == 1 else g.overcall_min2 if level_of(c) == 2 else g.overcall_min2 + 2) - b
        quality = lambda h, x=x: h.top5[x] >= g.overcall_quality
        sound = lambda h, x=x, lv=level_of(c), need=need: h.top5[x] >= g.overcall_quality and (
            lv < 3 or h.len[x] >= 6 or (h.top3[x] >= 2 and h.hcp >= need + 2))       # at the three level: six cards, or a good five and extras
        if g.jump_overcalls and not balancing and lvl <= 1 and level_of(c) == 1:
            t.append((bid(3, x), M((g.weak_lo, g.weak_hi), kind='preempt', test=quality, **{'CDHS'[x]: (g.preempt_len, 13)})))
        if g.jump_overcalls and not balancing and bid(level_of(c) + 1, x) > over and level_of(c) + 1 <= 3 and lvl <= 1:
            t.append((bid(level_of(c) + 1, x), M((g.weak_lo, g.weak_hi), kind='preempt', test=quality,
                                                 **{'CDHS'[x]: (6 if level_of(c) + 1 == 2 else g.preempt_len, 13)})))
        t.append((c, M((need, g.overcall_max), kind='overcall', test=sound, **{'CDHS'[x]: (5, 13)})))
    t.append((PASS, M((0, g.takeout_min + 5))))
    return t


def advance_table(st, me, g):
    """First action after partner's overcall or takeout double."""
    partner = (me + 2) % 4
    ptoken, pkind = st.acts[partner][-1]
    plo, phi = st.shown[partner].hcp
    game = g.game - plo
    over = st.last[1]
    rho_passed = st.calls[-1][1] == PASS
    theirs = [x for x in SUITS if x in st.natural[1 - me % 2]]
    cheapest = lambda x: next((bid(l, x) for l in range(1, 8) if bid(l, x) > over), None)
    stops = lambda h: all(h.stop[x] for x in theirs)
    t = []
    if pkind == 'nt' and rho_passed:
        return nt_responses(st, me, g, level_of(ptoken), plo, phi)
    if pkind == 'takeout':
        best = lambda h: max((x for x in SUITS if x not in theirs), key=lambda x: (h.len[x] + (x in MAJORS) * 0.5, x))
        pts = lambda h: h.hcp + max(0, h.len[best(h)] - 4) + sum(1 for x in theirs if h.len[x] <= 1)
        shift = max(0, g.takeout_min - plo)             # a double in the pass-out seat is lighter
        if rho_passed and st.doubled == 1 and strain_of(over) != N:
            ts, lv = strain_of(over), level_of(over)
            t.append((PASS, M(kind='penalty-pass', test=lambda h: h.top5[ts] >= 3 and (lv >= 2 or h.len[ts] >= 6), **{'CDHS'[ts]: (5, 13)})))
        for x in MAJORS:
            if x not in theirs and bid(4, x) > over:
                t.append((bid(4, x), M((10 + shift, 40), kind='signoff', test=lambda h, x=x: best(h) == x and pts(h) >= 12 + shift, **{'CDHS'[x]: (4, 13)})))
        if bid(3, N) > over:
            t.append((bid(3, N), M((12 + shift, 40), kind='signoff', test=stops)))
        for x in (S, H, D, C):
            c = cheapest(x)
            if x in theirs or not c:
                continue
            if bid(level_of(c) + 1, x) > over and level_of(c) + 1 <= 3:
                t.append((bid(level_of(c) + 1, x), M((7 + shift, 11 + shift), kind='invite', test=lambda h, x=x: best(h) == x and 9 + shift <= pts(h),
                                                     **{'CDHS'[x]: (4, 13)})))
        c = cheapest(N)
        if c and level_of(c) <= 2 and theirs:
            t.append((c, M((6 + shift, 11 + shift), kind='nt-response', test=lambda h: stops(h) and max(h.len[H], h.len[S]) < 4)))
        if rho_passed:
            for x in (S, H, D, C):
                c = cheapest(x)
                if x not in theirs and c:
                    t.append((c, M((0, 9 + shift), test=lambda h, x=x: best(h) == x, **{'CDHS'[x]: (3, 13)})))
        else:
            for x in (S, H, D, C):
                c = cheapest(x)
                if x not in theirs and c and level_of(c) <= 3:
                    t.append((c, M((5 + shift, 9 + shift), test=lambda h, x=x: best(h) == x and h.len[x] >= 4, **{'CDHS'[x]: (4, 13)})))
            t.append((PASS, M((0, 8 + shift))))
        return t
    if pkind in ('overcall', 'preempt'):
        s = strain_of(ptoken)
        need = max(2, 8 - st.shown[partner].len[s][0])
        if s in MAJORS and bid(4, s) > over:
            t.append((bid(4, s), M((0, 40), kind='signoff', test=lambda h: h.support(s) >= game or h.len[s] >= need + 2
                                    or (h.len[s] >= need + 1 and h.support(s) >= game - 4), **{'CDHS'[s]: (need, 13)})))
        if bid(3, N) > over and pkind == 'overcall':
            t.append((bid(3, N), M((game + 1, 40), kind='signoff', test=stops)))
        c = cheapest(s)
        if c and level_of(c) <= 3:
            if bid(level_of(c) + 1, s) > over and level_of(c) + 1 <= 3 and pkind == 'overcall':
                t.append((bid(level_of(c) + 1, s), M((game - 7, game - 1), kind='invite', test=lambda h: h.support(s) >= game - 5, **{'CDHS'[s]: (need, 13)})))
                t.append((bid(level_of(c) + 1, s), M((3, game - 6), kind='preempt', test=lambda h: h.support(s) >= 7, **{'CDHS'[s]: (need + 1, 13)})))
            t.append((c, M((4, game - 4), test=lambda h: 6 <= h.support(s) < game - 5, **{'CDHS'[s]: (need, 13)})))
            t.append((c, M((4, game - 1), test=lambda h: h.support(s) >= 6, **{'CDHS'[s]: (need, 13)})))
        if pkind == 'overcall':
            cn = cheapest(N)
            if cn and level_of(cn) <= 2 and theirs:
                t.append((cn, M((game - 5, game - 1), kind='nt-response', test=lambda h: stops(h) and h.shape[3] >= 2 and h.shape[0] <= 6)))
            for x in (S, H, D, C):
                c2 = cheapest(x)
                if x != s and x not in theirs and c2 and level_of(c2) <= 2:
                    t.append((c2, M((game - 6, 40), force=1, **{'CDHS'[x]: (5, 13)}, test=lambda h, x=x: h.top5[x] >= 2)))
        t.append((PASS, M((0, max(game - 1, 9)))))
        return t
    return t


def table_for(st, me):
    """The defined calls in this situation, in order of preference, or [] when only the general procedure applies."""
    g = st.systems[me % 2]
    if st.opening is None:
        return opening_table(st, me, g)
    opener = st.opening[0]
    partner = (me + 2) % 4
    mine, theirs_acted = st.acts[me], any(st.acts[x] for x in ((me + 1) % 4, (me + 3) % 4))
    if opener == partner and not mine and st.turns[partner] >= 1 and len(st.acts[partner]) == 1:
        last_seat, last_tok, _ = st.calls[-1]
        if last_tok in (PASS, DOUBLE) and st.last[0] == partner:
            return response_table(st, me, g)
        if last_tok >= 5 and st.last[0] == (me + 3) % 4 and not st.acts[(me + 1) % 4]:
            return competitive_response_table(st, me, g)
        return []
    if mine and st.acts[partner] and st.acts[partner][-1][1] in ('stayman', 'transfer') and st.calls[-1][1] == PASS \
            and st.calls[-2][0] == partner and strain_of(mine[-1][0]) == N:
        ptoken, pkind = st.acts[partner][-1]
        if pkind == 'transfer':
            m, lv, top = (H if strain_of(ptoken) == D else S), level_of(ptoken), st.shown[me].hcp[1]
            return [(bid(lv + 1, m), M(test=lambda h: h.len[m] >= 4 and h.hcp >= top - 1, **{'CDHS'[m]: (4, 5)})), (bid(lv, m), NOTHING)]
        return [(bid(level_of(ptoken), H), M(H=(4, 5))), (bid(level_of(ptoken), S), M(S=(4, 5), H=(2, 3))), (bid(level_of(ptoken), D), M(H=(2, 3), S=(2, 3)))]
    if st.acts[partner] and st.acts[partner][-1][1] == 'nt' and st.calls[-1][1] == PASS and st.last == (partner, st.acts[partner][-1][0]) \
            and level_of(st.last[1]) <= 2 and all(k == 'negative' for _, k in mine):
        lo, hi = st.shown[partner].hcp
        return nt_responses(st, me, g, level_of(st.last[1]), lo, min(hi, lo + 5))
    if opener == me and len(mine) == 1 and st.calls[-1][1] == PASS:
        return rebid_table(st, me, g)
    if opener % 2 != me % 2 and not mine and not st.acts[partner]:
        return defensive_table(st, me, g)
    if opener % 2 != me % 2 and not mine and len(st.acts[partner]) == 1:
        return advance_table(st, me, g)
    return []


# ---- the general procedure ---------------------------------------------------------------

def middle2(ps):
    """Twice the points partner is taken to hold: the middle of what it has shown. A wide-open hand is taken two
    above its minimum: with much more it acts itself, so the hands that leave the decision here are the lower ones."""
    lo, hi = ps.hcp
    return 2 * lo + (4 if hi - lo > 10 else min(hi - lo, 6))


def invite_floor(g, ps):
    """The fewest points on which the general procedure invites game opposite `ps`."""
    return (2 * g.game - 2 - g.invite_width - middle2(ps) + 1) // 2


def plan(h, st, me):
    """What the general procedure wants: (token, kind)."""
    g = st.systems[me % 2]
    partner = (me + 2) % 4
    ps, my = st.shown[partner], st.shown[me]
    plo, phi = ps.hcp[0], min(ps.hcp[1], ps.hcp[0] + 10)      # an unlimited hand is taken as within ten of its minimum
    mid2 = middle2(ps)
    over = st.last[1]
    ours = st.last[0] % 2 == me % 2
    level, strain = level_of(over), strain_of(over)
    enemy = st.natural[1 - me % 2]
    side_gf = st.game_force[me % 2]
    cheapest = lambda x: next((bid(l, x) for l in range(1, 8) if bid(l, x) > over), None)
    trumps = lambda x: h.len[x] + ps.len[x][0]
    # the best trump fit known from this hand and partner's shown lengths; a long suit of one's own counts
    theirs_long = [x for x in MAJORS if ps.len[x][0] >= 6 and h.len[x] >= 1 and x not in enemy]      # partner's six-card major: one card is support
    fits = [x for x in SUITS if x not in enemy and (trumps(x) >= 8 or x in theirs_long or (not theirs_long and (
        h.len[x] >= 7 or (h.len[x] >= 6 and x in MAJORS and ps.len[x][1] >= 1))))]
    fit = max(fits, key=lambda x: (x in MAJORS, trumps(x), x)) if fits else None
    if fit is None:
        points = h.hcp + max(0, h.shape[0] - 5)
    elif ps.len[fit][0] >= max(4, h.len[fit]):
        points = h.support(fit)
    else:
        points = h.playing() + sum(1 for x in SUITS if x != fit and h.len[x] <= 1)
    if fit is not None:
        points += max(0, min(trumps(fit), h.len[fit] + 4) - 8)
    cmin, cmax = points + plo, points + phi
    pact = st.acts[partner][-1] if st.acts[partner] else (None, '')
    partner_nt = (pact[0] is not None and pact[0] >= 5 and strain_of(pact[0]) == N) or any(k == 'nt' for _, k in st.acts[partner])
    stoppers = partner_nt or (h.shape[3] >= 2 and all(h.stop[x] or ps.len[x][0] >= 4 for x in enemy))
    forced = st.forced(me)
    rho_passed = st.calls[-1][1] == PASS
    invited = pact[1] == 'invite' and rho_passed
    slam_invited = pact[1] == 'slam-invite' and rho_passed
    if invited and fit is None and any(ps.len[x][0] >= 6 and h.len[x] <= 1 for x in SUITS):
        points -= 2                                      # asked, and short in partner's long suit
        cmin, cmax = cmin - 2, cmax - 2

    def game_token():
        if fit in MAJORS:
            return bid(4, fit)
        if stoppers and (fit is None or h.balanced or h.len[fit] <= 5):
            return bid(3, N)
        if fit is not None:
            return bid(5, fit) if cmin >= g.game_minor - 1 else bid(3, N) if stoppers else bid(4, fit)
        return bid(3, N) if stoppers else None

    # ---- slam ----
    slam_strain = fit if fit is not None else N
    if slam_invited:
        if 2 * points + mid2 >= 2 * g.slam and bid(6, slam_strain) > over:
            return bid(6, slam_strain), 'signoff'
        if ours and strain == N:
            return PASS, ''
    if cmin >= g.slam and h.aces >= 1 and (fit is not None or h.balanced) and level < 6:
        want = bid(7 if cmin >= g.grand and h.aces >= 2 else 6, slam_strain)
        if want > over:
            return want, 'signoff'
    if cmin >= g.slam - 2 and cmax >= g.slam + 1 and h.aces >= 1 and (fit is None or fit in MINORS) and h.shape[0] <= 5 and bid(4, N) > over \
            and not slam_invited and pact[1] != 'signoff':
        return bid(4, N), 'slam-invite'
    target = game_token()
    if target == bid(3, N) and fit is not None:          # no trump with a minor fit: shortness is not worth points there
        points = h.hcp + max(0, h.shape[0] - 5)
        cmin, cmax = points + plo, points + phi
    need = g.game_minor if target is not None and level_of(target) == 5 else g.game
    in_game = ours and below_game_is_enough(over)
    if pact[0] == bid(3, N) and ours and rho_passed and any(k == 'transfer' for _, k in st.acts[partner]):
        for m in MAJORS:                                 # partner transferred and offered three no-trump: three cards make the major better
            if ps.len[m][0] >= 5 and h.len[m] >= 3 and bid(4, m) > over:
                return bid(4, m), 'signoff'
    if pact[1] == 'signoff' and ours and rho_passed and not forced and cmin < g.slam - 2:
        return PASS, ''                                  # partner placed the contract
    if pact[1] == 'choice' and rho_passed and ours:      # partner showed five of a major over our no-trump: choose the game
        m = strain_of(pact[0])
        go = bid(4, m) if h.len[m] >= 3 else bid(3, N)
        if go > over:
            return go, 'signoff'
    narrow = my.hcp[1] - my.hcp[0] <= 6 and 2 * h.hcp > my.hcp[0] + my.hcp[1]             # the top half of what this hand has shown
    accept = cmin >= need or (invited and (narrow or 2 * points + mid2 >= 2 * need))
    over_2nt = partner_nt and ours and strain == N and level == 2 and st.last[0] == partner and rho_passed
    if over_2nt and accept and pact[1] != 'signoff' and fit not in MAJORS:
        for m in (S, H):
            if h.len[m] >= 5 and my.len[m][0] < 5 and ps.len[m][1] >= 3 and bid(3, m) > over:
                return bid(3, m), 'choice'
    # ---- partner asked, or doubled for takeout ----
    if invited:
        if (narrow or 2 * points + mid2 >= 2 * need) and target is not None and target > over:
            return target, 'signoff'
        if ours:
            return PASS, ''
    if pact[1] == 'takeout' and pact[0] == DOUBLE and not ours and ((st.doubled == 1 and rho_passed) or (st.doubled == 2 and st.calls[-1][1] == REDOUBLE)):
        suit = max((x for x in SUITS if x not in enemy), key=lambda x: (h.len[x] + (x in MAJORS) * 0.5, x))
        if fit in MAJORS and h.len[fit] >= 4:
            suit = fit                                   # partner has shown four of this major
        if strain != N and h.len[strain] >= 5 and h.top5[strain] >= 3:
            return PASS, ''                              # their suit is ours: leave the double in
        if cmin >= need and suit in MAJORS and h.len[suit] >= 4 and bid(4, suit) > over:
            return bid(4, suit), 'signoff'
        c = cheapest(suit)
        if c is not None and level_of(c) <= 4:
            return c, ''
    # ---- a game-forcing auction below game: describe before placing ----
    if side_gf and not in_game and level <= 2 and rho_passed and fit not in MAJORS:
        for x in (S, H, D, C):
            c = cheapest(x)
            if c is not None and level_of(c) <= 3 and x not in enemy and h.len[x] >= 5 and my.len[x][0] < 5 and ps.len[x][0] < 3:
                return c, ''
        for x in MAJORS:
            c = cheapest(x)
            if c is not None and level_of(c) <= 2 and x not in enemy and h.len[x] == 4 and my.len[x][0] < 4 and ps.len[x][1] >= 4:
                return c, ''
    if level == 1 and rho_passed and ours and not in_game and fit not in MAJORS and cmax >= need - 4:
        for x in MAJORS:
            if bid(1, x) > over and x not in enemy and h.len[x] >= 4 and my.len[x][0] < 4 and ps.len[x][1] >= 4:
                return bid(1, x), ''
    if rho_passed and ours and level <= 2 and not in_game and cmin >= need - 4 and fit not in MAJORS and not invited:
        for x in MAJORS:
            if h.len[x] >= 5 and 4 <= my.len[x][0] < 5 and ps.len[x][1] >= 3 and bid(2, x) > over and x not in enemy:
                return bid(2, x), ''
    # ---- game, or an invitation ----
    width = phi - plo
    if cmin >= need or (side_gf and not in_game and rho_passed):
        if in_game and (strain == N or strain == fit or fit is None):
            return PASS, ''
        if target is not None and target > over:
            return target, 'signoff'
        if in_game:
            return PASS, ''
    elif cmax >= need and 2 * points + mid2 >= 2 * need - 2 - g.invite_width and not in_game and not invited:
        inv = bid(3, fit) if fit in MAJORS else bid(2, N) if stoppers and fit is None else bid(3, fit) if fit is not None else None
        if over_2nt and inv is not None and strain_of(inv) in MAJORS:
            inv = None                                   # three of a major over two no-trump is the forcing choice of games
        if inv is not None and level_of(inv) == 3 and not is_invitation(st, me, inv):
            inv = None                                   # it would be read as a preference or as competing, not as an invitation
        if inv is not None and inv > over and not (ours and strain == strain_of(inv) and level >= level_of(inv)) and cmin < need - 1:
            return inv, 'invite'
        if (2 * points + mid2 >= 2 * need and (inv is None or inv <= over)) or cmin >= need - 1:      # no room to ask, or nearly enough alone
            go = target
            if go is None or go <= over:
                raised = [x for x in MAJORS if x not in enemy and h.len[x] >= 3 and ps.len[x][0] >= 3 and bid(4, x) > over]
                go = bid(4, max(raised, key=lambda x: trumps(x))) if raised else None
            if go is not None and go > over and level_of(go) <= 4:
                return go, 'signoff'
    # ---- they hold the contract ----
    if not ours:
        if pact[0] == DOUBLE and pact[1] == 'penalty' and st.doubled == 1 and rho_passed:
            return PASS, ''                              # partner doubled for penalty
        if fit is not None and cmin >= need - 1 and strain != N and h.len[strain] <= 1 and level >= 3 and st.doubled == 0:
            c = cheapest(fit)                            # game values, a fit and shortness in their suit: bid on, do not double
            if c is not None and (level_of(c) <= 4 or (level_of(c) == 5 and cmin >= g.game_minor - 2)):
                return c, 'signoff'
        if fit is not None:
            c = cheapest(fit)
            if c is not None and level_of(c) <= trumps(fit) - 6 + g.compete + (1 if cmin >= 23 else 0) and cmin >= 16:
                return c, ''
        passed_out = len(st.calls) >= 2 and rho_passed and st.calls[-2][1] == PASS
        if passed_out and level <= 2 and st.doubled == 0 and strain != N and my.hcp[0] >= 10:
            shape = all(h.len[x] >= 3 for x in MAJORS if x not in enemy and x != strain) and h.shape[0] <= 6
            bid_nt = any(t >= 5 and strain_of(t) == N for t, _ in st.acts[me])
            if h.len[strain] <= 2 and shape and not bid_nt and h.hcp + ps.hcp[1] >= 22 \
                    and (h.hcp >= my.hcp[0] + 3 or h.hcp >= 15) and st.legal(DOUBLE):
                return DOUBLE, 'takeout'                 # extra values and short in their suit: ask partner to choose
            for x in (S, H, D, C):
                c = cheapest(x)
                if c is not None and level_of(c) <= 2 and x not in enemy and h.len[x] >= 6 and h.hcp >= my.hcp[0] + 1:
                    return c, ''
        if st.legal(DOUBLE) and cmin >= g.penalty and level >= 2 and not forced and (fit is None or level >= 4):
            return DOUBLE, 'penalty'
        if not forced:
            return PASS, ''
    # ---- our contract, or we must speak: something natural and cheap ----
    wrong_strain = ours and strain != N and strain != fit and (fit is not None or (h.len[strain] <= 1 and ps.len[strain][0] <= 5) or (ps.len[strain][1] <= 2 and h.len[strain] <= 5))
    better_major = ours and strain == N and fit in MAJORS and level <= 2
    if forced or wrong_strain or better_major:
        options = []
        if fit is not None and cheapest(fit) is not None:
            options.append((cheapest(fit), 2.5 + (fit in MAJORS)))
        for x in SUITS:
            c = cheapest(x)
            if c is None or x in enemy:
                continue
            if h.len[x] >= 4 and my.len[x][0] < 4 and x != fit:
                options.append((c, 2 - 0.4 * (level_of(c) - level) + 0.1 * h.len[x]))
            if h.len[x] >= 6 and my.len[x][0] >= 4:
                options.append((c, 1.8 - 0.4 * (level_of(c) - level)))
            if ps.len[x][0] >= 4 and h.len[x] >= 3 and x != fit:
                options.append((c, 2.2 - 0.4 * (level_of(c) - level)))
        c = cheapest(N)
        if c is not None and (stoppers or not enemy):
            options.append((c, 1.6 - 0.5 * (level_of(c) - level) + (0.5 if h.balanced else 0)))
        misfit = wrong_strain and fit is None
        if options and (forced or max(o[1] for o in options) >= (1.5 if misfit else 2.5)):
            best = max(options, key=lambda o: o[1])[0]
            if level_of(best) <= (5 if forced else 3):
                return best, ''
        if forced:
            own = max((x for x in SUITS if x not in enemy), key=lambda x: (h.len[x], x), default=None)
            c = (cheapest(own) if own is not None else None) or cheapest(N)
            if c is not None and level_of(c) <= 5:
                return c, ''
    return PASS, ''


def escape(h, st, me):
    """Our low contract was doubled and the double left in: run to a long suit when the trump holding is thin."""
    if st.doubled != 1 or st.last is None or st.last[0] % 2 != me % 2 or level_of(st.last[1]) > 2 or len(st.calls) < 3:
        return None
    if not (st.calls[-1][1] == PASS and st.calls[-2][1] == PASS and st.calls[-3][1] == DOUBLE):
        return None
    strain = strain_of(st.last[1])
    held = 0 if strain == N else h.len[strain] + st.shown[(me + 2) % 4].len[strain][0]
    if strain != N and held >= 7:
        return None
    long = max((x for x in SUITS if x != strain), key=lambda x: (h.len[x], x))
    if h.len[long] >= 5 or (strain != N and h.len[strain] <= 1 and h.len[long] >= 4):
        c = next((bid(l, long) for l in range(1, 4) if bid(l, long) > st.last[1]), None)
        return c
    return None


def is_invitation(st, me, token):
    """Is a three-level suit bid over our own side's bid an invitation? A raise of the suit we just bid at the two
    level, or a jump; the cheapest bid in a new strain is only a preference."""
    if st.last is None or level_of(token) != 3:
        return False
    strain = strain_of(token)
    if bid(2, strain) > st.last[1]:
        return True                                      # a jump
    return st.last[0] % 2 == me % 2 and strain == strain_of(st.last[1])


def general_meaning(st, me, token):
    """A rough public reading of a call the tables do not define."""
    g = st.systems[me % 2]
    partner = (me + 2) % 4
    ps, my = st.shown[partner], st.shown[me]
    game = g.game - ps.hcp[0]
    if token == PASS:
        if st.acts[partner] and st.acts[partner][-1][1] == 'invite' and st.calls and st.calls[-1][1] == PASS:
            return M((0, max(my.hcp[0], (my.hcp[0] + my.hcp[1] + 1) // 2 - 1)))
        if st.forced(me) or st.last is None:
            return NOTHING
        top = min(my.hcp[1], game + 1)                  # an unforced pass: no game opposite partner's minimum
        if my.hcp[1] - my.hcp[0] > 6:                   # and from a wide-open hand, not much more than it has promised
            top = min(top, my.hcp[0] + (3 if level_of(st.last[1]) <= 2 else 6))
        return M((0, max(my.hcp[0], top)))
    if token in (DOUBLE, REDOUBLE):
        low = st.last is not None and level_of(st.last[1]) <= 2 and strain_of(st.last[1]) != N
        if low and len(st.calls) >= 2 and st.calls[-1][1] == PASS and st.calls[-2][1] == PASS and my.hcp[0] >= 10:
            return M((max(my.hcp[0], 13), 40), force=1, kind='takeout', **{'CDHS'[strain_of(st.last[1])]: (0, 2)})
        return M((max(my.hcp[0], g.penalty - ps.hcp[1]), 40), kind='penalty')
    level, strain = level_of(token), strain_of(token)
    if token == bid(4, N) and not (st.last is not None and st.last[1] == bid(3, N) and st.last[0] % 2 != me % 2):
        low = min(my.hcp[1], max(my.hcp[0], g.slam - 2 - ps.hcp[0] - 2))
        return M((low, max(low, min(my.hcp[1], low + 4))), kind='slam-invite')
    if below_game_is_enough(token):
        return M((max(my.hcp[0], game - 4), 40), kind='signoff', **({'CDHS'[strain]: (max(2, 8 - ps.len[strain][0]), 13)} if strain != N else {}))
    forced = st.forced(me)
    asks = level == 3 and strain != N and not forced and not st.game_force[me % 2] and is_invitation(st, me, token)
    floor = invite_floor(g, ps)
    if strain == N:
        if level == 2 and (not forced or st.last is None or bid(1, N) > st.last[1]):       # unforced, or a jump: an invitation
            return M((max(my.hcp[0], min(my.hcp[1], floor - 1)), max(my.hcp[0], floor - 1, g.game - 2 - ps.hcp[0])), kind='invite')
        return M()
    upper = (max(my.hcp[0], min(my.hcp[1], floor)), my.hcp[1]) if asks else (0, 40)       # points: shape counts in a suit
    if ps.len[strain][0] >= 3:                           # partner's suit: a raise
        return M(upper, kind='invite' if asks else '', **{'CDHS'[strain]: (max(2, 8 - ps.len[strain][0]), 13)})
    pact = st.acts[partner][-1] if st.acts[partner] else (None, '')
    if level == 3 and strain in MAJORS and my.len[strain][0] < 5 and st.last is not None and st.last == (partner, bid(2, N)) \
            and pact[0] == bid(2, N) and pact[1] != 'signoff':
        return M((my.hcp[0], 40), force=1, kind='choice', **{'CDHS'[strain]: (5, 13)})
    if my.len[strain][0] >= 3:                           # one's own suit again: longer than shown
        longer = max(my.len[strain][0] + 1, 5)
        return M(upper, kind='invite' if asks else '', **{'CDHS'[strain]: (longer, 13)})
    constructive = st.last is not None and st.last[0] % 2 == me % 2 and st.doubled == 0 and pact[1] != 'signoff'
    wide = my.hcp[1] - my.hcp[0] > 6                     # a new suit from a hand that may still be strong is forcing for a round
    return M(force=1 if constructive and wide and not below_game_is_enough(token) else 0, **{'CDHS'[strain]: (4, 13)})


def merged(entries):
    """One public meaning for a call the table lists more than once: the widest ranges that cover every entry."""
    if len(entries) == 1:
        return entries[0]
    out = M((min(m.hcp[0] for m in entries), max(m.hcp[1] for m in entries)), force=max(m.force for m in entries), kind=entries[0].kind)
    for s in SUITS:
        if all(s in m.len for m in entries):
            out.len[s] = (min(m.len[s][0] for m in entries), max(m.len[s][1] for m in entries))
    return out


def odd_opening(token):
    """An opening the table does not list (as a rule the other side's): a long suit and a limited hand."""
    if token < 5:
        return NOTHING
    level, strain = level_of(token), strain_of(token)
    if strain == N:
        return M(kind='signoff')
    return M((0, 15), kind='preempt', **{'CDHS'[strain]: (min(8, 4 + level), 13)})


def explain(st, me, token):
    entries = [m for t, m in table_for(st, me) if t == token]
    if entries:
        return merged(entries)
    return general_meaning(st, me, token) if st.opening is not None else odd_opening(token)


def choose(h, st, me):
    """The call this hand makes now."""
    forced = st.forced(me)
    run = escape(h, st, me)
    if run is not None and st.legal(run):
        return run
    for token, m in table_for(st, me):
        if st.legal(token) and not (forced and token == PASS and m.kind != 'penalty-pass') and m.fits(h):
            return token
    if st.opening is None:
        return PASS
    token, _ = plan(h, st, me)
    return token if st.legal(token) else PASS


class RuleSystemBidder(RuleBidder):
    """A queryable bidder that plays `settings` and reads the other side by `opponents`
    ('standard', 'same', or a settings dictionary)."""
    kind = 'rules'

    def __init__(self, settings=None, opponents='standard'):
        self.settings = settings if isinstance(settings, Settings) else Settings(**(settings or {}))
        if opponents == 'same':
            self.opponents = self.settings
        elif opponents == 'standard':
            self.opponents = STANDARD
        else:
            self.opponents = opponents if isinstance(opponents, Settings) else Settings(**opponents)
        # the system it bids: the rules' version and the settings (how it reads the other side is not part of it)
        self.sha256 = options_sha256(self.kind, dict(asdict(self.settings), rules=RULES))
        self.cache = {}
        self._facing = {}
        self.errors = 0                                  # calls where a rule failed and the bidder passed instead

    def facing(self, same):
        """This system against a side that plays the same system (True) or something natural (False)."""
        if same not in self._facing:
            self._facing[same] = RuleSystemBidder(self.settings, opponents='same' if same else 'standard')
        return self._facing[same]

    def state(self, side, dealer, vul, calls):
        key = (side, dealer, vul, calls)
        st = self.cache.get(key)
        if st is None:
            if len(self.cache) > 50000:
                self.cache.clear()
            systems = (self.settings, self.opponents) if side == 0 else (self.opponents, self.settings)
            st = State(dealer, vul, systems)
            for token in calls:
                st.push(token)
            self.cache[key] = st
        return st

    def call(self, hand, seat, dealer, vul, calls):
        try:
            st = self.state(int(seat) % 2, int(dealer), int(vul), tuple(int(c) for c in calls))
            return choose(Hand(hand), st, int(seat))
        except Exception:                                # a bidder at a table must always produce a legal call
            if STRICT:
                raise
            self.errors += 1
            return PASS

    def choose(self, hands, seat, dealer, vul, calls, turn, legal):
        out = np.empty(len(hands), np.int64)
        for i in range(len(hands)):
            out[i] = self.call(hands[i], seat[i], dealer[i], vul[i], calls[i, :int(turn[i])])
        return out

    def describe(self, seat, dealer, vul, calls):
        """What every call so far has shown, as this bidder reads it: for inspection and tests."""
        st = self.state(int(seat) % 2, int(dealer), int(vul), tuple(int(c) for c in calls))
        return [dict(seat=s, call=t, hcp=m.hcp, lengths={'CDHS'[k]: v for k, v in m.len.items()}, kind=m.kind, force=m.force) for s, t, m in st.calls]


def settings_fields():
    return [f.name for f in fields(Settings)]


def from_package(settings_file=None, settings=None, root=None):
    """Factory for a system package's generator entry: the settings are in a JSON file ({"settings": {...}}, a path
    relative to the repository unless `root` says otherwise) or given."""
    if settings_file:
        import json
        from pathlib import Path
        path = Path(settings_file)
        base = Path(root) if root else Path(__file__).resolve().parents[1]
        settings = json.loads((path if path.is_absolute() else base / path).read_text())['settings']
    return RuleSystemBidder(settings)
