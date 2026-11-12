"""What a bot is told about a partnership it sits with or against.

Gen 9 design in progress (interface I3 of docs/gen9/architecture.md). Used by no arena bot.

A PlayerModel has three layers, general to specific:

  profiles    probability over known ways of bidding and carding (system ids of the Gen 8
              registry; None is "unknown", read as Gen 8 reads a pair it knows nothing about).
              One system holds for a whole board, so readers mix over profiles outside the
              product over seats and calls. Two ids are reserved: 'card' (the declared card's
              rules alone, no scorer) and 'flat' (the calls say nothing about the hands).
  card        what the partnership declared: `bidding` (a card IR document, read by the bidding
              reader) and `carding` (a carding descriptor over configs/systems/_carding_fields.json,
              read by the card-play reader). Public agreements.
  experience  an experience-v1 snapshot (experience.py): additive statistics of what this
              partnership did on finished boards, frozen at an epoch boundary.

Nothing in a PlayerModel concerns the board being played. It is public agreements plus our own
notes from earlier boards, so handing it to a player does not cross the information boundary
that Observation guards.

The table contract. The board runner already tells a player who it faces: `meet(opponent)`
(gen5_arena.run_board, Gen 8 prototype). In Gen 9 `opponent` is a PlayerModel, or a bot id as
before, which a Gen 9 player resolves through `resolve()` against the models named in its own
spec. A player works out which side is which from the seat it is asked to play, so one model per
opposing partnership is enough.
"""
import math
from dataclasses import dataclass, field, replace
from typing import Mapping

from . import experience as xp

KINDS = ('house', 'anchor', 'synthetic', 'outside', 'guest', 'unknown')
UNKNOWN_PROFILE = ((None, 1.0),)
CARD_PROFILE = 'card'                 # reserved: the declared card's rules alone, no scorer
FLAT_PROFILE = 'flat'                 # reserved: the calls say nothing about the hands
PROFILE_STAT = 'profile'              # experience: summed log-likelihood of the pair's calls on its own hands, by candidate


def _profiles(value):
    """((system id or None, probability), ...), probabilities positive and summing to 1, no id twice."""
    if value is None:
        return UNKNOWN_PROFILE
    items = list(value.items()) if isinstance(value, Mapping) else [tuple(x) for x in value]
    out = []
    for system, p in items:
        system = None if system in (None, 'unknown') else str(system)
        p = float(p)
        if p < 0:
            raise ValueError('a profile probability is negative')
        if p > 0:
            out.append((system, p))
    if not out or len({s for s, _ in out}) != len(out):
        raise ValueError('profiles need at least one entry and no system twice')
    total = sum(p for _, p in out)
    if abs(total - 1.) > 1e-6:
        raise ValueError(f'profile probabilities sum to {total}, not 1')
    return tuple(sorted(((s, p / total) for s, p in out), key=lambda sp: (sp[0] is None, sp[0] or '')))


@dataclass(frozen=True)
class PlayerModel:
    id: str
    kind: str = 'unknown'
    profiles: tuple = UNKNOWN_PROFILE
    bidding: Mapping | None = None          # card IR for the auction, or None when nothing was declared
    carding: Mapping | None = None          # carding descriptor, or None
    experience: Mapping | None = None       # experience-v1 snapshot, or None
    notes: tuple = field(default_factory=tuple)

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError('a player model needs an id')
        if self.kind not in KINDS:
            raise ValueError(f'kind must be one of {KINDS}')
        object.__setattr__(self, 'profiles', _profiles(self.profiles))
        if self.experience is not None:
            xp.check(self.experience)
            if 'applied' in self.experience:
                raise ValueError('a player model carries a snapshot, not the live store')

    # ---- what readers ask -----------------------------------------------------------------
    @property
    def plain(self):
        """Nothing declared, nothing learned: readers must treat this player exactly as Gen 8 does."""
        return self.profiles == UNKNOWN_PROFILE and self.bidding is None and self.carding is None and not self.boards

    @property
    def boards(self):
        return int((self.experience or {}).get('boards', 0))

    @property
    def snapshot(self):
        return (self.experience or {}).get('snapshot')

    def stat(self, name):
        """One named statistic of the experience snapshot, or None."""
        return ((self.experience or {}).get('stats') or {}).get(name)

    def profile_ids(self):
        return tuple(s for s, _ in self.profiles)

    # ---- documents ------------------------------------------------------------------------
    @classmethod
    def from_dict(cls, d):
        extra = set(d) - {'id', 'kind', 'profiles', 'bidding', 'carding', 'experience', 'notes'}
        if extra:
            raise ValueError(f'unknown keys in a player model: {sorted(extra)}')
        return cls(d['id'], d.get('kind', 'unknown'), d.get('profiles'), d.get('bidding'), d.get('carding'),
                   d.get('experience'), tuple(d.get('notes') or ()))

    def to_dict(self):
        out = dict(id=self.id, kind=self.kind, profiles=[['unknown' if s is None else s, p] for s, p in self.profiles])
        for key in ('bidding', 'carding', 'experience'):
            if getattr(self, key) is not None:
                out[key] = dict(getattr(self, key))
        if self.notes:
            out['notes'] = list(self.notes)
        return out


