"""X9: the Gen 9 player on the 8X engine (Gen 9 tasks G9-A10, G9-A11; plan `docs/gen9/sid-integration.md` on
`feature/gen9`, sections 2.2 and 3). Work in progress; nothing here is adopted or deployed.

`X8Player` and `Gen9Player` share `Gen7Player`, and 8X's decisions read layout weights through the hooks the Gen 9
player overrides (`type_log_weights`, `layout_log_weights`, `play_log_likelihood`, all called through `self` in
`X8Player.read_layouts`). So this class runs 8X's rollouts, winning-line logic and the conditional claims below on
Gen 9's readings of the auction (profiles, card, replayed bidder) and of the cards (declared carding, honesty,
experience). With nothing declared, empty experience and `x9` off it plays exactly as the 8X bot it wraps
(tests/test_x9.py).

Composition:
- `meet`: the Gen 9 player takes a `PlayerModel` or an id; 8X keeps an id, which its `claims.opponents` and `mix.read_*`
  lists are matched against. This class gives 8X the id.
- A seat's cards are read one way. 8X pools a mixer's run of touching cards (`x8.mix.read_*`); the Gen 9 player reads a
  declared carding scheme. Where the opponent declares a carding scheme, the opponent's seats are not pooled.
- `x8.names` is unchanged (a newcomer's name from the arrival mixture: experiment E9-22).

Conditional claims (`x9` settings; `x9_conditional.py`; DESIGN.md section 6 of the conditional claims, shape level):
- **Where.** The declaring side to play with `conditional` or fewer cards, no outright claim (8X's `claim` state is not
  'guaranteed'), in games, slams and doubled contracts (`contracts`), inside an 8X rollout or blend decision.
- **Floors.** The cells and weights come from the decision's own layouts and weights (Gen 9's reading). Where a
  candidate's floor is `min_floor` or more, the rollouts' `floor0` is set for the layouts inside its certified set, so
  those layouts count as made and the rollouts value the rest and the overtricks. No blending weight.
- **Preference** (`prefer`, off by default). For the declaring side, the floors take the place of 8X's hand-over odds:
  among the stage's candidates within `prefer` tricks of the best value, the card with the highest certified floor wins
  when that floor is `min_floor` or more.
- **Commitment.** The chosen card's certified set is stored; at the declaring side's next decision of the deal, one
  question asks which cards keep the line over that set's live cells, and only those stay candidates (when some do).
  Not built: the exception for a heavier set certified at the new decision, and adding the best-floor card when the
  stage's own candidates leave it out.
- **Record.** `details['x9']` per decision where it ran: cells, weights, floors, ceilings, the card's set, timings,
  and whether it moved the card. Where it did, `capture.audit` is 'features' and `x9.fork` is on, the card the same bot plays with conditional claims off (same random stream) is named as the
  reference card, so the collector forks both.
"""
import copy
from dataclasses import asdict, dataclass, fields, replace
import random

import numpy as np

from .core import symbol
from .gen9 import Gen9Player
from .player_model import PlayerModel
from .x8_player import X8Player, game_or_doubled
from . import x9_conditional as xc

ENGINE = 'gen9x'


@dataclass(frozen=True)
class X9Config:
    conditional: int = 0        # conditional claims with this many cards or fewer in hand; 0 = off
    min_floor: float = .9       # a certified set sets floors when its weight is at least this
    mass: float = .99           # cells are taken heaviest first until this share of the layouts' weight is covered
    ms: int = 2000              # wall-clock allowance a decision for the conditional questions
    nodes: int = 2_000_000      # node cap a question (the solver's --maxnodes)
    contracts: str = 'games'    # 'games' (games, slams, doubled) or 'all'
    commit: bool = True         # keep to the chosen card's certified set at the next decisions
    fork: bool = True           # where it moved the card and capture.audit is 'features', fork against the card without it
    binary: str = ''            # the cells solver; default the environment's CELLS_BIN
    prefer: float = 0.          # among the stage's candidates within this many tricks of the best value, the highest certified
                                # floor wins when it is min_floor or more (8X's odds rule, for the declaring side); 0 = off

    def __post_init__(self):
        if not (0 <= self.conditional <= 13 and 0. <= self.min_floor <= 1. and 0. < self.mass <= 1. and self.ms > 0 and self.nodes > 0
                and self.contracts in ('games', 'all') and 0. <= self.prefer <= 13.):
            raise ValueError('Invalid X9 settings')


