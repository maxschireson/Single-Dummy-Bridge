"""Gen 9 player shell: the Gen 8 prototype player, reading calls and cards through a model of
whoever made them.

Design in progress (docs/gen9/architecture.md, sections 4 and 7). Used by no arena bot; the
arena's collector runtime does not know the engine name 'gen9'.

The search, the tree and every setting of Gen 7 and the Gen 8 prototype are unchanged. What
changes is how a candidate layout is weighted, at the two places the Gen 8 player already has:

  type_log_weights      calls. For a partnership whose PlayerModel is not plain, the hand-fit
                        score becomes a mixture over that partnership's profiles, taken over
                        the whole board: log sum_k p_k * exp(sum over its seats of S_k), its
                        visible hands included, plus `card_weight` times the term of a reader
                        built from its declared card (the rule filter). A plain partnership is
                        scored exactly as before.
  play_log_likelihood   cards. Handed to a card-play reader when the spec names one; otherwise
                        Gen 8's reading, with the opponent's play factor taken from experience
                        when there is enough of it.

Two facts are told to the player by whoever runs the table:

  meet(opponent)        who plays the cards against it (already called by gen5_arena.run_board):
                        a PlayerModel, or a bot id resolved against spec['gen9']['players'].
  auction_by(bidders)   who made the calls at this table, four models or ids in seat order. Not
                        called: each side bid for itself. In a common auction all four are the
                        common bidder.

spec['gen9'], every key optional:

  players          {bot id: player model as a dict}; '*' is the default entry
  own              this bot's own partnership as a player model (its declared carding, say)
  bidding_reader   'module:callable'. Called as f(model, other_model, root) for a partnership
                   that declared a bidding card; returns an object with FitScorer's
                   type_log_score(length, hon, seat, dealer, vulnerability, auction), or None.
  play_reader      'module:callable'. Called once as f(player); returns an object with
                   play_log_likelihood(player, o, view, assign, plays), or None.
  max_profiles, card_weight, factor_min_plays, factor_prior_plays      Gen9Config
  oracle           TEST ONLY: tilt the layout weights toward the true deal (experiment E9-0).
                   Refused unless BRIDGE_ALLOW_ORACLE=1, and the deal must be shown with peek().

With no 'gen9' block, or one whose models are all plain and which names no reader, the player
is the Gen 8 prototype player card for card (tests/test_gen9_player.py).
"""
from dataclasses import asdict, dataclass
import importlib
import math
import os

import numpy as np

from . import experience as xp
from .gen7 import Gen7Player, floored, hidden_plays
from .gen7 import player as gen7_player
from .player_model import PlayerModel, resolve

ENGINE = 'gen9'
CONFIG_KEYS = ('max_profiles', 'card_weight', 'factor_min_plays', 'factor_prior_plays')
BLOCK_KEYS = CONFIG_KEYS + ('players', 'own', 'bidding_reader', 'play_reader', 'oracle')


@dataclass(frozen=True)
class Gen9Config:
    max_profiles: int = 4           # profiles kept in the mixture, most probable first
    card_weight: float = 1.         # factor on the declared card's term; 0 = the card is not read
    factor_min_plays: float = 200.  # occasions of the 'play.info' statistic before experience sets the opponent's play factor
    factor_prior_plays: float = 50. # shrinkage of each factor's mean gain toward zero, as this many occasions

    def __post_init__(self):
        if isinstance(self.max_profiles, bool) or not isinstance(self.max_profiles, int) or not 1 <= self.max_profiles <= 16 \
                or not 0 <= self.card_weight <= 8 or self.factor_min_plays < 1 or self.factor_prior_plays < 0:
            raise ValueError('Invalid Gen9 settings')


@dataclass(frozen=True)
class Oracle:
    """Test only. `tilt` nats are added to the true layout's log weight ('inf': it gets all the weight)."""
    tilt: float = 0.
    roles: str = 'both'             # 'both' | 'declarer' | 'defender': whose decisions are tilted
    from_trick: int = 1
    to_trick: int = 13

    def __post_init__(self):
        if self.roles not in ('both', 'declarer', 'defender') or not 1 <= self.from_trick <= self.to_trick <= 13 \
                or not (self.tilt == math.inf or 0 <= self.tilt <= 50):
            raise ValueError('Invalid oracle settings')


def gen9_settings(block):
    """spec['gen9'] -> (Gen9Config, the rest of the block)."""
    block = dict(block or {})
    extra = set(block) - set(BLOCK_KEYS)
    if extra:
        raise ValueError(f'Unknown Gen9 settings: {sorted(extra)}')
    return Gen9Config(**{k: block[k] for k in CONFIG_KEYS if k in block}), block


def _factory(name):
    module, _, attr = str(name).partition(':')
    if not module or not attr:
        raise ValueError(f"a reader is named 'module:callable', not {name!r}")
    return getattr(importlib.import_module(module), attr)


def _logsumexp(rows):
    stacked = np.stack(rows)
    top = stacked.max(axis=0)
    return top + np.log(np.exp(stacked - top).sum(axis=0))


