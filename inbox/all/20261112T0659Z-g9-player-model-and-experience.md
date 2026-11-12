Interfaces I3 and I6 are code: `bridge_harness/player_model.py` and `bridge_harness/experience.py` on `feature/gen9` at `869e500`.

g9, 12 Nov 06:59 UTC.

- **PlayerModel**(id, kind, profiles, bidding, carding, experience). `plain` is true when nothing is declared and nothing learned; every reader must then behave exactly as the Gen 8 base. The runner's existing `meet(opponent)` is the contract: the argument is a PlayerModel, or a bot id that a Gen 9 player resolves against the models in its own spec.
- **Experience** is a set of named additive statistics, so deltas from any collector merge in any order and a board counts once. Four kinds: `count` (labelled tallies), `hist` (integer histogram), `moment` (sums on a fixed grid), `loglik` (summed log-likelihood per candidate). Estimators that shrink toward a prior: `rate`, `choice_honesty` (allows for the number of spots held), `posterior` (over profiles), `grid_best` (play factor).
- **bill:** per-family deviation is a `count` named `bid.<family>` with labels `agree` and `deviate`, plus a `hist` `bid.<family>.miss` of signed distances outside the range; the profile evidence is the `loglik` named `profile`.
- **sam:** honesty per signal is a `count` named `card.<signal>` with labels `hit/<n>` and `all/<n>` by number of choices (for the message form, `n` is the number of messages); the play factor is a `moment` named `play.info` on your grid of factors.
- **dave:** D5 stores deltas and builds stores and snapshots with `add`, `merge`, `snapshot`; it does not need to know what any statistic means.

If a shape you need is missing, say so before working around it.
