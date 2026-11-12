"""Carding agreements as executable rules: what a spot card or a lead says, and how likely it was.

Gen 9 work in progress (G9-S2; design: docs/gen9/signals.md). Used by no arena bot.

One function, `SignalModel.probabilities`, serves both sides of the table:

  the carding bot   draws its card from it, with its own hand as the only layout;
  the reader        evaluates it for the card actually played, in every candidate layout.

So a reader given a bot's descriptor and honesty has exactly the bot's model.

Situations come from public information only (`situation`). The fact a signal states (parity of
the suit, an honour in it, where the side strength is) is computed on the chooser's original
thirteen cards in a layout (`facts`). With honesty h, message form:

    P(c | S, m) = (1 - eps) [ h r(c | m, S) + (1 - h) nu(c | S) ] + eps / |S|
    nu(c | S)   = mean over the messages m' of r(c | m', S)

where S is the class (the chooser's spots two to nine in the suit; for the opening lead the
whole suit held) and r puts all its weight on the spot the message prescribes in S. A message the
holding cannot send (odd-even with no odd spot) is uniform over S. For the opening lead, r is the
lead convention's card for the holding and nu is uniform over the suit. Probabilities over S sum
to 1 in every layout, and h = 0 makes the card independent of the fact.

Card indices are 13 * suit + rank, suits S H D C, rank 0 the deuce and 12 the ace.
"""
from functools import lru_cache
from typing import Mapping

import numpy as np

VERSION = 'signals-v1'
SPOT = 7                                    # rank index of the nine: the spots are ranks 0..7
RANK = np.arange(52) % 13
SUIT_OF = np.arange(52) // 13
HCP = np.where(RANK >= 9, RANK - 8, 0).astype(np.int64)      # J 1, Q 2, K 3, A 4
SUIT_MASK = SUIT_OF[None, :] == np.arange(4)[:, None]         # [4, 52]
SPOT_MASK = SUIT_MASK & (RANK <= SPOT)[None, :]
AKQ_MASK = SUIT_MASK & (RANK >= 10)[None, :]
ODD_RANK = (RANK % 2 == 1)                  # the 3, 5, 7, 9 (and J, K): an odd number on the card
NO_TRUMP = 4

SITUATION_FIELD = {'partner_lead': 'signal_on_partner_lead', 'declarer_lead': 'signal_on_declarer_lead',
                   'first_discard': 'first_discard', 'trump': 'trump_signal'}
SUPPORTED = {'partner_lead': ('attitude', 'count', 'suit_preference'), 'declarer_lead': ('count', 'suit_preference'),
             'first_discard': ('attitude', 'count', 'lavinthal', 'odd_even'), 'trump': ('count', 'suit_preference')}
LEAD_FIELDS = ('length_lead_vs_suit', 'length_lead_vs_nt', 'lead_from_ak', 'honor_sequence_lead')
MESSAGES = {'attitude': ('like', 'dislike'), 'count': ('even', 'odd'), 'suit_preference': ('higher', 'lower'),
            'lavinthal': ('higher', 'lower'), 'odd_even': ('like', 'dislike')}