def resolve(opponent, models=None):
    """The PlayerModel for whatever `meet` was given: a PlayerModel as is; a bot id looked up in
    `models` ({id: PlayerModel or its dict}, '*' as the default entry); otherwise a plain model,
    which every reader treats as Gen 8 treats an opponent it knows only by id."""
    if isinstance(opponent, PlayerModel):
        return opponent
    name = 'unknown' if opponent is None else str(opponent)
    entry = (models or {}).get(name, (models or {}).get('*'))
    if entry is None:
        return PlayerModel(name)
    if isinstance(entry, PlayerModel):
        return entry
    return PlayerModel.from_dict(dict(entry, id=entry.get('id', name)))


def arrive(id, kind='guest', bidding=None, carding=None, distances=None, tau=0.05, slack=0.15, flat=0.25, least=1e-3, notes=()):
    """The model of a partnership nobody has met, from what it declared (architecture 3, "arrival").

    distances   {system id: the rate at which that system's own bidder breaks the declared card's
                rules, over the calls the card covers} for every system we can read
                (cards.match.card_distance). With no card declared, pass the systems with any
                value: they then share the weight equally.

    The prior over profiles, before normalising: 1 for 'card' when a card is declared;
    max(exp(-max(d - slack, 0) / tau), least) for each system (equal weights with no card);
    `flat` for 'flat'. `slack` is how far a player is from the best card that can be written
    for it: a house net breaks the card fitted to that very net on about 15% of covered calls
    (bill, 12 Nov), so a system within `slack` of the declared card is as likely as the card.
    Every system keeps some weight so that boards can overturn the mapping (`believed`); the
    reader keeps only the most probable few. tau, slack, flat and least are first settings,
    not fitted. Nothing declared and no systems named gives the plain model."""
    if tau <= 0 or slack < 0 or flat < 0 or least < 0:
        raise ValueError('tau must be positive; slack, flat and least not negative')
    weights = {}
    for system, d in (distances or {}).items():
        if system in (None, 'unknown', CARD_PROFILE, FLAT_PROFILE):
            raise ValueError(f'{system!r} is not a system a distance can be given for')
        if not 0 <= float(d) <= 1:
            raise ValueError('a distance is a rate between 0 and 1')
        weights[str(system)] = max(math.exp(-max(float(d) - slack, 0.) / tau), least) if bidding is not None else 1.
    if bidding is not None:
        weights[CARD_PROFILE] = 1.
    if not weights:
        return PlayerModel(id, kind, None, bidding, carding, None, tuple(notes))
    if flat > 0:
        weights[FLAT_PROFILE] = float(flat)
    total = sum(weights.values())
    return PlayerModel(id, kind, {k: v / total for k, v in weights.items() if v > 0}, bidding, carding, None, tuple(notes))


def believed(model, temper=1., floor=0.02):
    """`model` with its profile probabilities moved by its experience: the statistic 'profile'
    holds, for each candidate, the summed log-likelihood of the partnership's calls on its own
    hands over the boards of the snapshot (cards.match.board_loglik; 'flat' is a model of the
    calls that does not look at the hand).

    A candidate the statistic has not scored keeps its prior share, and the scored ones divide
    theirs by the evidence. `temper` below 1 slows the update; `floor` is a share of the scored
    mass spread evenly over the scored candidates, so that the mixture never drops one that a
    misspecified likelihood ruled out. A model with the unknown profile, or with nothing scored,
    comes back as it is."""
    stat = model.stat(PROFILE_STAT)
    if not stat or not stat.get('n') or any(s is None for s, _ in model.profiles):
        return model
    prior = dict(model.profiles)
    scored = {s: p for s, p in prior.items() if s in stat['ll']}
    if len(scored) < 2:
        return model
    share = sum(scored.values())
    post = xp.posterior(dict(stat, ll={s: stat['ll'][s] for s in scored}), {s: p / share for s, p in scored.items()},
                        temper=temper, floor=floor)
    out = {s: share * post[s] if s in post else p for s, p in prior.items()}
    total = sum(out.values())
    return replace(model, profiles={s: p / total for s, p in out.items() if p > 0})
