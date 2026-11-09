# Nested 16 / 32 / 64 scoring for the next round

User request, 9 November 2026: prepare a multi-score player for the next generation.
The implementation is isolated from the frozen g0001-bid40k collector. It makes
one belief sampler, draws 64 worlds, calls DDS once, and reduces prefixes16,32,64
through the existing player and selector code. Every legal move gets its own
utility, uncertainty and gap at each budget, followed by that budget's eligible
set, selector predictions, selected move and behavior probabilities.

## Interface

```python
from bridge_harness.multiscore import make_multiscore_player
player = make_multiscore_player(
    belief='selected-belief.npz', policy='selected-policy.npz',
    budgets=(16, 32, 64), active_samples=32,
    near_tie=.125, exploration=0.)
result = player.choose_all(observation, rng)
# result.decisions[16], [32], [64]: separate Decision objects
# result.rng_states[budget]: standalone-equivalent post-decision RNG states
# result.shared_work: physical solver cost, counted once
# Or use player.choose(observation, rng) in the existing player interface.
player.close()
```

`choose` logs the alternatives in `details['multi_score']` and returns the
explicit active budget's action. Default active32 preserves the current behavior
budget; scoring64 is not adoption of64. The separate64-vs32 evaluation retains
its500-board/no-automatic-promotion condition. Active16/64 can be selected
explicitly in a future frozen manifest. No8-sample experiment is revived.

The factory supports public or auction beliefs, old or auction-aware or IMP
selectors, and an optional `reference_policy` for the existing local audit
protocol. A bare batch PIMC-family player can also be wrapped in
`MultiScorePlayer(player, ...)`. Instances are worker-local. Known supported
players have read-only model state during choose; custom stateful subclasses
need their own parity validation before use.

## Exactness and cost accounting

Sampling uses a private copy of the caller RNG. Checkpoints after16/32/64 draws
allow each existing chooser to consume precisely its standalone tie-breaking
and policy-selection randomness. The caller ends in the active budget's state.
Each selector sees only its own prefix estimates and sample-count feature.
The belief net and DDS work are shared; selector inference is budget-specific.
Forced moves do no sampling or DDS work and leave the RNG unchanged.

Prefix decisions report zero physical DDS work and `work_accounting=shared-multiscore`.
`choose_all.shared_work`, or the outer `choose().details`, owns the actual cost
once. `samples` remains the behavior budget; `dds_calls` at the outer level is
64 on nonforced moves. Do not charge16+32+64 to the fork admission budget or
mistake three score views for three independent observations. No sampled hidden
worlds or continuation outcomes enter actor input features.

## Boundary handoff

`configs/multiscore_next_round.json` is a manifest-compatible factory profile,
not an executable launch instruction. Bind the next selected belief/policy and
optimizer checkpoints, use each roster member's actual belief kind, and freeze
new code/model/config identities. The versioned direct-pair collector must
explicitly construct this player rather than its hard-coded ArenaPlayer.
Preserve A-B:A-C:B-C=4:2:1 allocation, frozen common auctions, family splits,
post-commit random audits and separate match/audit IMP accounting. Keep all
budget views and all future continuations within the same board family and
normalize training weight per family across views.

This delivers the multi-score player, not a new trajectory scheduler. Alternative
move scores are not counterfactual reward labels or completed16/64 matches.
A collector that follows all three must branch only into the prescribed budget
policies on disagreement, charge real work once, and evaluate each branch with
its own public history/RNG. Exact DDS positions can share cached solutions;
different public histories cannot be merged solely because cards coincide.
Until that collector is implemented, the drop-in `choose` API follows one
explicit behavior budget and logs all three scores.

No current source/model/manifest, STOP marker, schedule, writer or trainer is
changed by installing this branch. The owner must integrate it in the isolated
successor checkout before collection, never cherry-pick into the live checkout.

## Validation

`tests/test_multiscore.py` checks standalone parity for16/32/64 across score,
tricks and make objectives, early/late/partial-trick/forced states, exact RNG
state, single batch, active16 accounting and warm-cache reuse.
`scripts/validate_multiscore.py --run RUN --out REPORT` additionally checks the
actual frozen public belief, new policy and reference policy, all estimates,
probabilities, audit reference choices and RNG states. It runs serially and
only reads the named run. The recorded small cost experiment is in
`reports/multiscore_validation_2026-11-09.json`; it is not a full-collector speed
benchmark and does not measure the cost of divergent trajectories.
