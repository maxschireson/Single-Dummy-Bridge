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

Partnerships (Max, 21:14 UTC on 14 November): "Partnership personalities should be independent, but somewhat
correlated": every latent draw of a persona (its weights, random shares, knowledge and disclosure) is correlated 0.5
with the matching draw of its partner's (`draw_partnership`). Opposing partnerships are independent. The correlation
across dimensions is drawn once per partnership.

Identifiers (same message): a population of variable-personality bots has one identifier, `SidVariable` for Sid's.
"When playing against variable personality bots the system should by default use their identifier": a reader is told
the identifier, never the persona, so it can read the population (whose variability and disclosure rules are public:
`public`) without learning any one persona from its name. "It can ask their partner for estimated styles": the
opponents' view (`view(persona, 'opponent')`, in words `describe(persona, 'opponent')`) is what the partner says.

What is built: drawing personas and partnerships, the public description, the views and their text, and the hooks that
play a persona at a table (Gen7Player and X8Player `table_styles`; the match runner and the play server set them).
What is not: readers that act on the views. The belief nets, the hand-fit scorer and the rollouts' opponent models read
a variable bot by its identifier and otherwise as unstyled; `bid_style.distribution` gives the exact call probabilities
a reader needs to do more.
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


PARTNER_RHO = 0.5           # latent correlation between partners' matching draws (Max, 21:14 UTC on 14 November)
PLAY_NEAR_X8 = 0.05         # an 8X (rollout) bot's margin for its play style, in the rollouts' tricks: inside their standard
                            # error, so close to free; not calibrated. A Gen 8 search bot uses its spec's `near_tie`
DEFAULTS = dict(bid_near=6.0, bid_scale=3.0, bid_random=(0.05, 0.20), play_random=(0.05, 0.20))
KNOWN = ('SidVariable', 'Gen8Variable')     # identifiers of variable-personality populations every reader knows as such


def _u(z, lo, hi):
    return lo + (hi - lo) * _phi(z)


def _one(dimensions, rho, zk, zr, zw, zx, bid_near, bid_scale, bid_random, play_random):
    knowledge = {d: round(0.8 * _phi(z), 3) for d, z in zip(dimensions, zk)}
    ratio = {d: _triangular_ppf(_phi(z), 0., 0.75, 1.5) for d, z in zip(dimensions, zr)}
    disclosure = {d: round(knowledge[d] * ratio[d], 3) for d in dimensions}
    weights = {d: 2 * _phi(z) - 1 for d, z in zip(dimensions, zw)}           # uniform on [-1, 1]
    play = {d: round(weights[d], 3) for d in PLAY if d in weights}
    play['random'] = round(_u(zx[0], *play_random), 3)
    bid = {d: round(weights[d] * bid_scale, 3) for d in BID if d in weights}
    near = _u(zx[2], *bid_near) if isinstance(bid_near, (tuple, list)) else float(bid_near)
    bid.update(random=round(_u(zx[1], *bid_random), 3), near=round(near, 3))
    return dict(play_style=play_styles.check(play), bid_style=bid_style.check(bid), knowledge=knowledge,
                disclosure=disclosure, correlation=round(rho, 3))


def draw_partnership(rng=None, partner_rho=PARTNER_RHO, dimensions=DIMENSIONS, **dials):
    """Two personas for the two players of one partnership: each latent normal of one is correlated `partner_rho` with
    the matching one of the other (so each persona alone is distributed as `draw` gives it). The correlation across
    dimensions (knowledge, disclosure) is drawn once for the partnership. dials: as `draw`."""
    rng = rng or random.Random()
    dials = dict(DEFAULTS, **dials)
    rho = rng.triangular(-0.2, 0.8, 0.6)
    n = len(dimensions)
    c = math.sqrt(1 - partner_rho ** 2)

    def pair(make):
        a, w = make(), make()
        return a, [partner_rho * x + c * y for x, y in zip(a, w)]

    zk = pair(lambda: _equicorrelated(rng, n, rho))
    zr = pair(lambda: _equicorrelated(rng, n, rho))
    zw = pair(lambda: [rng.gauss(0, 1) for _ in range(n)])
    zx = pair(lambda: [rng.gauss(0, 1) for _ in range(3)])                  # play random, bid random, bid margin
    return [_one(dimensions, rho, zk[i], zr[i], zw[i], zx[i], **dials) for i in (0, 1)]


