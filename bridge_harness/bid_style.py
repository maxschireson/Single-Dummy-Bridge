"""Styles of bidding: a directed preference among the calls a bidder rates as close, the counterpart of style.py.

Max, 19:31 UTC on 14 November 2026: two bidding style dimensions, "then put some randomization in", with the same
disclosure and correlation rules as the card-play styles (bridge_harness/persona.py). A bidding style does not change
what the bidder thinks a call is worth. Among the legal calls the bidder rates within `near` of its best (a log
probability ratio: the cap), it trades the bidder's probability for action at a fixed rate (the weight), and a share of
the time (`random`) draws one of them from the bidder's own probabilities. The larger the weight and the wider `near`,
the more the style costs.

A style is {'aggressive': a, 'shape': s, 'random': share, 'near': margin}:

  aggressive  more bidding (a > 0) or less (a < 0). Each call's `action`: pass 0, double or redouble 0.5, a bid
              1 plus the levels it goes beyond the cheapest legal bid in its strain (a raise to game over an
              invitation, a jump, a bid instead of a pass). One step of action is worth |a| nats of the bidder's log
              probability: with a = 1 the style bids a level higher whenever the bidder rates that call at least
              1/e (37%) as likely as the lower one
  shape       values shape more (s > 0) or high cards more (s < 0). It moves the aggression for THIS hand: a shape
              bidder bids more with a shapely hand and less with a flat one (s * z_D); a points bidder bids more with
              high cards and less without them (|s| * z_H). z_D and z_H are the hand's distribution points and high-card
              points standardised over all hands, clipped to [-2, 2]. Across hands the lean averages zero, so the shape
              dimension changes WHICH hands bid more, not how much the bidder bids on average
  random      the share of decisions on which it draws a call from the close ones in proportion to the bidder's own
              probabilities (an earlier version drew uniformly; at near 6 a 15% uniform share alone cost 0.17 IMP a
              board, more than the directed part of most styles)
  near        the margin: a call is close if its probability is at least exp(-near) times the best call's

Effective aggression for a hand: a_eff = a + lean(hand). The style's choice: the close call with the highest
log p(call) + a_eff * action(call); ties go to the bidder's own order, so with a_eff = 0 it is the bidder's best. The
weight's size matters (an earlier version took the close call with the most or least action whatever the weight, so
only the weight's sign and `near` mattered, and a reader told half a style read it as the whole style).
`distribution` gives the exact probability of each call under a style (what a reader needs to read a styled bidder, at
the strength it knows or was told: `scaled`).
"""
from __future__ import annotations

import math

import numpy as np

from .bidding_env import CALLS

FEATURES = ('aggressive', 'shape')
STRAINS = 'CDHSN'
# Distribution points of a hand: one per card past four in a suit, plus void 3, singleton 2, doubleton 1. Mean and
# standard deviation over all 13-card hands (exact, from the suit-length distribution: compute_d_moments below).
D_MEAN, D_SD = 2.5752, 1.7636
H_MEAN, H_SD = 10.0, 4.1302


def check(style):
    """A bidding style as it must be: known keys, weights between -4 and 4, `random` a share, `near` >= 0."""
    if not isinstance(style, dict) or set(style) - set(FEATURES) - {'random', 'near'}:
        raise ValueError(f'A bidding style is a dict of {FEATURES}, random and near')
    for k, v in style.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f'Bad bidding style setting {k}: {v!r}')
        ok = (0 <= v <= 1) if k == 'random' else (0 <= v <= 6) if k == 'near' else (-4 <= v <= 4)
        if not ok:
            raise ValueError(f'Bad bidding style setting {k}: {v!r}')
    return dict(style)


def scaled(style, f):
    """The style as a reader who knows a share f of it models it: the directed weights times f; random and near kept
    (a reader who knows a bidder randomises knows it does so among close calls)."""
    out = dict(style)
    for k in FEATURES:
        if k in out:
            out[k] = float(out[k]) * f
    return out


