"""Gen 9 player: the Gen 8 prototype player, reading calls and cards through a model of
whoever made them.

Design in progress (docs/gen9/architecture.md, sections 4 and 7). Used by no arena bot; the
arena's collector runtime does not know the engine name 'gen9'.

The search, the tree and every setting of Gen 7 and the Gen 8 prototype are unchanged. What
changes is how a candidate layout is weighted, at the two places the Gen 8 player already has,
and which of its exactly tied cards a bot with declared carding plays:

  type_log_weights      calls. For a partnership whose PlayerModel is not plain, the hand-fit
                        score becomes a mixture over that partnership's profiles, taken over
                        the whole board: log sum_k p_k * exp(sum over its seats of row_k), its
                        visible hands included. For a net profile row_k is that profile's
                        scorer plus the declared card's term on the contexts where the card
                        departs from the profile; for the reserved profile 'card' it is the
                        card's term alone, with no scorer. A plain partnership is scored
                        exactly as before.
  play_log_likelihood   cards. The layer below (gen9_play.SignalPlayer) splits the reading of
                        a defender with declared carding into the net's part (which class of
                        card) and the signal's part (which spot). Here the signal part is kept
                        out of the caller's exponent; without declared carding it is Gen 8's
                        reading, with the opponent's play factor taken from experience when
                        there is enough of it.
  break_ties            a bot with its own declared carding signals by it (SignalPlayer).

Two facts are told to the player by whoever runs the table:

  meet(opponent)        who plays the cards against it (already called by gen5_arena.run_board):
                        a PlayerModel, or a bot id resolved against spec['gen9']['models'].
  auction_by(bidders)   who made the calls at this table, four models or ids in seat order. Not
                        called: each side bid for itself. In a common auction all four are the
                        common bidder.

spec['gen9'], every key optional:

  models           {bot id: player model as a dict}; '*' is the default entry
  own              this bot's own partnership as a player model (what it has declared about
                   its bidding; its carding is the `carding` key)
  carding, signal_eps, signal_margin, read_partner, reader_eps      gen9_play.SignalConfig
  bidding_reader   'module:callable'. Called as f(model, other_model, root) for a partnership
                   that declared a bidding card; returns an object with FitScorer's
                   type_log_score(length, hon, seat, dealer, vulnerability, auction), which may
                   also take profile=<system id> to return only the part on that profile's
                   residual contexts; or None.
  max_profiles, card_weight, factor_min_plays, factor_prior_plays      Gen9Config
  oracle           TEST ONLY: tilt the layout weights toward the true deal (experiment E9-0).
                   Refused unless BRIDGE_ALLOW_ORACLE=1, and the deal must be shown with peek().

With no 'gen9' block, or one whose models are all plain and which declares no carding, the
player is the Gen 8 prototype player card for card (tests/test_gen9_player.py).
"""
from dataclasses import asdict, dataclass
import importlib
import inspect
import math
import os

import numpy as np

from . import experience as xp
from .gen6_nets import hand_types
from .gen7 import player as gen7_player
from .gen9_play import SIGNAL_KEYS, SignalPlayer
from .player_model import PlayerModel, resolve

ENGINE = 'gen9'
CONFIG_KEYS = ('max_profiles', 'card_weight', 'factor_min_plays', 'factor_prior_plays')
BLOCK_KEYS = CONFIG_KEYS + SIGNAL_KEYS + ('own', 'bidding_reader', 'oracle')
CARD_PROFILE = 'card'                 # the reserved profile: the declared card's rules alone, no scorer
RANK_WEIGHT = np.array([0.5] * 8 + [1.0, 1.5, 2.0, 3.0, 4.0])      # by rank, 2 to ace: how much a misplaced card counts (gen6.CARD_WEIGHT)


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
    """Test only: two ways of telling the bot more about the true deal than its readers do.

    tilt      the true layout itself is put among the layouts the search solves, at exp(tilt) times their mean
              weight ('inf': it gets all the weight, so the bot plays double dummy).
    near      every layout of the pool the readers weigh (after the opening lead) is multiplied by
              exp(-near * distance), distance = the cards it places in the wrong hidden hand, counted by rank
              (2-9: 0.5, T: 1, J: 1.5, Q: 2, K: 3, A: 4). This is where a real reader acts: belief moves toward
              layouts like the true one, and the true one is never handed over. The realised gain in the true
              layout's log weight is recorded with each decision."""
    tilt: float = 0.
    near: float = 0.
    roles: str = 'both'             # 'both' | 'declarer' | 'defender': whose decisions are helped
    from_trick: int = 1
    to_trick: int = 13

    def __post_init__(self):
        if self.roles not in ('both', 'declarer', 'defender') or not 1 <= self.from_trick <= self.to_trick <= 13 \
                or not (self.tilt == math.inf or 0 <= self.tilt <= 50) or not 0 <= self.near <= 10:
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