class Gen9Player(Gen7Player):
    """Gen7Player (with the Gen 8 prototype's settings) whose layout weights read each partnership's model."""

    def __init__(self, spec, root, reference=None):
        self.g9, block = gen9_settings(spec.get('gen9'))
        self.models = dict(block.get('players') or {})
        own = block.get('own')
        self.own = PlayerModel.from_dict(dict(own, id=own.get('id', str(spec.get('id', 'own'))))) if own else PlayerModel(str(spec.get('id', 'own')), 'house')
        self.opponent, self.bidders = PlayerModel('unknown'), None
        self.readers = {}
        self.deal = None
        self.oracle = None
        if block.get('oracle'):
            if os.environ.get('BRIDGE_ALLOW_ORACLE') != '1':
                raise ValueError('An oracle bot is given the deal. It is for experiments only: set BRIDGE_ALLOW_ORACLE=1 to build one.')
            tilt = block['oracle'].get('tilt', 0.)
            self.oracle = Oracle(**dict(block['oracle'], tilt=math.inf if tilt in ('inf', math.inf) else float(tilt)))
        self.bidding_factory = _factory(block['bidding_reader']) if block.get('bidding_reader') else None
        super().__init__(spec, root, reference)             # ends by calling meet(spec.get('table_opponent'))
        self.root = root
        # the unbound system scorer, to read a partnership under each of its candidate systems
        self.system_scorer, self.table_systems = None, tuple(spec.get('table_systems') or (None, None))
        if spec.get('system_scorer'):
            from pathlib import Path
            from .system_nets import SystemFitScorer
            self.system_scorer = SystemFitScorer(Path(root) / spec['system_scorer'])
        self.play_reader = _factory(block['play_reader'])(self) if block.get('play_reader') else None

    # ---- what the table tells the player -----------------------------------------------------
    def meet(self, opponent):
        """Who plays the cards against this bot: a PlayerModel, a bot id, or None."""
        super().meet(opponent.id if isinstance(opponent, PlayerModel) else opponent)     # Gen 8's factor by bot id
        self.opponent = resolve(opponent, self.models)
        self.bidders = None
        stat = self.opponent.stat('play.info')
        if stat is not None and stat['n'] >= self.g9.factor_min_plays:      # enough boards against them: their own best factor
            self.opponent_factor = float(xp.grid_best(stat, prior_n=self.g9.factor_prior_plays)[0])

    def auction_by(self, bidders):
        """Who made the calls at this table: four PlayerModels or ids, seats N E S W. None = each side bid for itself."""
        if bidders is None:
            self.bidders = None
            return
        if len(bidders) != 4:
            raise ValueError('auction_by takes four bidders in seat order')
        self.bidders = tuple(resolve(b, self.models) for b in bidders)

    def peek(self, hands):
        """TEST ONLY: the four original hands, for an oracle bot. Anything else refuses it."""
        if self.oracle is None:
            raise ValueError('Only an oracle bot may be shown the deal')
        self.deal = tuple(tuple(sorted(int(c) for c in h)) for h in hands)

    def bidder_of(self, o, seat):
        """The model of whoever made `seat`'s calls."""
        if self.bidders is not None:
            return self.bidders[seat]
        return self.own if seat % 2 == o.controller % 2 else self.opponent

    # ---- calls ---------------------------------------------------------------------------------
    def card_reader(self, model, other):
        """The reader built from a partnership's declared bidding card, or None."""
        if self.bidding_factory is None or model.bidding is None or self.g9.card_weight <= 0:
            return None
        key = (model.id, model.snapshot, other.id, other.snapshot)
        if key not in self.readers:
            if len(self.readers) >= 32:
                self.readers.clear()
            self.readers[key] = self.bidding_factory(model, other, self.root)
        return self.readers[key]

    def profile_scorer(self, side, system):
        """The hand-fit scorer if side `side` (0 = NS, 1 = EW) plays `system`. Without a system-aware scorer file
        every profile is read alike, by the player's own scorer."""
        if self.system_scorer is None:
            return self.scorer
        from .systems import TableSystems
        systems = list(self.table_systems)
        systems[side] = system
        return self.system_scorer.bind(TableSystems(*systems))

    def read_calls(self, o, model, other, side, seats, length, hon):
        """Log weight of side `side`'s hidden hands (seats: [(index into view.hidden, seat)]) given its calls:
        the mixture over its profiles carried through the board, its visible hands included, plus the card's term."""
        profiles = sorted(model.profiles, key=lambda sp: -sp[1])[:self.g9.max_profiles]
        total = sum(p for _, p in profiles)
        hidden = {seat for _, seat in seats}
        seen = [s for s in (side, side + 2) if s not in hidden and o.known_hands[s] is not None]
        rows = []
        for system, p in profiles:
            scorer = self.profile_scorer(side, system)
            row = sum(scorer.type_log_score(length[j], hon[j], seat, o.dealer, o.vulnerability, o.auction) for j, seat in seats)
            for s in seen:                              # a hand of theirs we can see says which system they are playing
                member = np.zeros((1, 52), np.int8)
                member[0, list(o.original_hand(s))] = 1
                row = row + float(scorer.seat_log_score(member, s, o.dealer, o.vulnerability, o.auction)[0])
            rows.append(math.log(p / total) + row)
        out = rows[0] if len(rows) == 1 else _logsumexp(rows)
        reader = self.card_reader(model, other)
        if reader is not None:
            out = out + self.g9.card_weight * sum(reader.type_log_score(length[j], hon[j], seat, o.dealer, o.vulnerability, o.auction)
                                                  for j, seat in seats)
        return out

    def type_log_weights(self, o, view, length, hon, source):
        if source == 'lead_net':                        # the lead net knows only the house system; Gen 8 routes other tables to the scorer
            return super().type_log_weights(o, view, length, hon, source)
        by_side = {}
        for j, seat in enumerate(view.hidden):
            by_side.setdefault(seat % 2, []).append((j, seat))
        models = {side: self.bidder_of(o, seats[0][1]) for side, seats in by_side.items()}
        if all(m.plain for m in models.values()):
            return super().type_log_weights(o, view, length, hon, source)
        total = 0.
        for side, seats in by_side.items():
            model = models[side]
            if model.plain:
                total = total + sum(self.scorer.type_log_score(length[j], hon[j], seat, o.dealer, o.vulnerability, o.auction) for j, seat in seats)
            else:
                other = self.bidder_of(o, (seats[0][1] + 1) % 4)
                total = total + self.read_calls(o, model, other, side, seats, length, hon)
        return total

    # ---- cards ---------------------------------------------------------------------------------
    def play_fit(self, o, view, assign, plays):
        """([plays, layouts] floored log-probability of each hidden play under the house net, before any factor;
        [plays, layouts] how many legal cards the chooser had). For card-play readers."""
        logp, options = self.play_log_probabilities(o, view, assign, plays)
        return floored(logp, options, self.g7.play_floor), options

    def play_log_likelihood(self, o, view, assign, plays=None):
        if self.play_reader is None:
            return super().play_log_likelihood(o, view, assign, plays)
        plays = hidden_plays(o, self.g7.play_lead) if plays is None else plays
        return self.play_reader.play_log_likelihood(self, o, view, assign, plays)

    # ---- the test-only oracle --------------------------------------------------------------------
    def tilted(self, o, worlds, weights):
        """(worlds, weights, note) with the true layout's weight multiplied by exp(tilt); it is added if absent."""
        c, k = o.contract, self.oracle
        declaring = o.controller % 2 == c.declarer % 2
        trick = len(o.history) // 4 + 1
        if (k.roles == 'declarer' and not declaring) or (k.roles == 'defender' and declaring) or not k.from_trick <= trick <= k.to_trick:
            return worlds, weights, None
        if self.deal is None:
            raise RuntimeError('An oracle bot was not shown the deal (peek)')
        gone = {x for _, x in o.history}
        truth = tuple(tuple(x for x in hand if x not in gone) for hand in self.deal)
        for s, hand in enumerate(o.known_hands):
            if hand is not None and tuple(hand) != truth[s]:
                raise RuntimeError('The deal shown to the oracle is not the deal being played')
        worlds = [tuple(tuple(int(x) for x in h) for h in w) for w in worlds]
        w = np.asarray(weights, np.float64)
        w = w / w.sum()
        present = truth in worlds
        if present:
            i = worlds.index(truth)
            before = float(np.log(w[i]))
        else:
            i, before = len(worlds), float(np.log(1. / len(worlds)))        # taken in at the pool's mean weight
            worlds, w = worlds + [truth], np.append(w, 1. / len(w))
        if k.tilt == math.inf:
            w = np.zeros(len(w))
            w[i] = 1.
        else:
            w[i] *= math.exp(k.tilt)
            w = w / w.sum()
        return worlds, w, dict(tilt='inf' if k.tilt == math.inf else k.tilt, present=present, log_weight_before=before,
                               log_weight_after=float(np.log(w[i])), layouts=len(worlds))

    def layouts(self, o, view, source, rng):
        worlds, weights, info = super().layouts(o, view, source, rng)
        if self.oracle is not None:
            worlds, weights, note = self.tilted(o, worlds, weights)
            if note is not None:
                self.solved_layouts = worlds
                info = dict(info, oracle=note)
        return worlds, weights, info

    def choose(self, o, rng):
        result = super().choose(o, rng)
        if 'gen6' in result.details and not (self.opponent.plain and self.own.plain and self.bidders is None):
            result.details['gen9'] = dict(asdict(self.g9), opponent=self.opponent.id, opponent_boards=self.opponent.boards,
                                          snapshot=self.opponent.snapshot, opponent_factor=self.opponent_factor)
        return result


def player(spec, root, reference=None):
    """player_factory for gen5_arena.run_board: Gen 9 specs get this engine, every other spec is as before."""
    if spec.get('engine') == ENGINE:
        return Gen9Player(spec, root, reference)
    return gen7_player(spec, root, reference)
