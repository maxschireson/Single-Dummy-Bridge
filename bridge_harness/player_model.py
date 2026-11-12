"""What a bot is told about a partnership it sits with or against.

Gen 9 design in progress (interface I3 of docs/gen9/architecture.md). Used by no arena bot.

A PlayerModel has three layers, general to specific:

  profiles    probability over known ways of bidding and carding (system ids of the Gen 8
              registry; None is "unknown"). One system holds for a whole board, so readers mix
              over profiles outside the product over seats and calls.
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
from dataclasses import dataclass, field
from typing import Mapping

from . import experience as xp

KINDS = ('house', 'anchor', 'synthetic', 'outside', 'guest', 'unknown')
UNKNOWN_PROFILE = ((None, 1.0),)


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
