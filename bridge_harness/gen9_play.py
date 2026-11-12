"""Gen 9 card play (prototype): carding bots and the signal reader, on the Gen 7 player.

Gen 9 work in progress (G9-S2; design: docs/gen9/signals.md). Used by no arena bot.

A spec with `engine: gen9` is a Gen 7 spec plus a `gen9` block (Gen9Config). Two independent parts:

  Carding bot.  With `carding`, the bot signals by that descriptor among the cards its search rates
                as exactly equal: the class is chosen as the house bot chooses (the net's likeliest
                tied card); if it is a spot (or the opening lead's suit) and two or more cards of its
                class are tied, the card is drawn from signals.SignalModel with the bot's own hand.
                Honours, declarer's and dummy's cards, and situations the descriptor does not cover
                are left to the Gen 7 tie-break.

  Reader.       A hidden defender whose partnership's PlayerModel has a carding descriptor (the
                opponents, through `models` and `meet`; partner, with `read_partner`) is read as

                    phi * log P_net(class of the card)  +  log P_signal(card | class, layout's facts)

                instead of Gen 8's phi * log P_net(card). Declarer's and dummy's cards, plain models
                and models without carding are read exactly as Gen 8 reads them.

With an empty `gen9` block the player is the Gen 7 player it is built on, card for card (tested).
`play_log_terms` returns the net part and the signal part apart (proposed addition to interface I5),
so a caller can temper the net alone; `play_log_likelihood` returns their sum, as Gen 7's does.
"""
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Mapping

import numpy as np

from .core import card, symbol
from .gen7 import BIT, Gen7Player, hidden_plays
from .player_model import resolve
from .players import Decision
from .signals import SPOT, SPOT_MASK, SUIT_MASK, SignalModel, situation

ENGINE = 'gen9'
DEFAULT_HONESTY = .8                # a declared card with no honesty and no experience is read at this
_FIELDS = None


def carding_fields():
    global _FIELDS
    if _FIELDS is None:
        path = Path(__file__).resolve().parents[1] / 'configs' / 'systems' / '_carding_fields.json'
        _FIELDS = {k: tuple(v) for k, v in json.loads(path.read_text())['fields'].items()}
    return _FIELDS


def check_descriptor(descriptor):
    fields = carding_fields()
    for k, v in descriptor.items():
        if k not in fields or str(v) not in fields[k]:
            raise ValueError(f'carding {k}={v!r} is not in configs/systems/_carding_fields.json')


def carding_parts(block, default_honesty=DEFAULT_HONESTY):
    """(descriptor, honesty) from a carding block {'descriptor': {...}, 'honesty': h or {key: h}} or a bare descriptor."""
    if not block:
        return {}, default_honesty
    block = dict(block)
    descriptor = dict(block['descriptor']) if 'descriptor' in block else {k: v for k, v in block.items() if k not in ('honesty', 'phi', 'notes')}
    check_descriptor(descriptor)
    return descriptor, block.get('honesty', default_honesty)


@dataclass(frozen=True)
class Gen9Config:
    carding: Mapping | None = None      # this bot's own carding block: it signals by it
    signal_eps: float = 0.              # the bot's floor: share of its signalling choices made uniformly in the class
    signal_margin: float = 0.           # class cards within this many tricks of the best count as equal for signalling; 0 = exact ties
    models: Mapping = field(default_factory=dict)   # {bot id or '*': player-model document}: what is known about an opponent
    read_partner: bool = False          # read partner's spots by this bot's own carding (both play it)
    reader_eps: float = .05             # the reader's floor on the signal term

    def __post_init__(self):
        if not 0 <= self.signal_eps < 1 or not 0 <= self.reader_eps < 1 or not 0 <= self.signal_margin <= 13:
            raise ValueError('Invalid Gen9 settings')
        if self.read_partner and not self.carding:
            raise ValueError('read_partner needs the bot\'s own carding')
        carding_parts(self.carding)
        for m in self.models.values():
            carding_parts(dict(m).get('carding'))


