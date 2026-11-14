"""Personas: a bot's card-play and bidding styles, how much of them its partner knows, and how much of them is disclosed
to its opponents.

Max, 04:02 to 04:10 UTC on 14 November 2026, for play styles (training/rollout-loop-20261113/PLAN.md, "the population's
dials (not built yet)"), and 19:31 UTC the same day: the same rules for bidding styles. Per style dimension d:

  knowledge   k_d: the share of the style the partner knows, uniform-ish over 0 to 80%
  disclosure  x_d = k_d * r_d: what the opponents are told, usually 75% of the partner's knowledge (r_d from 0 to 150%,
              mode 0.75), so a partner usually reads a little more of the style than the opponents were told, and now
              and then the opponents are told more than the partner knows

Both are correlated across dimensions: each persona draws one correlation rho, centred 0.6 in [-0.2, 0.8] (triangular),
and the latent normals behind k and behind r are equicorrelated at rho. A partner who knows one of a bot's habits well
tends to know the others.

The styles themselves: each dimension's weight is drawn on [-1, 1] (most personas lean several ways at once, each a
little), plus a random share; `play_style` is a bridge_harness/style.py style, `bid_style` a bridge_harness/bid_style.py
style. Doses (the margins that set what a style costs) are given by the caller: the play margin belongs to the player
spec (`near_tie`, `mix.near`), the bidding margin is the bid style's `near`.

What is built: drawing personas, the views a partner and an opponent should read with (`view`), and disclosure text.
What is not: the readers using those views. The belief nets, the hand-fit scorer and the rollouts' opponent models read
every bot as unstyled; `bid_style.distribution` gives the exact call probabilities a reader needs to do otherwise.
"""
from __future__ import annotations

import math
import random

from . import bid_style, style as play_styles

PLAY = play_styles.FEATURES              # tempo, active, high
BID = bid_style.FEATURES                 # aggressive, shape
DIMENSIONS = PLAY + BID


def _phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _triangular_ppf(u, lo, mode, hi):
    c = (mode - lo) / (hi - lo)
    if u < c:
        return lo + math.sqrt(u * (hi - lo) * (mode - lo))
    return hi - math.sqrt((1 - u) * (hi - lo) * (hi - mode))


def _equicorrelated(rng, n, rho):
    """n standard normals with pairwise correlation rho (rho >= -1/(n-1))."""
    common = rng.gauss(0, 1)
    a, b = math.sqrt(max(rho, 0.)), math.sqrt(1 - abs(rho))
    if rho >= 0:
        return [a * common + b * rng.gauss(0, 1) for _ in range(n)]
    # negative rho: centre independent normals (pairwise correlation -1/(n-1)), then mix toward independence
    xs = [rng.gauss(0, 1) for _ in range(n)]
    m = sum(xs) / n
    centred = [(x - m) * math.sqrt(n / (n - 1)) for x in xs]
    t = min(1., -rho * (n - 1))
    ys = [rng.gauss(0, 1) for _ in range(n)]
    return [math.sqrt(t) * cx + math.sqrt(1 - t) * y for cx, y in zip(centred, ys)]


def draw(rng=None, bid_near=6.0, bid_random=(0.05, 0.20), play_random=(0.05, 0.20), dimensions=DIMENSIONS,
         bid_scale=3.0):
    """One persona. rng: random.Random; bid_near: the bidding style's margin, a number or a (low, high) range drawn
    uniformly per persona; bid_scale: the bidding weights are uniform on [-bid_scale, bid_scale] (play weights on
    [-1, 1]); *_random: ranges for the random shares. bid_near and bid_scale together are the bidding dose: the
    defaults (6, 3) cost a mixed population 0.24 +- 0.03 IMP a board, double dummy (reports/bid_style_cost_2026-11-14.md)."""
    rng = rng or random.Random()
    rho = rng.triangular(-0.2, 0.8, 0.6)
    n = len(dimensions)
    zk = _equicorrelated(rng, n, rho)
    zr = _equicorrelated(rng, n, rho)
    knowledge = {d: round(0.8 * _phi(z), 3) for d, z in zip(dimensions, zk)}
    ratio = {d: _triangular_ppf(_phi(z), 0., 0.75, 1.5) for d, z in zip(dimensions, zr)}
    disclosure = {d: round(knowledge[d] * ratio[d], 3) for d in dimensions}
    weights = {d: round(rng.uniform(-1, 1), 3) for d in dimensions}
    play = {d: weights[d] for d in PLAY if d in weights}
    play['random'] = round(rng.uniform(*play_random), 3)
    bid = {d: round(weights[d] * bid_scale, 3) for d in BID if d in weights}
    near = rng.uniform(*bid_near) if isinstance(bid_near, (tuple, list)) else float(bid_near)
    bid.update(random=round(rng.uniform(*bid_random), 3), near=round(near, 3))
    return dict(play_style=play_styles.check(play), bid_style=bid_style.check(bid), knowledge=knowledge,
                disclosure=disclosure, correlation=round(rho, 3))


def view(persona, who):
    """The styles as `who` ('partner' or 'opponent') should model them: each dimension's weight times the share that
    reader knows (knowledge) or was told (disclosure). Random shares and the bidding margin are known to both."""
    shares = persona['knowledge'] if who == 'partner' else persona['disclosure']
    play = {k: (v * shares.get(k, 0.) if k in PLAY else v) for k, v in persona['play_style'].items()}
    bid = {k: (v * shares.get(k, 0.) if k in BID else v) for k, v in persona['bid_style'].items()}
    return dict(play_style=play, bid_style=bid)


WORDS = {
    'aggressive': ('bids aggressively', 'bids conservatively'),
    'shape': ('values shape over high cards', 'values high cards over shape'),
    'tempo': ('takes its tricks early', 'ducks and waits'),
    'active': ('leads and defends actively', 'leads and defends passively'),
    'high': ('plays high cards freely', 'keeps its high cards'),
}


def disclosure_text(persona):
    """What the opponents are told, in words: each dimension at its disclosed strength (weight times disclosure)."""
    out = []
    for d in DIMENSIONS:
        style = persona['bid_style'] if d in BID else persona['play_style']
        w = float(style.get(d, 0.)) * persona['disclosure'].get(d, 0.)
        if abs(w) < 0.15:
            continue
        degree = 'slightly' if abs(w) < 0.4 else 'often' if abs(w) < 0.8 else 'strongly'
        out.append(f'{degree} {WORDS[d][0 if w > 0 else 1]}')
    return '; '.join(out) or 'nothing beyond the system'