# ---- situations: public information only ---------------------------------------------------
def situation(history, i, contract):
    """(key, suit) for play i of `history` ((seat, card) pairs), or None where no carding situation applies.

    Keys: 'lead.opening'; 'partner_lead' and 'declarer_lead' (following on the first round of the suit led);
    'first_discard' (the seat's first off-suit card that is not a ruff); 'trump' (following on the first
    round of trumps). Only defenders signal; later rounds, later leads and ruffs are None."""
    seat, c = history[i]
    if seat in (contract.declarer, contract.dummy):
        return None
    if i == 0:
        return ('lead.opening', c // 13)
    start = i - i % 4
    if i == start:
        return None
    trump = contract.trump
    led_seat, led = history[start]
    led_suit = led // 13
    if c // 13 != led_suit:
        if trump != NO_TRUMP and c // 13 == trump:
            return None
        for j in range(i):
            sj, cj = history[j]
            if sj == seat and j % 4 and cj // 13 != history[j - j % 4][1] // 13 and not (trump != NO_TRUMP and cj // 13 == trump):
                return None                 # an earlier discard: this is not the first
        return ('first_discard', c // 13)
    if any(history[t][1] // 13 == led_suit for t in range(0, start, 4)):
        return None                         # not the first round of the suit
    if trump != NO_TRUMP and led_suit == trump:
        return ('trump', led_suit)
    return ('partner_lead', led_suit) if led_seat == (seat + 2) % 4 else ('declarer_lead', led_suit)


def preference_suits(kind, trump, led_suit, suit):
    """The two suits a suit-preference or Lavinthal signal chooses between, higher-ranking first, or None."""
    if kind == 'lavinthal':
        left = [x for x in range(4) if x != trump and x != suit]
        if len(left) == 3:
            left = [x for x in left if x != led_suit]
    else:
        left = [x for x in range(4) if x != trump and x != led_suit]
    return tuple(left) if len(left) == 2 else None


# ---- facts: on the chooser's original thirteen cards in each layout ------------------------
def facts(kind, original, suit, trump, led_suit):
    """[layouts] index into MESSAGES[kind] of the message the hand calls for, or None when the signal cannot apply.
    `original` is [layouts, 52] bool."""
    original = np.asarray(original, bool)
    if kind == 'count':
        return (original & SUIT_MASK[suit]).sum(axis=1) % 2
    if kind in ('attitude', 'odd_even'):
        return np.where((original & AKQ_MASK[suit]).any(axis=1), 0, 1)
    if kind in ('suit_preference', 'lavinthal'):
        pair = preference_suits(kind, trump, led_suit, suit)
        if pair is None:
            return None
        a, b = ((original & SUIT_MASK[x]) @ HCP for x in pair)
        return np.where(a > b, 0, 1)
    raise ValueError(f'unknown signal {kind}')


# ---- spot rules ----------------------------------------------------------------------------
def pick(K, rule):
    """[layouts] the card `rule` picks in each row's class K ([layouts, 52] bool), -1 where it cannot."""
    if rule == 'odd':
        K = K & ODD_RANK[None, :]
        rule = 'high'
    elif rule == 'even':
        K = K & ~ODD_RANK[None, :]
        rule = 'low'
    some = K.any(axis=1)
    if rule == 'high':
        idx = 51 - np.argmax(K[:, ::-1], axis=1)
    elif rule == 'low':
        idx = np.argmax(K, axis=1)
    else:
        raise ValueError(f'unknown spot rule {rule}')
    return np.where(some, idx, -1)


def spot_rules(kind, descriptor):
    """For each message of `kind` (in MESSAGES order) the spot rule: 'high', 'low', 'odd' or 'even'."""
    if kind == 'odd_even':
        return ('odd', 'even')
    if kind in ('suit_preference', 'lavinthal'):
        return ('high', 'low')
    direction = descriptor.get(kind, 'standard')
    if direction not in ('standard', 'upside_down'):
        raise ValueError(f'{kind} must be standard or upside_down')
    return ('high', 'low') if direction == 'standard' else ('low', 'high')


@lru_cache(maxsize=64)
def lead_table(length_field, from_ak, sequence):
    """[8192] rank index the lead convention prescribes for each 13-bit holding of the suit led (-1 if empty)."""
    out = np.full(8192, -1, np.int64)
    for mask in range(1, 8192):
        ranks = [r for r in range(12, -1, -1) if mask >> r & 1]            # high to low
        n = len(ranks)
        if n == 1:
            card = ranks[0]
        elif ranks[0] >= 8 and ranks[0] - ranks[1] == 1:                    # top two touching, the top a ten or better
            if ranks[0] == 12 and ranks[1] == 11:
                card = 11 if sequence == 'rusinow' or from_ak == 'king' else 12
            else:
                card = ranks[1] if sequence == 'rusinow' else ranks[0]
        elif n == 2:
            card = ranks[0]
        elif n == 3:
            card = ranks[2] if ranks[0] >= 9 else ranks[0]                 # low from an honour (A K Q J), top of three small
        elif length_field == '4th':
            card = ranks[3]
        elif length_field == '3rd_5th':
            card = ranks[2] if n % 2 == 0 else ranks[4]
        elif length_field == 'attitude':
            card = ranks[-1] if ranks[0] >= 9 else ranks[0]
        else:
            raise ValueError(f'unknown length lead {length_field}')
        out[mask] = card
    return out


# ---- the model ------------------------------------------------------------------------------
class SignalModel:
    """A partnership's carding descriptor plus honesty per situation key, and the probabilities they imply.

    `descriptor`: the fields of configs/systems/_carding_fields.json, or a carding block {'descriptor': {...}}.
    `honesty`: one value, or {key: value} with '*' as the default; keys are situation keys with the signal
    ('partner_lead.attitude', 'lead.opening', ...). `eps`: the floor, a share spread evenly over the class."""

    def __init__(self, descriptor, honesty=1., eps=0., emission=None):
        d = descriptor.get('descriptor', descriptor) if isinstance(descriptor, Mapping) else None
        if not isinstance(d, Mapping):
            raise ValueError('a carding descriptor is a mapping of fields')
        self.descriptor = {k: str(v) for k, v in d.items()}
        self.honesty_by_key = dict(honesty) if isinstance(honesty, Mapping) else {'*': float(honesty)}
        for v in self.honesty_by_key.values():
            if not 0 <= float(v) <= 1:
                raise ValueError('honesty is between 0 and 1')
        if not 0 <= eps < 1:
            raise ValueError('eps is in [0, 1)')
        self.eps = float(eps)
        self.emission = {}
        for key, rows in (emission or {}).items():         # {full key: [[P(low), P(high), P(middle)] for each message]}
            rows = np.asarray(rows, float)
            if rows.ndim != 2 or rows.shape[1] != 3 or (rows < 0).any() or not np.allclose(rows.sum(axis=1), 1., atol=1e-3):
                raise ValueError(f'emission for {key}: one row of P(low), P(high), P(middle) per message, each summing to 1')
            self.emission[key] = rows / rows.sum(axis=1, keepdims=True)    # rounded tables are renormalised

    def __bool__(self):
        """Active only if the descriptor declares a signalling situation or a lead convention: one that names only
        directions (attitude: standard) says nothing about which spots mean what, and readers treat it as absent."""
        return any(f in self.descriptor for f in (*SITUATION_FIELD.values(), *LEAD_FIELDS))

    def honesty(self, key):
        return float(self.honesty_by_key.get(key, self.honesty_by_key.get('*', 1.)))

    def signal(self, key):
        """What the descriptor makes of a situation: a signal kind, 'lead', 'none' (declared: no signal), or None
        (the descriptor says nothing about it; readers then fall back to the Gen 8 reading)."""
        if key == 'lead.opening':
            return 'lead' if any(f in self.descriptor for f in LEAD_FIELDS) else None
        value = self.descriptor.get(SITUATION_FIELD[key])
        if value is None:
            return None
        return value if value in SUPPORTED[key] else 'none'

    def full_key(self, key, kind):
        return key if kind == 'lead' else f'{key}.{kind}'

    def probabilities(self, key, kind, played, K, original, suit, trump, led_suit, strain_nt=False, holding=None):
        """[layouts] P(card `played` | class K, the layout's facts) for one play. K and original are [layouts, 52]
        bool; `holding` (opening lead only) is the suit held, from which the convention's card is taken (default K).
        kind 'none' (or a signal the holding cannot carry) gives 1 / |K|."""
        K = np.asarray(K, bool)
        n = K.sum(axis=1)
        if not K[:, played].all():
            raise ValueError('the card played is not in its class in every layout')
        uniform = 1. / n
        h, eps = self.honesty(self.full_key(key, kind)), self.eps
        if kind == 'lead':
            held = K if holding is None else np.asarray(holding, bool)
            bits = (held[:, suit * 13:suit * 13 + 13] * (1 << np.arange(13))).sum(axis=1)
            d = self.descriptor
            table = lead_table(d.get('length_lead_vs_nt' if strain_nt else 'length_lead_vs_suit', '4th'),
                               d.get('lead_from_ak', 'ace'), d.get('honor_sequence_lead', 'top'))
            prescribed = suit * 13 + table[bits]
            inside = K[np.arange(len(K)), np.clip(prescribed, 0, 51)] & (prescribed >= 0)
            r = np.where(inside, (prescribed == played).astype(float), uniform)
            return (1 - eps) * (h * r + (1 - h) * uniform) + eps * uniform
        message = None if kind == 'none' else facts(kind, original, suit, trump, led_suit)
        if message is None:
            return uniform
        table = self.emission.get(self.full_key(key, kind))
        if table is not None and kind != 'odd_even':
            return (1 - eps) * self.emitted(table, message, played, K) + eps * uniform
        rules = spot_rules(kind, self.descriptor)
        r = np.stack([np.where(p < 0, uniform, (p == played).astype(float)) for p in (pick(K, x) for x in rules)])   # [messages, layouts]
        told = r[message, np.arange(len(K))]
        return (1 - eps) * (h * told + (1 - h) * r.mean(axis=0)) + eps * uniform

    @staticmethod
    def emitted(table, message, played, K):
        """[layouts] P(card | class, message) under an emission table: the card's position in the class (lowest, highest,
        or one of the |K| - 2 middle cards) has probability table[message][position], shared evenly among the middle
        cards; with two cards there is no middle, and the low and high entries are renormalised."""
        n = K.sum(axis=1)
        rows = table[message]                                               # [layouts, 3]
        low, high = pick(K, 'low'), pick(K, 'high')
        position = np.where(played == low, 0, np.where(played == high, 1, 2))
        weight = rows[np.arange(len(K)), position]
        total = np.where(n >= 3, 1., rows[:, 0] + rows[:, 1])
        size = np.where(position == 2, np.maximum(n - 2, 1), 1)
        return np.where(total > 0, weight / np.maximum(total, 1e-300) / size, 1. / n)

    def distribution(self, key, kind, choices, hand, suit, trump, led_suit, strain_nt=False, holding=None):
        """{card: probability} over `choices` (the cards a bot may play) for a bot holding `hand` (its original
        thirteen cards): the same function the reader evaluates, with the bot's own hand as the only layout."""
        K = np.zeros((1, 52), bool)
        K[0, list(choices)] = True
        original = np.zeros((1, 52), bool)
        original[0, list(hand)] = True
        held = None
        if holding is not None:
            held = np.zeros((1, 52), bool)
            held[0, list(holding)] = True
        return {c: float(self.probabilities(key, kind, c, K, original, suit, trump, led_suit, strain_nt, held)[0]) for c in sorted(choices)}
