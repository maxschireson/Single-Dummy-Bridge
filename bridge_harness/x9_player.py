"""X9: the Gen 9 player on the 8X engine (Gen 9 task G9-A10; plan `docs/gen9/sid-integration.md` on `feature/gen9`,
section 2.2). Work in progress; nothing here is adopted or deployed.

`X8Player` and `Gen9Player` share `Gen7Player`, and 8X's decisions read layout weights through the hooks the Gen 9
player overrides (`type_log_weights`, `layout_log_weights`, `play_log_likelihood`, all called through `self` in
`X8Player.read_layouts`). So this class runs 8X's rollouts, winning-line logic and, once they are built, conditional
claims and the tree, on Gen 9's readings of the auction (profiles, card, replayed bidder) and of the cards (declared
carding, honesty, experience). With nothing declared and empty experience it plays exactly as the 8X bot it wraps
(tests/test_x9.py).

Three points of composition:
- `meet`: the Gen 9 player takes a `PlayerModel` or an id; 8X keeps an id, which its `claims.opponents` and `mix.read_*`
  lists are matched against. This class gives 8X the id.
- A seat's cards are read one way. 8X pools a mixer's run of touching cards (`x8.mix.read_*`); the Gen 9 player reads a
  declared carding scheme. Where the opponent declares a carding scheme, the opponent's seats are not pooled, so the
  scheme is read; otherwise 8X's pooling stands. Partner's seat is 8X's to decide, as before.
- `x8.names` (who each side is, for a rollout net that takes names) is unchanged. A newcomer's name taken from the
  arrival mixture's profile is a later step (experiment E9-22).
"""
from .gen9 import Gen9Player
from .player_model import PlayerModel
from .x8_player import X8Player

ENGINE = 'gen9x'


class X9Player(X8Player, Gen9Player):
    """8X's decisions on the Gen 9 player's readings."""

    def meet(self, opponent):
        super().meet(opponent)
        self.opponent_id = opponent.id if isinstance(opponent, PlayerModel) else opponent

    def mixers(self, o):
        seats = super().mixers(o)
        model = getattr(self, 'opponent', None)
        if model is None or not getattr(model, 'carding', None):
            return seats
        return {s for s in seats if s % 2 == o.controller % 2}        # the opponent's scheme is read, not pooled


def player(spec, root, reference=None):
    return X9Player(spec, root, reference)