def x9_settings(block):
    block = dict(block or {})
    known = {f.name for f in fields(X9Config)}
    unknown = set(block) - known
    if unknown:
        raise ValueError(f'Unknown X9 settings: {sorted(unknown)}')
    return X9Config(**block)


class X9Player(X8Player, Gen9Player):
    """8X's decisions on the Gen 9 player's readings, with conditional claims."""

    def __init__(self, spec, root, reference=None):
        self.x9 = x9_settings(spec.get('x9'))
        self.cells = None
        self.commitment = None
        self.cond = None
        self.keep = None
        self.stash = None
        self.certified = None
        self.prefer_odds = None
        super().__init__(spec, root, reference)
        if self.x9.conditional:
            self.cells = xc.Cells(self.x9.binary or None, self.x9.nodes)

    def close(self):
        if self.cells is not None:
            self.cells.close()
        super().close()

    # ---- composition -----------------------------------------------------------------------------------------
    def meet(self, opponent):
        super().meet(opponent)
        self.opponent_id = opponent.id if isinstance(opponent, PlayerModel) else opponent

    def mixers(self, o):
        seats = super().mixers(o)
        model = getattr(self, 'opponent', None)
        if model is None or not getattr(model, 'carding', None):
            return seats
        return {s for s in seats if s % 2 == o.controller % 2}        # the opponent's scheme is read, not pooled

    # ---- conditional claims --------------------------------------------------------------------------------
    def conditional_applies(self, o):
        c = self.x9
        if not c.conditional or self.cells is None or o.contract is None or o.controller % 2 != o.contract.declarer % 2:
            return False
        if o.known_hands[o.contract.dummy] is None or len(o.known_hands[o.actor]) > c.conditional:
            return False
        if c.contracts == 'games' and not game_or_doubled(o.contract):
            return False
        return self.claim is None or self.claim[0] != 'guaranteed'

    def hand_overs(self, o, worlds, w, reps, rng):
        self.stash = (worlds, w)                       # first_floor, called next, needs the layouts' weights
        hand, odds, cover = super().hand_overs(o, worlds, w, reps, rng)
        self.prefer_odds = None
        if self.x9.prefer > 0 and odds is None and self.conditional_applies(o):
            got = self.certify(o, worlds, reps)
            if got is not None:
                floors = [self.rep_floor(got, x) for x in reps]
                if max(floors) >= self.x9.min_floor:
                    self.prefer_odds = np.array([1. - f for f in floors])      # 8X's odds rule: the lowest wins
                    return hand, self.prefer_odds, cover
        return hand, odds, cover

    def by_odds(self, order, value, odds, margin):
        if odds is not None and odds is self.prefer_odds and margin > 0:
            margin = self.x9.prefer
        return super().by_odds(order, value, odds, margin)

    def certify(self, o, worlds, reps):
        """The conditional questions for this decision's layouts and candidates, asked once."""
        if self.stash is None or self.stash[0] is not worlds:
            return None
        if self.certified is not None and self.certified[0] is worlds and self.certified[1] == tuple(reps):
            return self.certified[2]
        w = np.asarray(self.stash[1], np.float64)
        got = xc.decide(self.cells, o, worlds, w, reps, mass=self.x9.mass, allowance=self.x9.ms / 1000)
        self.certified = (worlds, tuple(reps), got)
        return got

    @staticmethod
    def rep_floor(got, x):
        r = got.get('rep_of', {}).get(int(x))
        return got['floor'].get(r, 0.) if r is not None and r in got['set'] else 0.

    def first_floor(self, o, worlds, reps, hand):
        floor0 = super().first_floor(o, worlds, reps, hand)
        if not self.conditional_applies(o) or self.stash is None or self.stash[0] is not worlds:
            return floor0
        got = self.certify(o, worlds, reps)
        if got is None:
            return floor0
        applied = {}
        cell = np.array(got['layout_cell'])
        for j, x in enumerate(reps):
            r = got.get('rep_of', {}).get(int(x))
            f = got['floor'].get(r, 0.)
            if r is not None and r in got['set'] and f > 0 and f >= self.x9.min_floor:
                inside = np.isin(cell, got['set'][r])
                floor0[:, j] |= inside
                applied[symbol(x)] = f
        self.cond = dict(got, applied=applied, reps=[symbol(x) for x in reps],
                         preferred=self.prefer_odds is not None)
        return floor0

    def allowed(self, o):
        base = super().allowed(o)
        if self.keep:
            kept = [x for x in base if x in self.keep]
            if kept:
                return kept
        return base

    def unconditional_card(self, o):
        """The card this bot plays here with conditional claims off, from the same random stream."""
        if getattr(self, 'unconditional_player', None) is None:
            shadow = copy.copy(self)
            shadow.x9 = replace(self.x9, conditional=0)
            shadow.reference = None
            shadow.keep = None
            self.unconditional_player = shadow
        self.unconditional_player.keep, self.unconditional_player.cond = None, None
        stream = random.Random()
        stream.setstate(self.start_state)
        return X8Player.choose(self.unconditional_player, o, stream).card

    def choose(self, o, rng):
        self.cond, self.keep, self.stash = None, None, None
        self.certified, self.prefer_odds = None, None
        kept_note = None
        if self.x9.conditional and self.x9.commit and self.commitment is not None and self.cells is not None \
                and o.contract is not None and o.controller % 2 == o.contract.declarer % 2 and len(o.legal) > 1:
            live = xc.live_cells(self.commitment, o)
            if live is None:
                self.commitment = None
            elif live:
                keep = xc.keeping(self.cells, o, live)
                if keep and len(keep) < len(o.legal):
                    self.keep = keep
                kept_note = dict(live=len(live), keep=sorted(symbol(x) for x in keep) if keep else [])
        result = super().choose(o, rng)
        if self.cond is None and kept_note is None:
            return result
        d = dict(result.details)
        note = dict(kept=kept_note)
        if self.cond is not None:
            got = self.cond
            chosen = got.get('rep_of', {}).get(int(result.card))
            f = got['floor'].get(chosen, 0.) if chosen is not None else 0.
            note.update(cells=got['cells'], weight=got['weight'], covered=got['covered'], reps=got['reps'],
                        floor={symbol(k): v for k, v in got['floor'].items()}, ceiling={symbol(k): v for k, v in got['ceiling'].items()},
                        applied=got['applied'], chosen_floor=f, queries=got['queries'], seconds=got['seconds'], complete=got['complete'],
                        preferred=got.get('preferred', False))
            if f >= self.x9.min_floor and self.x9.commit:
                pos = xc.position(o)
                self.commitment = dict(history=tuple((int(a), int(b)) for a, b in o.history), side=o.controller % 2, east=pos[1],
                                       cells=[tuple(got['cells'][i]) for i in got['set'][chosen]]) if pos else None
            elif self.keep is None:
                self.commitment = None
        acted = bool((self.cond or {}).get('applied')) or self.keep is not None or bool((self.cond or {}).get('preferred'))
        if acted:
            plain = self.unconditional_card(o)
            note['moved'] = plain != result.card
            cap = self.x8.capture
            if note['moved'] and self.reference and cap.audit == 'features' and self.x9.fork:
                for key in ('reference_card', 'expected_gain_imps', 'prediction_units'):
                    d.pop(key, None)
                d.update(reference_card=symbol(plain), expected_gain_imps=None, prediction_units='x9-against-no-conditional',
                         x8_features=sorted(set(d.get('x8_features') or []) | {'conditional'}))
        d['x9'] = note
        return type(result)(result.card, d)


def player(spec, root, reference=None):
    return X9Player(spec, root, reference)