# ---- the hand ------------------------------------------------------------------------------------
def distribution_points(hand):
    lengths = [sum(1 for c in hand if c // 13 == s) for s in range(4)]
    return sum(max(0, n - 4) for n in lengths) + sum({0: 3, 1: 2, 2: 1}.get(n, 0) for n in lengths)


def hcp(hand):
    return sum(max(0, c % 13 - 8) for c in hand)


def lean(hand, shape):
    """The shape dimension's change to this hand's aggression."""
    if not shape:
        return 0.
    if shape > 0:
        z = (distribution_points(hand) - D_MEAN) / D_SD
    else:
        z = (hcp(hand) - H_MEAN) / H_SD
    return abs(shape) * max(-2., min(2., z))


# ---- the calls -------------------------------------------------------------------------------------
def _parse(call):
    if call in ('PASS', 'P'):
        return None
    if call in ('X', 'XX'):
        return call
    return int(call[0]), STRAINS.index(call[1])


def action(call, legal_calls):
    """How much a call bids: pass 0, double or redouble 0.5, a bid 1 plus the levels it goes beyond the cheapest legal
    bid in its strain."""
    p = _parse(call)
    if p is None:
        return 0.
    if p in ('X', 'XX'):
        return .5
    level, strain = p
    cheapest = min((q[0] for q in map(_parse, legal_calls) if isinstance(q, tuple) and q[1] == strain), default=level)
    return 1. + (level - cheapest)


def close_calls(probs, mask, near):
    """Indices of the legal calls whose probability is within exp(-near) of the best legal call's, best first."""
    p = np.where(mask, np.asarray(probs, float), -1.)
    best = int(np.argmax(p))
    floor = p[best] * math.exp(-near)
    idx = [i for i in np.flatnonzero(mask) if p[i] >= floor and p[i] > 0]
    return sorted(idx, key=lambda i: -p[i]) or [best]


def choose(probs, mask, hand, style, ticket, pick, legal_calls=None):
    """The call index a styled bidder makes. probs: the bidder's probabilities over CALLS; mask: legal calls; hand: the
    bidder's 13 cards; ticket, pick: two uniform numbers in [0, 1) (whether this is a random decision, and which close
    call it takes). legal_calls: the auction's legal call names, for `action` (default: all legal calls)."""
    near = float(style.get('near', 0.))
    close = close_calls(probs, mask, near)
    if len(close) < 2:
        return close[0]
    if ticket < float(style.get('random', 0.)):
        w = np.array([float(probs[i]) for i in close])
        k = int(np.searchsorted(np.cumsum(w / w.sum()), pick, side='right'))
        return close[min(k, len(close) - 1)]
    return _directed(probs, close, hand, style,
                     legal_calls if legal_calls is not None else [CALLS[i] for i in np.flatnonzero(mask)])


def _directed(probs, close, hand, style, legal_calls):
    """The close call with the highest log p + a_eff * action (close is best first, so ties go to the bidder)."""
    a = float(style.get('aggressive', 0.)) + lean(hand, float(style.get('shape', 0.)))
    if a == 0:
        return close[0]
    vals = [math.log(float(probs[i])) + a * action(CALLS[i], legal_calls) for i in close]
    best = max(vals)
    return next(i for i, v in zip(close, vals) if v >= best - 1e-12)


def distribution(probs, mask, hand, style, legal_calls=None):
    """{call index: probability} under the style: (1 - random) on the directed call, random spread over the close
    calls in proportion to the bidder's probabilities. The plain bidder's greedy choice is the style {} (all mass on its
    best call)."""
    near = float(style.get('near', 0.))
    close = close_calls(probs, mask, near)
    r = float(style.get('random', 0.)) if len(close) > 1 else 0.
    legal = legal_calls if legal_calls is not None else [CALLS[i] for i in np.flatnonzero(mask)]
    total = sum(float(probs[i]) for i in close)
    out = {i: r * float(probs[i]) / total for i in close}
    d = _directed(probs, close, hand, style, legal) if len(close) > 1 else close[0]
    out[d] = out.get(d, 0.) + 1 - r
    return out


def compute_d_moments():
    """Exact mean and standard deviation of distribution_points over all 13-card hands (by suit-length patterns)."""
    from math import comb
    total = comb(52, 13)
    m1 = m2 = 0.
    for a in range(14):
        for b in range(14 - a):
            for c in range(14 - a - b):
                d = 13 - a - b - c
                ways = comb(13, a) * comb(13, b) * comb(13, c) * comb(13, d)
                lengths = (a, b, c, d)
                dp = sum(max(0, n - 4) for n in lengths) + sum({0: 3, 1: 2, 2: 1}.get(n, 0) for n in lengths)
                m1 += ways * dp
                m2 += ways * dp * dp
    mean = m1 / total
    return mean, math.sqrt(m2 / total - mean * mean)