class Gen9Player(Gen7Player):
    def __init__(self, spec, root, reference=None):
        self.g9 = Gen9Config(**(spec.get('gen9') or {}))
        descriptor, honesty = carding_parts(self.g9.carding, 1.)
        self.own_signals = SignalModel(descriptor, honesty, eps=self.g9.signal_eps) or None
        self.partner_signals = (SignalModel(descriptor, honesty, eps=self.g9.reader_eps) or None) if self.g9.read_partner else None
        self.opponent_model, self.opponent_signals, self.opponent_phi = None, None, None
        self.class_cache = (None, {})
        super().__init__(spec, root, reference)

    # ---- who sits against us ---------------------------------------------------------------
    def meet(self, opponent):
        model = resolve(opponent, self.g9.models)
        super().meet(None if opponent is None else model.id)
        self.opponent_model = model
        descriptor, honesty = carding_parts(model.carding)
        self.opponent_signals = SignalModel(descriptor, honesty, eps=self.g9.reader_eps) or None
        phi = (model.carding or {}).get('phi') if model.carding else None
        self.opponent_phi = self.opponent_factor if phi is None else float(phi)

    def reader_for(self, o, chooser):
        """(SignalModel, factor on the class term) for a hidden chooser read by its carding, or None for Gen 8's reading."""
        if chooser == o.contract.declarer:
            return None
        if chooser % 2 == o.controller % 2:
            return (self.partner_signals, 1.) if self.partner_signals else None
        return (self.opponent_signals, self.opponent_phi) if self.opponent_signals else None

    # ---- reading ---------------------------------------------------------------------------
    def play_log_terms(self, o, view, assign, plays=None):
        """([layouts] the net's part, [layouts] the signal part) of the log-likelihood of the hidden plays so far."""
        plays = hidden_plays(o, self.g7.play_lead) if plays is None else plays
        readers = [self.reader_for(o, chooser) for _, _, chooser in plays]
        if all(r is None for r in readers):
            return Gen7Player.play_log_likelihood(self, o, view, assign, plays), np.zeros(len(assign))
        rest = [p for p, r in zip(plays, readers) if r is None]
        net = Gen7Player.play_log_likelihood(self, o, view, assign, rest) if rest else np.zeros(len(assign))
        signal = np.zeros(len(assign))
        for play, reader in zip(plays, readers):
            if reader is not None:
                model, phi = reader
                part, sig = self.signal_row(o, view, assign, *play, model)
                net = net + phi * part
                signal = signal + sig
        return net, signal

    def play_log_likelihood(self, o, view, assign, plays=None):
        net, signal = self.play_log_terms(o, view, assign, plays)
        return net + signal

    def signal_row(self, o, view, assign, i, seat, chooser, model):
        """([layouts] log P_net(class), [layouts] log P_signal(card | class)) for one play by a chooser read by `model`."""
        c = o.contract
        played = o.history[i][1]
        suit = played // 13
        sit = situation(o.history, i, c)
        key = sit[0] if sit else 'none'
        kind = model.signal(key) if sit else 'none'
        held = self.held_then(o, view, assign, i, chooser)
        if kind is None or (played % 13 > SPOT and key != 'lead.opening'):
            K = np.zeros_like(held)
            K[:, played] = True
        else:
            K = held & (SUIT_MASK[suit] if key == 'lead.opening' else SPOT_MASK[suit])[None, :]
        log_class = self.class_log_probabilities(o, view, assign, i, seat, chooser, held, K, played)
        if kind is None or K.sum(axis=1).max() < 2:
            return log_class, np.zeros(len(assign))
        original = view.original(assign, view.hidden.index(chooser)).astype(bool)
        start = i - i % 4
        led_suit = o.history[start][1] // 13
        p = model.probabilities(key, kind, played, K, original, suit, c.trump, led_suit, c.trump == 4)
        return log_class, np.log(p)

    def class_log_probabilities(self, o, view, assign, i, seat, chooser, held, K, played):
        """[layouts] log of the floored net probability of the play's class (Gen 8's floor, card by card); 0 if forced."""
        c = o.contract
        ident = (o.auction, o.dealer, o.vulnerability, c, o.original_hand(c.dummy))
        if self.class_cache[0] != ident:
            self.class_cache = (ident, {})
        cache = self.class_cache[1]
        prefix = tuple(o.history[:i + 1])
        keys = held.astype(np.uint64) @ BIT            # what the chooser held then, and which of it is the class
        kmask = K.astype(np.uint64) @ BIT
        entry = cache.get(i)
        if entry is None or entry[0] != prefix:
            entry = (prefix, {})
            cache[i] = entry
        known = entry[1]
        out = np.zeros(len(assign))
        todo = []
        for row, (h, k) in enumerate(zip(keys.tolist(), kmask.tolist())):
            v = known.get((h, k))
            if v is None:
                todo.append(row)
            else:
                out[row] = v
        if todo:
            batch = self.play_arrays(o, i, seat, chooser, held[todo])
            legal = np.asarray(batch['legal'])
            if not legal[:, played].all():
                raise RuntimeError('A listed layout makes an observed play illegal')
            count = legal.sum(axis=1)
            fresh = np.zeros(len(todo))
            choice = count > 1
            if choice.any():
                rows = np.flatnonzero(choice)
                logp = self.net.log_policy_arrays({k: batch[k][rows] for k in batch})
                self.net_rows += len(rows)
                p = np.exp(logp.astype(np.float64)) * legal[rows]
                f = self.g7.play_floor
                members = K[np.array(todo)[rows]]
                mass = (1 - f) * (p * members).sum(axis=1) + f * members.sum(axis=1) / count[rows]
                fresh[rows] = np.log(mass)
            for j, row in enumerate(todo):
                out[row] = fresh[j]
                known[(int(keys[row]), int(kmask[row]))] = fresh[j]
        return out

    # ---- signalling ------------------------------------------------------------------------
    def break_ties(self, o, rng, result):
        if self.own_signals is None:
            return super().break_ties(o, rng, result)
        c = o.contract
        if o.actor != o.controller or o.actor % 2 == c.declarer % 2:
            return super().break_ties(o, rng, result)
        d = result.details
        tied = sorted(card(k) for k, p in d['behavior_probabilities'].items() if p > 0)
        if not tied:
            return super().break_ties(o, rng, result)
        logp = self.net.log_policy([o])[0]
        first = max(tied, key=lambda x: (float(logp[x]), -x))                  # the class, as the house bot would choose it
        i = len(o.history)
        sit = situation(o.history + ((o.actor, first),), i, c)
        kind = self.own_signals.signal(sit[0]) if sit else 'none'
        key = sit[0] if sit else 'none'
        suit = first // 13
        if kind is None:
            return super().break_ties(o, rng, result)
        if key == 'lead.opening':
            members = [x for x in o.legal if x // 13 == suit]
        elif first % 13 <= SPOT:
            members = [x for x in o.legal if x // 13 == suit and x % 13 <= SPOT]
        else:
            return super().break_ties(o, rng, result)
        estimates = d.get('estimates') or {}
        margin = self.g9.signal_margin
        choices = [x for x in members if x in tied or (margin > 0 and estimates.get(symbol(x), {}).get('gap_to_best', 99.) <= margin + 1e-9)]
        if len(choices) < 2:
            return super().break_ties(o, rng, result)
        hand = o.original_hand(o.actor)
        led_suit = o.trick[0][1] // 13 if o.trick else suit
        holding = [x for x in hand if x // 13 == suit] if key == 'lead.opening' else None
        dist = self.own_signals.distribution(key, kind, choices, hand, suit, c.trump, led_suit, c.trump == 4, holding)
        ticket = rng.random()
        chosen = choices[-1]
        for x in sorted(dist):
            ticket -= dist[x]
            if ticket <= 0:
                chosen = x
                break
        gap = estimates.get(symbol(chosen), {}).get('gap_to_best')
        return Decision(chosen, dict(d, selector=f'carding-{self.own_signals.full_key(key, kind)}-{self.spec["id"]}',
                                     proposal_probabilities=d['behavior_probabilities'],
                                     behavior_probabilities={symbol(x): dist.get(x, 0.) for x in o.legal},
                                     selected_probability=dist[chosen], selected_pimc_gap=gap,
                                     gen9_signal=dict(key=key, kind=kind, choices=len(choices), class_size=len(members))))

    def choose(self, o, rng):
        result = super().choose(o, rng)
        if 'gen6' in result.details or 'gen7' in result.details:
            note = dict(version='gen9-play-v0', signals=self.own_signals is not None, read_partner=self.partner_signals is not None,
                        read_opponents=self.opponent_signals is not None)
            return Decision(result.card, dict(result.details, gen9=note))
        return result


def player(spec, root, reference=None):
    return Gen9Player(spec, root, reference)
