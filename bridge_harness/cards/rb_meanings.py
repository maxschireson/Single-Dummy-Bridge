"""The rule bidder's own tables as filter meanings (Gen 9 WIP).

``RuleBidderMeanings(settings).rules(ctx)`` lifts the table that g8's rule bidder
(bridge_harness/rule_bidder.py) consults in a situation into Rules whose predicates can be
evaluated over hand types, so the filter reads a rule-bidder player with exactly the meanings it
bids with. A meaning's private test is evaluated on a hand built from the type (lengths and
honours A-T; the tests read nothing else).

These tables are not exhaustive: a hand that fits no entry is bid by the general procedure, so
for such a hand the filter learns nothing (``exhaustive = False``).
"""
import numpy as np

from .. import rule_bidder as rb
from ..bidding_env import CALL_ID, CALLS
from .features import Rule, WEIGHTS

VUL_INDEX = {'None': 0, 'NS': 1, 'EW': 2, 'Both': 3}
G8_SUIT = 'CDHS'                    # rule_bidder's suit index order


def type_hand(length, hon):
    """A 13-card hand (core card ids) with these lengths and honours, spot cards from the two up."""
    cards = []
    for s in range(4):
        h, n = int(hon[s]), int(length[s])
        top = [12 - j for j in range(5) if h >> j & 1]
        cards += [13 * s + r for r in top]
        cards += [13 * s + r for r in range(n - len(top))]
    return cards


class MeaningPred:
    """Distance to one rule-bidder meaning: ranges as in Clause, plus a fixed cost when the private test fails."""

    def __init__(self, m, test_cost=2.0):
        self.m, self.test_cost = m, test_cost
        self._cache = {}

    def dist(self, f, weights=WEIGHTS):
        m = self.m
        d = weights['hcp'] * (np.maximum(m.hcp[0] - f['hcp'], 0) + np.maximum(f['hcp'] - m.hcp[1], 0)).astype(float)
        for s, (lo, hi) in m.len.items():
            v = f[G8_SUIT[s]]
            d = d + weights['len'] * (np.maximum(lo - v, 0) + np.maximum(v - hi, 0))
        if m.test is not None:
            length, hon = f['_length'], f['_hon']
            keys = (length * (14 ** np.arange(4))).sum(1) * 32 ** 4 + (hon * (32 ** np.arange(4))).sum(1)
            ok = np.empty(len(keys), bool)
            for i, k in enumerate(keys):
                k = int(k)
                if k not in self._cache:
                    self._cache[k] = bool(m.test(rb.Hand(type_hand(length[i], hon[i]))))
                ok[i] = self._cache[k]
            d = d + np.where(ok, 0.0, self.test_cost)
        return d

    def sat(self, f):
        return self.dist(f) == 0


class RuleBidderMeanings:
    exhaustive = False

    def __init__(self, settings=None, opponents='standard', name=None):
        self.bidder = rb.RuleSystemBidder(settings, opponents)
        self.id = name or ('rules-' + self.bidder.sha256[:8])
        self._cache = {}

    def rules(self, ctx):
        key = (ctx.calls, ctx.dealer, ctx.seat, ctx.vul)
        if key in self._cache:
            return self._cache[key]
        tokens = tuple(CALL_ID[c] for c in ctx.calls)
        try:
            st = self.bidder.state(ctx.seat % 2, ctx.dealer, VUL_INDEX[ctx.vul], tokens)
            table = rb.table_for(st, ctx.seat)
        except (IndexError, ValueError, KeyError):  # its tables reading an auction from another system
            self.failures = getattr(self, 'failures', 0) + 1
            self._cache[key] = None
            return None
        out = None
        if table:
            forced = st.forced(ctx.seat)
            out = [Rule(CALLS[t], MeaningPred(m), 'rb_' + (m.kind or 'call'), m.kind)
                   for t, m in table if st.legal(t) and not (forced and t == rb.PASS)] or None
        self._cache[key] = out
        return out
