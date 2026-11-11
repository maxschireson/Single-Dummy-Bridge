"""Gen7 card play (prototype): the Gen6 search, reading the Gen7 policy net.

Everything Gen6 does with the auction is unchanged: layouts still come from the lead net, the
hand-fit scorer and the deal list, and DDS still ranks the cards. The policy net (gen7_net.py,
trained to predict Gen6's own card from one seat's view) is read in three places:

  1. Play weights.  From the trick where every card-fit layout is listed, each layout's scorer
     weight is multiplied by how likely the hidden seats' plays so far were if that layout were
     true: the product, over every past card chosen by a seat the decider cannot see, of the
     net's probability of that card given what that seat saw in that layout (its own hand,
     dummy, the play to that point), raised to `play_weight`. A defender's hidden choosers are
     partner and declarer (declarer also chose dummy's cards); declarer's are both defenders.
     The list holds every layout, so this is the exact posterior under the net, tempered.
  2. Ties.          Among exactly tied cards the net's most probable card is played, in place
                    of the Gen5 policy net.
  3. No search.     Tricks before `search_from_trick` are played from the net alone. Meant for
                    fast data tables (the opening lead and tricks 1-2 are about 90% of Gen6's
                    search time); those cards carry no search estimates and are not training
                    examples.

With play_weight 0, tie_break 'gen5' and search_from_trick 1 the player is Gen6, card for card
and draw for draw (tested).

A hypothetical seat's view is built from the decider's Observation and the layout only
(`past_view`); the test suite checks it against the Observation the game itself would have
given that seat.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
import random

import numpy as np

from .core import Observation, card, symbol, winner
from .gen6 import POLICY_SAMPLE_RANGE, Gen6Player, _effective, systematic
from .gen6 import player as gen6_player
from .gen7_net import INPUTS, PolicyNet
from .players import Decision

ENGINE = 'gen7'
BIT = np.uint64(1) << np.arange(52, dtype=np.uint64)
SUIT = np.arange(52)[None, :] // 13 == np.arange(4)[:, None]


@dataclass(frozen=True)
class Gen7Config:
    play_weight: float = .5         # exponent on the net's probability of each observed play; 0 = Gen6's weights
    play_floor: float = .05         # each play's probability is mixed with this share of uniform over the legal cards
    play_max_layouts: int = 1024    # a longer deal list is resampled by scorer weight to this many before the net scores it
    play_lead: bool = True          # the opening lead counts as a play
    tie_break: str = 'net'          # among exactly tied cards: 'net' | 'gen5' (the spec's policy net, as Gen6)
    search_from_trick: int = 1      # earlier tricks are played from the net without search; 1 = always search
    net_sample: bool = False        # unsearched cards: draw from the net's policy instead of taking its top card

    def __post_init__(self):
        if self.tie_break not in ('net', 'gen5') or not 0 <= self.play_weight <= 4 or not 0 <= self.play_floor < 1 \
                or not 1 <= self.search_from_trick <= 14 or not 1 <= self.play_max_layouts <= 100000:
            raise ValueError('Invalid Gen7 settings')


def hidden_plays(o, lead=True):
    """Past plays chosen by a seat whose hand the controller cannot see: (history index, seat, chooser)."""
    c = o.contract
    out = []
    for i, (seat, _) in enumerate(o.history):
        chooser = c.declarer if seat == c.dummy else seat
        if chooser != o.controller and (i or lead):
            out.append((i, seat, chooser))
    return out


def floored(logp, options, floor):
    """log of the probability mixed with `floor` of uniform over the legal cards; 0 where the card was forced."""
    return np.where(options > 1, np.log((1 - floor) * np.exp(logp) + floor / np.maximum(options, 1)), 0.)


def past_view(o, i, hand=()):
    """The Observation the chooser of play i had, if it then held `hand`.

    Everything else is public and comes from `o`: the play before i, dummy as it then was, the
    auction. With hand=() it is the part of that view which is the same in every layout.
    """
    c = o.contract
    seat = o.history[i][0]
    chooser = c.declarer if seat == c.dummy else seat
    start = i - i % 4
    trick = tuple(o.history[start:i])
    won = sum(winner(o.history[t:t + 4], c.trump) % 2 == c.declarer % 2 for t in range(0, start, 4))
    known = [None] * 4
    known[chooser] = tuple(sorted(hand))
    if i:                                           # dummy goes down after the opening lead
        known[c.dummy] = tuple(sorted(set(o.known_hands[c.dummy]) | {x for s, x in o.history[i:] if s == c.dummy}))
    cards = known[seat]
    follow = [x for x in cards if x // 13 == trick[0][1] // 13] if trick else []
    return Observation(chooser, seat, tuple(known), tuple(follow or cards), tuple(o.history[:i]), trick,
                       trick[0][0] if trick else seat, c, o.dealer, o.vulnerability, o.auction, won)


class Gen7Player(Gen6Player):
    """Gen6Player whose deal-list weights, tie-breaks and (optionally) early tricks read the Gen7 net."""

    def __init__(self, spec, root, reference=None):
        super().__init__(spec, root, reference)
        self.g7 = Gen7Config(**spec.get('gen7', {}))
        self.net = PolicyNet(Path(root) / spec['gen7_policy'], self.scorer)
        self.play_cache = (None, {})
        self.net_rows = 0

    # ---- how likely was the play so far, layout by layout --------------------------------
    def held_then(self, o, view, assign, i, chooser):
        """[layouts, 52] the cards `chooser` held just before play i: its cards in the layout plus what it has played since."""
        held = np.zeros((len(assign), 52), bool)
        held[:, view.unseen] = assign == view.hidden.index(chooser)
        held[:, [x for s, x in o.history[i:] if s == chooser]] = True
        return held

    def play_arrays(self, o, i, seat, chooser, held):
        """Net inputs for the chooser's view at play i in each layout (one row per row of `held`)."""
        base = self.net.encode(past_view(o, i))
        n = len(held)
        batch = {k: np.broadcast_to(base[k], (n, *base[k].shape)) for k in INPUTS}
        state = batch['state'].copy()
        state[held] = 1
        batch['state'] = state
        if seat == chooser:                         # a card from the hidden hand itself: follow suit if it could
            if i % 4:
                in_suit = held & SUIT[o.history[i - i % 4][1] // 13]
                batch['legal'] = np.where(in_suit.any(axis=1)[:, None], in_suit, held)
            else:
                batch['legal'] = held
        return batch

    def play_log_probabilities(self, o, view, assign, plays=None):
        """([plays, layouts] the net's log-probability of each hidden chooser's past play, given what that seat saw in
        that layout; [plays, layouts] how many legal cards it had). A forced card scores 0."""
        plays = hidden_plays(o, self.g7.play_lead) if plays is None else plays
        c = o.contract
        ident = (o.auction, o.dealer, o.vulnerability, c, o.original_hand(c.dummy))
        if self.play_cache[0] != ident:
            self.play_cache = (ident, {})
        cache = self.play_cache[1]
        logp, options = np.zeros((len(plays), len(assign))), np.ones((len(plays), len(assign)), np.int64)
        for row, (i, seat, chooser) in enumerate(plays):
            played = o.history[i][1]
            held = self.held_then(o, view, assign, i, chooser)
            masks = held.astype(np.uint64) @ BIT
            prefix = tuple(o.history[:i + 1])
            keys, values, counts = cache[i][1:] if i in cache and cache[i][0] == prefix else \
                (np.zeros(0, np.uint64), np.zeros(0), np.zeros(0, np.int64))
            where = np.searchsorted(keys, masks).clip(max=max(0, len(keys) - 1))
            known = keys[where] == masks if len(keys) else np.zeros(len(masks), bool)
            logp[row, known], options[row, known] = values[where[known]], counts[where[known]]
            if not known.all():
                batch = self.play_arrays(o, i, seat, chooser, held[~known])
                legal = np.asarray(batch['legal'])
                if not legal[:, played].all():
                    raise RuntimeError('A listed layout makes an observed play illegal')
                count = legal.sum(axis=1)
                fresh = np.zeros(len(count))
                choice = count > 1
                if choice.any():
                    fresh[choice] = self.net.log_policy_arrays({k: batch[k][choice] for k in INPUTS})[:, played]
                    self.net_rows += int(choice.sum())
                logp[row, ~known], options[row, ~known] = fresh, count
                keys, values, counts = np.concatenate([keys, masks[~known]]), np.concatenate([values, fresh]), np.concatenate([counts, count])
                order = np.argsort(keys)
                cache[i] = (prefix, keys[order], values[order], counts[order])
        return logp, options

    def play_log_likelihood(self, o, view, assign, plays=None):
        """[layouts] sum over the hidden choosers' past plays of the floored log-probability of the card played."""
        logp, options = self.play_log_probabilities(o, view, assign, plays)
        return floored(logp, options, self.g7.play_floor).sum(axis=0)

    def layouts(self, o, view, source, rng):
        g = self.g7
        if source != 'list' or g.play_weight <= 0:
            return super().layouts(o, view, source, rng)
        c = self.config
        assign = view.every()
        logw = self.layout_log_weights(o, view, assign)
        info = dict(listed=len(assign), effective=_effective(logw))
        plays = hidden_plays(o, g.play_lead)
        if len(assign) > g.play_max_layouts:
            index, share = systematic(np.exp(logw - logw.max()), g.play_max_layouts, rng)
            assign, logw = assign[index], np.log(share)
        rows = self.net_rows
        logw = logw + g.play_weight * self.play_log_likelihood(o, view, assign, plays)
        info.update(play_decisions=len(plays), play_layouts=len(assign), play_net_rows=self.net_rows - rows,
                    effective_with_play=_effective(logw))
        w = np.exp(logw - logw.max())
        if c.list_solve and len(assign) > c.list_solve:
            index, weights = systematic(w, c.list_solve, rng)
        else:
            index, weights = np.arange(len(assign)), w / w.sum()
        return [view.world(assign[i]) for i in index], weights, info

    # ---- one decision --------------------------------------------------------------------
    def choose(self, o, rng):
        if len(o.legal) > 1 and len(o.history) // 4 + 1 < self.g7.search_from_trick:
            return self.net_decision(o, rng)
        result = super().choose(o, rng)
        if 'gen6' not in result.details:
            return result
        return Decision(result.card, dict(result.details, gen7=asdict(self.g7)))

    def net_decision(self, o, rng):
        """A card straight from the net: no layouts, no DDS, no estimates."""
        logp = self.net.log_policy([o])[0]
        p = np.exp(logp[list(o.legal)].astype(np.float64))
        p /= p.sum()
        if self.g7.net_sample:
            ticket, k = rng.random(), 0
            for k, share in enumerate(p):
                ticket -= share
                if ticket <= 0:
                    break
            behaviour = {symbol(x): float(q) for x, q in zip(o.legal, p)}
        else:
            k = int(np.argmax(p))
            behaviour = {symbol(x): float(j == k) for j, x in enumerate(o.legal)}
        chosen = o.legal[k]
        return Decision(chosen, dict(samples=0, dds_calls=0, unsearched=True, behavior_probabilities=behaviour,
            selected_probability=behaviour[symbol(chosen)], net_probabilities={symbol(x): float(q) for x, q in zip(o.legal, p)},
            gen7=dict(asdict(self.g7), source='net', trick=len(o.history) // 4 + 1)))

    def break_ties(self, o, rng, result):
        """Gen6Player.break_ties with the Gen7 net's log-probability in place of the Gen5 net's prediction."""
        if self.g7.tie_break != 'net':
            return super().break_ties(o, rng, result)
        d = result.details
        eligible = sorted(card(k) for k, p in d['behavior_probabilities'].items() if p > 0)
        if len(eligible) < 2:
            return result
        logp = self.net.log_policy([o])[0]
        values = {x: float(logp[x]) for x in eligible}
        best = max(values.values())
        ties = {x for x, v in values.items() if best - v <= 1e-7}
        epsilon = self.spec.get('exploration', 0.)
        probs = {x: epsilon / len(values) + (1 - epsilon) * (x in ties) / len(ties) for x in values}
        ticket = rng.random()
        for chosen, probability in sorted(probs.items()):
            ticket -= probability
            if ticket <= 0:
                break
        details = dict(d, selector='gen7-net-' + self.spec['id'], proposal_probabilities=d['behavior_probabilities'],
            behavior_probabilities={symbol(x): p for x, p in probs.items()}, selected_probability=probs[chosen],
            selector_predictions={symbol(x): v for x, v in values.items()},
            selected_pimc_gap=d['estimates'][symbol(chosen)]['gap_to_best'])
        if self.reference:
            seen = dict(d, samples=min(max(d['samples'], POLICY_SAMPLE_RANGE[0]), POLICY_SAMPLE_RANGE[1]))
            reference_rng = random.Random()
            reference_rng.setstate(rng.getstate())
            ref, _ = self.reference.choose(o, seen, reference_rng)
            details.update(reference_card=symbol(ref), expected_gain_imps=None, prediction_units='log-policy-probability')
        return Decision(chosen, details)


def player(spec, root, reference=None):
    """player_factory for gen5_arena.run_board: Gen7 specs get this engine, every other spec is as before."""
    if spec.get('engine') == ENGINE:
        return Gen7Player(spec, root, reference)
    return gen6_player(spec, root, reference)
