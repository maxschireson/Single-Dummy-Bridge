"""The auction from one seat's point of view (Gen 9 WIP).

Roles: 0 me, 1 left-hand opponent, 2 partner, 3 right-hand opponent. Calls are normalized
strings as in core.normalize_bid: 'PASS', 'X', 'XX', '1C'..'7N'.
"""
from dataclasses import dataclass
from functools import cached_property

from ..core import normalize_bid, vulnerable

ME, LHO, PARTNER, RHO = 0, 1, 2, 3
ROLE = 'MLPR'
BIDS = tuple(f'{level}{strain}' for level in range(1, 8) for strain in 'CDHSN')
RANK = {b: i for i, b in enumerate(BIDS)}


def is_bid(call):
    return call in RANK


def level(call):
    return int(call[0])


def strain(call):
    return call[1]


def bid_above(call, strain_):
    """The cheapest bid in a strain above `call` (None = no bid yet)."""
    start = RANK[call] + 1 if call else 0
    for b in BIDS[start:]:
        if b[1] == strain_:
            return b
    return None


def legal_calls(calls):
    """Legal next calls after a sequence of normalized calls (from the dealer)."""
    last_bid, last_bidder, doubled, redoubled = None, None, False, False
    for i, c in enumerate(calls):
        if is_bid(c):
            last_bid, last_bidder, doubled, redoubled = c, i % 4, False, False
        elif c == 'X':
            doubled = True
        elif c == 'XX':
            redoubled = True
    n = len(calls)
    out = ['PASS']
    if last_bid is not None:
        opp = (n - last_bidder) % 2 == 1
        if opp and not doubled and not redoubled:
            out.append('X')
        if opp is False and doubled and not redoubled:
            out.append('XX')
    out.extend(BIDS[RANK[last_bid] + 1:] if last_bid else BIDS)
    return out


@dataclass(frozen=True)
class Context:
    """`calls` from the dealer; `turn` = len(calls) is the call to be made by `seat`."""
    calls: tuple
    dealer: int
    seat: int
    vul: str = 'None'

    @staticmethod
    def make(calls, dealer, seat, vul='None'):
        return Context(tuple(normalize_bid(c) for c in calls), int(dealer), int(seat), vul)

    @cached_property
    def roles(self):
        """(role, call) for every call so far."""
        return tuple(((self.dealer + i - self.seat) % 4, c) for i, c in enumerate(self.calls))

    @cached_property
    def we_vul(self):
        return vulnerable(self.vul, self.seat)

    @cached_property
    def they_vul(self):
        return vulnerable(self.vul, (self.seat + 1) % 4)

    @cached_property
    def opening_index(self):
        for i, c in enumerate(self.calls):
            if is_bid(c):
                return i
        return None

    @cached_property
    def opener(self):
        i = self.opening_index
        return None if i is None else self.roles[i][0]

    @cached_property
    def opening(self):
        i = self.opening_index
        return None if i is None else self.calls[i]

    @cached_property
    def position(self):
        """Seat in the bidding order counted from the dealer, 1..4 (for opening decisions)."""
        return (self.seat - self.dealer) % 4 + 1

    @cached_property
    def after_open(self):
        """Roles and calls from the opening bid on, as a compact key such as 'P1H R2C'."""
        i = self.opening_index
        if i is None:
            return ''
        return ' '.join(f'{ROLE[r]}{c if c != "PASS" else "P"}' for r, c in self.roles[i:])

    @cached_property
    def last_bid(self):
        for c in reversed(self.calls):
            if is_bid(c):
                return c
        return None

    @cached_property
    def last_bidder(self):
        for r, c in reversed(self.roles):
            if is_bid(c):
                return r
        return None

    def calls_of(self, role):
        return [c for r, c in self.roles if r == role]

    def bids_of(self, role):
        return [c for r, c in self.roles if r == role and is_bid(c)]

    @cached_property
    def legal(self):
        return legal_calls(self.calls)

    @cached_property
    def key(self):
        if self.opening_index is None:
            return f'open{self.position}:{int(self.we_vul)}{int(self.they_vul)}'
        return f'{self.after_open}|{int(self.we_vul)}{int(self.they_vul)}'

    @cached_property
    def doubled_state(self):
        """'' undoubled, 'X' or 'XX' for the current contract."""
        state = ''
        for c in self.calls:
            if is_bid(c):
                state = ''
            elif c in ('X', 'XX'):
                state = c
        return state

    def unbid_suits(self):
        """Suits (as strain letters) nobody has bid naturally so far, cheapest first."""
        used = {strain(c) for c in self.calls if is_bid(c)}
        return [s for s in 'CDHS' if s not in used]
