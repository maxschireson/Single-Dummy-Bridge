"""The card factor: a declared card's evidence about a hidden hand, for a layout pool (Gen 9 WIP).

For every call a seat made in a context its card covers, the likelihood of that call under a
noisy reading of the card's rules:

    P(call | hand) = (1 - eps) * [first satisfied rule == call] + eps * softmax_rules(-lam * dist)[call]

The first term carries both the call's own meaning and the negative inference (the hand did
not satisfy any higher-priority rule); eps is how often this seat departs from its card in
this family of calls. A context the card does not cover, or a call the card does not list
there, contributes nothing: the net keeps everything past the declared layer.

``CardFactor.type_log_score`` has FitScorer's signature, so a player combines the two as
``a * scorer + b * card`` over the same hand types.
"""
import numpy as np

from .context import Context
from .features import hand_features
from .system import CardSystem

DEFAULT_EPS = 0.05
DEFAULT_LAM = 1.5


class Deviation:
    """eps per family of calls, for one seat (a player): a Beta posterior over agree/deviate counts."""

    def __init__(self, prior_eps=DEFAULT_EPS, prior_weight=20.0, counts=None):
        self.prior_eps, self.prior_weight = float(prior_eps), float(prior_weight)
        self.counts = dict(counts or {})              # family -> [agree, deviate]

    def eps(self, family):
        a, d = self.counts.get(family, (0, 0))
        k = self.prior_weight
        return (d + k * self.prior_eps) / (a + d + k)

    def observe(self, family, agreed):
        c = self.counts.setdefault(family, [0, 0])
        c[0 if agreed else 1] += 1

    def to_dict(self):
        return {'prior_eps': self.prior_eps, 'prior_weight': self.prior_weight, 'counts': self.counts}


def call_log_prob(rules, call, f, eps, lam=DEFAULT_LAM, exhaustive=True):
    """log P(call | hand) for feature arrays f under a context's rules; None if the card does not list the call.
    With exhaustive=False a hand that fits no rule is uninformative (log P = 0)."""
    calls = [r.call for r in rules]
    if call not in calls:
        return None
    n = len(f['hcp'])
    dist = np.stack([r.pred.dist(f) for r in rules])                     # (rules, n)
    sat = dist == 0
    first = np.where(sat.any(0), sat.argmax(0), len(rules) - 1)
    # rules sharing a call: the call is made if any of them is the first satisfied
    idx = [i for i, c in enumerate(calls) if c == call]
    hit = np.isin(first, idx)
    z = -lam * dist
    z = z - z.max(0, keepdims=True)
    soft = np.exp(z)
    soft = soft / soft.sum(0, keepdims=True)
    q = soft[idx].sum(0)
    lp = np.log((1 - eps) * hit + eps * q + 1e-300)
    if not exhaustive:
        lp = np.where(sat.any(0), lp, 0.0)
    return lp


class NoCard:
    """The filter when nothing is declared: exactly zero for every hand type."""
    exhaustive = True

    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction):
        return np.zeros(len(np.asarray(length).reshape(-1, 4)))

    def seat_terms(self, auction, dealer, seat, vulnerability):
        return []


def make_filter(card=None, deviation=None):
    """The rule filter for a declared card, or NoCard when nothing is declared."""
    return NoCard() if card is None else CardFactor(card, deviation)


class CardFactor:
    """log P(a seat's calls | its hand) under that seat's card, for hand types."""

    def __init__(self, card, deviation=None, lam=DEFAULT_LAM):
        """card: a card (id, path, dict, Card), a CardSystem, or anything with rules(ctx) (e.g. RuleBidderMeanings)."""
        self.system = card if hasattr(card, 'rules') else CardSystem(card)
        self.exhaustive = getattr(self.system, 'exhaustive', True)
        self.dev = deviation or Deviation()
        self.lam = lam
        self.covered = self.listed = 0

    def seat_terms(self, auction, dealer, seat, vulnerability):
        """(turn index, context, rules) for each call `seat` made in a covered context."""
        out = []
        calls = list(auction)
        for t in range(len(calls)):
            if (dealer + t) % 4 != seat:
                continue
            ctx = Context.make(calls[:t], dealer, seat, vulnerability)
            rules = self.system.rules(ctx)
            if rules is not None:
                out.append((t, ctx, rules))
        return out

    def log_score_features(self, f, seat, dealer, vulnerability, auction, explain=False):
        total = np.zeros(len(f['hcp']))
        parts = []
        calls = [Context.make(auction, dealer, seat).calls][0]
        for t, ctx, rules in self.seat_terms(calls, dealer, seat, vulnerability):
            fam = next((r.family for r in rules if r.call == calls[t]), None)
            if fam is None:
                parts.append((t, calls[t], None))
                continue
            lp = call_log_prob(rules, calls[t], f, self.dev.eps(fam), self.lam, self.exhaustive)
            total += lp
            parts.append((t, calls[t], fam))
        return (total, parts) if explain else total

    def type_log_score(self, length, hon, seat, dealer, vulnerability, auction):
        """Same signature as gen6_nets.FitScorer.type_log_score."""
        return self.log_score_features(hand_features(length, hon), seat, dealer, vulnerability, auction)

    def observe_board(self, hand_types, dealer, vulnerability, auction, seats=None):
        """After a board, with the hands known: count, per family, whether each covered call was the card's call."""
        out = []
        calls = Context.make(auction, dealer, 0).calls
        for seat in (seats if seats is not None else range(4)):
            length, hon = hand_types[seat]
            f = hand_features(np.asarray(length)[None], np.asarray(hon)[None])
            for t, ctx, rules in self.seat_terms(calls, dealer, seat, vulnerability):
                listed = [r for r in rules if r.call == calls[t]]
                fam = listed[0].family if listed else rules[0].family
                first = next((r for r in rules if r.pred.dist(f)[0] == 0), None)
                if first is None:                   # a non-exhaustive table the hand fits nowhere: no evidence
                    continue
                agreed = first.call == calls[t]
                self.dev.observe(fam, agreed)
                out.append((seat, t, calls[t], first.call, fam, agreed))
        return out


def covered(card_or_filter, auction, dealer, seat, vulnerability):
    """Turn indices of `seat`'s calls in `auction` that the card covers."""
    f = card_or_filter if hasattr(card_or_filter, 'seat_terms') else make_filter(card_or_filter)
    return [t for t, _, _ in f.seat_terms(auction, dealer, seat, vulnerability)]
