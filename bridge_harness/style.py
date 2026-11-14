"""Styles of card play: a directed preference among the cards a bot rates as close.

Max, 03:35 to 03:46 UTC on 14 November 2026: the opponents a bot meets should not all play alike, or a bot that knows
one of them reads its cards better than bridge logic allows, and that reading is counted as strength. So bots get
personalities. A personality does not change what a bot thinks a card is worth. Among the cards the bot rates within a
margin of its best (the spec's `near_tie` for a search bot, `mix.near` for a rollout bot), it prefers some to others in
a fixed direction, and a small share of the time takes any of them. The margin is the dose: the wider it is, the more
the personality costs. "It doesn't matter if we get that mix or even the exact dimensions of style right": the point is
a variety of habits, most of them directed, a little of it random.

A style is {feature: weight, ..., 'random': share}. Features, each worked out from the seat's own view:

  tempo    +1 for a card that takes the trick now: following, a card that beats what is on the table when partner's
           card is not already winning; leading, a card no outstanding card of its suit beats (cashing a winner).
           tempo > 0 is the greedy player (tricks now), tempo < 0 the patient one (duck, wait, keep the winner)
  active   leading only. +1 for a suit this side has not led before in the hand (a switch, an attack), and at any
           lead +1 for a low card from a suit headed by an honour it does not also hold the next honour under (leading
           away from an honour). active > 0 is the active defender, active < 0 the passive one. Counts for declarer too
  high     the card's rank within its suit, 0 for the two to 1 for the ace: high > 0 plays high cards freely,
           high < 0 keeps them

`choose` takes the best-scoring of the eligible cards (several where they score alike: the caller breaks that tie as
it always did), or, with probability `random`, all of them.
"""
from .core import winner

FEATURES = ('tempo', 'active', 'high')


def check(style):
    """A style as it must be: known features, weights between -4 and 4, `random` a share."""
    if not isinstance(style, dict) or set(style) - set(FEATURES) - {'random'}:
        raise ValueError(f'A style is a dict of {FEATURES} and random')
    for k, v in style.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0 <= v <= 1 if k == 'random' else -4 <= v <= 4):
            raise ValueError(f'Bad style setting {k}: {v!r}')
    return dict(style)


def features(o, x):
    """{feature: value} of card x for the seat to play in Observation o."""
    suit, rank = x // 13, x % 13
    side = o.actor % 2
    gone = {c for _, c in o.history}
    out = dict(tempo=0., active=0., high=rank / 12.)
    if o.trick:
        ahead = winner(list(o.trick), o.contract.trump)
        if ahead % 2 != side and winner(list(o.trick) + [(o.actor, x)], o.contract.trump) == o.actor:
            out['tempo'] = 1.
    else:
        mine = {c for s, h in enumerate(o.known_hands) if h is not None and s % 2 == side for c in h}
        if all(13 * suit + r in gone or 13 * suit + r in mine for r in range(rank + 1, 13)):
            out['tempo'] = 1.                               # nothing outstanding beats it: a winner being cashed
        tricks = [o.history[i:i + 4] for i in range(0, len(o.history) - len(o.history) % 4, 4)]
        led_before = {t[0][1] // 13 for t in tricks if t[0][0] % 2 == side}
        hand = set(o.known_hands[o.actor] or ())
        honours = [r for r in range(9, 13) if 13 * suit + r in hand]           # J, Q, K, A held in the suit
        broken = any(13 * suit + r - 1 not in hand for r in honours)           # an honour without the next one under it
        if (tricks and suit not in led_before) or (rank < 9 and honours and broken):
            out['active'] = 1.
    return out


def score(o, x, style):
    f = features(o, x)
    return sum(float(style.get(k, 0.)) * f[k] for k in FEATURES)


def choose(o, eligible, style, ticket):
    """The cards of `eligible` the style keeps: its best-scoring ones, or all of them when `ticket` (uniform in [0, 1))
    falls under the style's random share. `eligible` when there is nothing to choose."""
    eligible = list(eligible)
    if len(eligible) < 2 or ticket < float(style.get('random', 0.)):
        return eligible
    scores = {x: score(o, x, style) for x in eligible}
    best = max(scores.values())
    return [x for x in eligible if best - scores[x] <= 1e-9]