class Gen9Player(SignalPlayer):
    """The Gen 8 prototype player whose layout weights read each partnership's model (calls here, cards in SignalPlayer)."""

    def __init__(self, spec, root, reference=None):
        self.g9, block = gen9_settings(spec.get('gen9'))
        self.models = dict(block.get('models') or {})
        own = dict(block.get('own') or {})
        if block.get('carding') and 'carding' not in own:
            own['carding'] = block['carding']
        self.own = PlayerModel.from_dict(dict(own, id=own.get('id', str(spec.get('id', 'own'))), kind=own.get('kind', 'house')))
        self.opponent, self.bidders = PlayerModel('unknown'), None
        self.readers = {}
        self.deal = None
        self.oracle = None
        self.near_note = None
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

    # ---- what the table tells the player -----------------------------------------------------
    def meet(self, opponent):
        """Who plays the cards against this bot: a PlayerModel, a bot id, or None."""
        super().meet(opponent)                              # SignalPlayer: resolves the model, its carding, Gen 8's factor by bot id
        self.opponent = self.opponent_model
        self.bidders = None
        stat = self.opponent.stat('play.info')
        if stat is not None and stat['n'] >= self.g9.factor_min_plays:      # enough boards against them: their own best factor
            self.opponent_factor = float(xp.grid_best(stat, prior_n=self.g9.factor_prior_plays)[0])
            carding = self.opponent.carding or {}
            if carding.get('phi') is None:
                self.opponent_phi = self.opponent_factor

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
            reader = self.bidding_factory(model, other, self.root)
            takes = reader is not None and 'profile' in inspect.signature(reader.type_log_score).parameters
            self.readers[key] = (reader, takes)
        return self.readers[key]

    def profile_scorer(self, side, system):
        """The hand-fit scorer if side `side` (0 = NS, 1 = EW) plays `system`. Without a system-aware scorer file
        every net profile is read alike, by the player's own scorer."""
        if self.system_scorer is None:
            return self.scorer
        from .systems import TableSystems
        systems = list(self.table_systems)
        systems[side] = system
        return self.system_scorer.bind(TableSystems(*systems))

    def read_calls(self, o, model, other, side, seats, length, hon):
        """Log weight of side `side`'s hidden hands (seats: [(index into view.hidden, seat)]) given its calls: the
        mixture over its profiles carried through the board, its visible hands included.

        A net profile's row is its scorer, plus the card's term on that profile's residual contexts when the reader can
        give it. The profile 'card' is the card's term alone. A reader that cannot restrict itself to a profile's
        residual is applied in full to net profiles only when 'card' is not among the candidates."""
        profiles = sorted(model.profiles, key=lambda sp: -sp[1])[:self.g9.max_profiles]
        total = sum(p for _, p in profiles)
        hidden = {seat for _, seat in seats}
        seen = []
        for s in (side, side + 2):                      # a hand of theirs we can see says which system they are playing
            if s not in hidden and o.known_hands[s] is not None:
                member = np.zeros((1, 52), np.int8)
                member[0, list(o.original_hand(s))] = 1
                seen.append((s, member, hand_types(member)))
        reader, takes_profile = self.card_reader(model, other) or (None, False)
        card_only = any(system == CARD_PROFILE for system, _ in profiles)
        where = (o.dealer, o.vulnerability, o.auction)

        def card_term(seat, ln, hn, profile):
            if reader is None:
                return 0.
            if profile is None or not takes_profile:
                return self.g9.card_weight * reader.type_log_score(ln, hn, seat, *where)
            return self.g9.card_weight * reader.type_log_score(ln, hn, seat, *where, profile=profile)

        rows = []
        for system, p in profiles:
            row = math.log(p / total)
            if system == CARD_PROFILE:                  # the rules alone; with no reader this profile says nothing about the hands
                for j, seat in seats:
                    row = row + card_term(seat, length[j], hon[j], None)
                for s, _, (ln, hn) in seen:
                    row = row + float(np.asarray(card_term(s, ln, hn, None)).reshape(-1)[0]) if reader is not None else row
            else:
                scorer = self.profile_scorer(side, system)
                with_card = reader is not None and (takes_profile or not card_only)
                for j, seat in seats:
                    row = row + scorer.type_log_score(length[j], hon[j], seat, *where)
                    if with_card:
                        row = row + card_term(seat, length[j], hon[j], system)
                for s, member, (ln, hn) in seen:
                    row = row + float(scorer.seat_log_score(member, s, *where)[0])
                    if with_card:
                        row = row + float(np.asarray(card_term(s, ln, hn, system)).reshape(-1)[0])
            rows.append(row + np.zeros(len(length[seats[0][0]])))
        return rows[0] if len(rows) == 1 else _logsumexp(rows)

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
    def reading_exponent(self, o, view):
        """The exponent the caller is about to put on play_log_likelihood: Gen 7's on the deal list, Gen 8's before it."""
        return self.g7.play_weight if self.source(o, view) == 'list' else self.g7.early_play_weight

    def play_log_likelihood(self, o, view, assign, plays=None):
        net, signal = self.play_log_terms(o, view, assign, plays)
        out = net
        if signal.any():                # the signal part is a likelihood, not a net score: not tempered
            out = out + signal / max(self.reading_exponent(o, view), 1e-6)
        if self.oracle is not None and self.oracle.near > 0 and self.helped(o):
            out = out + self.nearness(o, view, assign) / max(self.reading_exponent(o, view), 1e-6)
        return out

    # ---- the test-only oracle --------------------------------------------------------------------
    def helped(self, o):
        """Does the oracle apply to this decision (its roles and tricks)?"""
        k = self.oracle
        declaring = o.controller % 2 == o.contract.declarer % 2
        trick = len(o.history) // 4 + 1
        return not ((k.roles == 'declarer' and not declaring) or (k.roles == 'defender' and declaring)) and k.from_trick <= trick <= k.to_trick

    def truth(self, o):
        """The four hands as they are now, from the deal the oracle was shown."""
        if self.deal is None:
            raise RuntimeError('An oracle bot was not shown the deal (peek)')
        gone = {x for _, x in o.history}
        truth = tuple(tuple(x for x in hand if x not in gone) for hand in self.deal)
        for s, hand in enumerate(o.known_hands):
            if hand is not None and tuple(hand) != truth[s]:
                raise RuntimeError('The deal shown to the oracle is not the deal being played')
        return truth

    def nearness(self, o, view, assign):
        """[layouts] -near * (rank-weighted count of unseen cards a layout puts in the wrong hidden hand)."""
        truth = self.truth(o)
        owner = np.full(52, -1, np.int8)
        for j, seat in enumerate(view.hidden):
            owner[list(truth[seat])] = j
        right = owner[view.unseen]
        if (right < 0).any():
            raise RuntimeError('The deal shown to the oracle does not account for every unseen card')
        distance = (assign != right[None, :]) @ RANK_WEIGHT[view.unseen % 13]
        term = -self.oracle.near * distance
        # what this does for the true layout among these rows, taken at equal weight: log(1 / mean exp(term))
        self.near_note = dict(near=self.oracle.near, rows=len(assign), mean_distance=float(distance.mean()),
                              gain=float(-np.log(np.mean(np.exp(term)))))
        return term

    def tilted(self, o, worlds, weights):
        """(worlds, weights, note) with the true layout's weight multiplied by exp(tilt); it is added if absent."""
        k = self.oracle
        if not self.helped(o) or (k.tilt == 0 and k.near > 0):
            return worlds, weights, None
        truth = self.truth(o)
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
        self.near_note = None
        worlds, weights, info = super().layouts(o, view, source, rng)
        if self.oracle is not None:
            worlds, weights, note = self.tilted(o, worlds, weights)
            if note is not None:
                self.solved_layouts = worlds
                info = dict(info, oracle=note)
            if self.near_note is not None:
                info = dict(info, oracle_near=self.near_note)
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
