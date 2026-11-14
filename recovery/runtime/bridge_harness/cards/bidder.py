"""A compiled card as a bidder (Gen 9 WIP).

Covered contexts: the first satisfied rule. Elsewhere: a fallback bidder if one is given
(anything with ``call(hand, seat, dealer, vul, calls) -> token``, e.g. g8's RuleSystemBidder),
otherwise pass. This is a generator for training and measurement data, not a strong bidder.

Speaks the system_bidders interface (session/act with bidding_env tokens) so the Gen 8
tooling can use it.
"""
import hashlib
import json

import numpy as np

from ..bidding_env import CALL_ID, CALLS
from .context import Context
from .features import features_of_hands
from .system import CardSystem

VUL_NAMES = ('None', 'NS', 'EW', 'Both')


def token_of(call):
    return CALL_ID[call]


def call_of(token):
    return CALLS[int(token)]


class CardBidder:
    kind = 'card'

    def __init__(self, card, fallback=None):
        self.system = card if isinstance(card, CardSystem) else CardSystem(card)
        self.fallback = fallback
        self.sha256 = hashlib.sha256(json.dumps({'kind': 'card', 'card': self.system.card.d}, sort_keys=True).encode()).hexdigest()
        self.stats = {'covered': 0, 'fallback': 0}

    def decide(self, hand, seat, dealer, vul, calls):
        """(call string, rule or None) for one hand. vul is a name ('None', 'NS', 'EW', 'Both')."""
        ctx = Context.make(calls, dealer, seat, vul)
        rules = self.system.rules(ctx)
        if rules is not None:
            f = features_of_hands([hand])
            for r in rules:
                if r.pred.dist(f)[0] == 0:
                    self.stats['covered'] += 1
                    return r.call, r
        self.stats['fallback'] += 1
        if self.fallback is not None:
            vi = VUL_NAMES.index(vul) if isinstance(vul, str) else int(vul)
            try:
                tok = self.fallback.call(hand, seat, dealer, vi, [token_of(c) for c in ctx.calls])
            except Exception:                       # the fallback reads our calls by its own tables; it may not cope
                self.stats['fallback_error'] = self.stats.get('fallback_error', 0) + 1
                return 'PASS', None
            c = call_of(tok)
            return (c if c in ctx.legal else 'PASS'), None
        return 'PASS', None

    # system_bidders interface ---------------------------------------------------------
    def call(self, hand, seat, dealer, vul, calls):
        names = [call_of(t) for t in calls]
        v = VUL_NAMES[int(vul)] if not isinstance(vul, str) else vul
        return token_of(self.decide(hand, seat, dealer, v, names)[0])

    def session(self, hands, seat, dealer, vul):
        return _Session(self, np.asarray(hands), np.asarray(seat), np.asarray(dealer), np.asarray(vul))


class _Session:
    def __init__(self, b, hands, seat, dealer, vul):
        self.b, self.hands, self.seat, self.dealer, self.vul = b, hands, seat, dealer, vul

    def act(self, rows, calls, turn, legal):
        out = np.empty(len(rows), np.int64)
        for k, r in enumerate(rows):
            prefix = [int(t) for t in calls[k, :turn[k]]]
            out[k] = self.b.call(self.hands[r], int(self.seat[r]), int(self.dealer[r]), int(self.vul[r]), prefix)
            if legal is not None and not legal[k, out[k]]:
                out[k] = CALL_ID['PASS']
        return out


def bid_table(bidders, hands, dealer, vul, max_calls=40):
    """Bid one deal: bidders[seat] (CardBidder or anything with decide/call), hands[seat] card ids.
    Returns the calls (strings) and, per call, the rule that made it (None if not covered)."""
    calls, why = [], []
    while True:
        seat = (dealer + len(calls)) % 4
        b = bidders[seat]
        if isinstance(b, CardBidder):
            c, r = b.decide(hands[seat], seat, dealer, vul, calls)
        else:
            vi = VUL_NAMES.index(vul)
            c, r = call_of(b.call(hands[seat], seat, dealer, vi, [token_of(x) for x in calls])), None
        ctx = Context.make(calls, dealer, seat, vul)
        if c not in ctx.legal:
            c = 'PASS'
        calls.append(c)
        why.append(r)
        n = len(calls)
        if n >= 4 and all(x == 'PASS' for x in calls[-3:]) and any(x != 'PASS' for x in calls[:-3]):
            break
        if n == 4 and all(x == 'PASS' for x in calls):
            break
        if n >= max_calls:
            break
    return calls, why