def draw(rng=None, dimensions=DIMENSIONS, **dials):
    """One persona. rng: random.Random. dials: bid_near, the bidding style's margin, a number or a (low, high) range
    drawn per persona; bid_scale, the bidding weights uniform on [-bid_scale, bid_scale] (play weights on [-1, 1]);
    bid_random, play_random: ranges for the random shares. bid_near and bid_scale together are the bidding dose: the
    defaults (6, 3) cost a mixed population 0.24 +- 0.03 IMP a board, double dummy (reports/bid_style_cost_2026-11-14.md)."""
    return draw_partnership(rng, dimensions=dimensions, **dials)[0]


def seats(rng=None, sides=(0, 1), **dials):
    """{seat: persona} for an independent partnership on each side listed (0: North-South, seats 0 and 2; 1: East-West)."""
    rng = rng or random.Random()
    out = {}
    for side in sides:
        a, b = draw_partnership(rng, **dials)
        out[side], out[side + 2] = a, b
    return out


def is_variable(bot_id, extra=()):
    """Is this a variable-personality population's identifier (the known ones, or `extra`, e.g. a match's own)?"""
    return bot_id is not None and (bot_id in KNOWN or bot_id in tuple(extra))


def public(identifier='SidVariable', **dials):
    """What anyone may know about a variable-personality population (Max: "the (to be publicly known) level of
    variability and disclosure"): how its personas are drawn, never any one persona."""
    d = dict(DEFAULTS, **dials)
    return dict(
        identifier=identifier,
        play=dict(dimensions=list(PLAY), weights='uniform on [-1, 1] per dimension', random=list(d['play_random']),
                  margin=f"among cards within the bot's margin of its best ({PLAY_NEAR_X8} tricks for a rollout bot; "
                         "exact ties for a search bot at near_tie 0)"),
        bid=dict(dimensions=list(BID), weights=f"uniform on [-{d['bid_scale']:g}, {d['bid_scale']:g}] per dimension",
                 random=list(d['bid_random']), near=d['bid_near'],
                 rule='among calls the bidder rates at least exp(-near) of its best, the highest log p + a_eff * action'),
        knowledge='0.8 * Phi(z) per dimension: 0 to 80%, what the partner knows of each weight',
        disclosure="knowledge * r per dimension, r triangular on [0, 1.5] with mode 0.75: what the opponents are told",
        dimension_correlation='triangular on [-0.2, 0.8], mode 0.6, drawn per partnership (latent normals of knowledge, of r)',
        partner_correlation=PARTNER_RHO,
        opponents='independent partnerships',
        cost='bidding: about 0.24 IMP a board across the population, double dummy; play: margins inside the search noise')


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


def describe(persona, who='opponent'):
    """A persona in words, each dimension at the strength `who` reads it: 'opponent' (what the partner says: weight
    times disclosure), 'partner' (weight times knowledge) or 'full' (the weight itself)."""
    shares = {'opponent': persona['disclosure'], 'partner': persona['knowledge']}.get(who)
    out = []
    for d in DIMENSIONS:
        style = persona['bid_style'] if d in BID else persona['play_style']
        scale = (float(style.get(d, 0.)) / 3 if d in BID else float(style.get(d, 0.)))     # bidding weights run to +-3
        w = scale * (1. if shares is None else shares.get(d, 0.))
        if abs(w) < 0.15:
            continue
        degree = 'slightly' if abs(w) < 0.4 else 'often' if abs(w) < 0.8 else 'strongly'
        out.append(f'{degree} {WORDS[d][0 if w > 0 else 1]}')
    return '; '.join(out) or 'nothing beyond the system'


def disclosure_text(persona):
    """What the opponents are told, in words: each dimension at its disclosed strength (weight times disclosure)."""
    return describe(persona, 'opponent')
