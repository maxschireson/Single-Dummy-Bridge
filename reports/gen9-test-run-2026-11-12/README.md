# Gen 9 test run in a fresh session sandbox, 12 November 2026

`python3 scripts/run_tests.py --prepare` on a fresh clone of `feature/gen9` at `297a913`, in a
Claude session sandbox (2 CPUs, Python 3.13, numpy and scipy present by default, no TensorFlow,
jax or h5py, no solver built, no nets restored), with the runner from
`feature/gen9-workflow-tests` copied in. G9-W3.

**Result.** Everything that could run passed: 292 tests passed, none failed, in 185 s end to end
(20 s to build DDS and restore the 13 nets, 165 s for the 43 test files two at a time). Six tests
did not run for a missing optional package (five need TensorFlow, one h5py). A second run in the
same clone with `--with tensorflow,h5py` installed both (`tensorflow-cpu`, 10.5 s, from pip's
cache) and ran the five files holding those six tests: all 53 of their tests passed. So all 298
tests pass in a fresh sandbox once the two packages are installed.

**Notes.**
- The DDS library's sha256 differed between two fresh clones built minutes apart in different
  directories (`f44a6b8e...`, `29b1aec4...`); the build is not byte-reproducible across paths, so
  the hash is a check within one checkout, not an identity across machines.
- jax is not needed by any test file on `feature/gen9`; the training scripts that use it are not
  under test.
- Not covered by any test here: BEN servers, TensorFlow GPU, the boxes' own environment (they
  have 8 cores and a venv). Estimate for a box: about 80 to 90 s of testing, set by the slowest
  file (`test_gen7.py`, 78 s here); the files' times add up to 316 s, so 8 at a time leave that
  file as the floor.

## Run 1: fresh clone, `--prepare`

Source `297a913` (feature/gen9); Python 3.13.18, 2 CPUs, Linux x86_64; wall time 164.6 s for 43 files, 2 at a time, plus 20.1 s to prepare.

**Tests:** 292 passed, 0 failed, 0 errors, 4 skipped, 2 not run for a missing optional package (plus any in files that could not be imported). **Files:** 2 partly not run, 41 passed.

## Preparation

- pip: nothing needed
- DDS: built in 19.5 s, sha256 `29b1aec4f9ea5bc3`
- Nets: `gen5-2026-11-10` ok; `gen6-candidate-2026-11-11` ok; `gen3-2026-11-09` ok; `gen4-2026-11-09` ok; `gen5-2026-11-10` ok; `gen5-belief-2026-11-10` ok; `gen7-policy-v0-2026-11-11` ok; `gen7-policy-v1-2026-11-11` ok; `gen7-policy-v2-2026-11-11` ok; `gen7-policy-v4-2026-11-11` ok; `gen7-policy-v4.1-2026-11-12` ok; `hand-fit-scorer-v0-2026-11-11` ok; `joint-auction-belief-lead-v0-2026-11-10` ok

## By file

| File | Status | Passed | Failed/errors | Skipped | Not run | Seconds | Note |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| test_auction_policy.py | partly not run | 2 | 0 | 0 | 1 | 0.2 | needs `tensorflow` |
| test_belief_capacity.py | partly not run | 2 | 0 | 0 | 1 | 0.2 | needs `tensorflow` |
| test_arena_diagnostics.py | passed | 2 | 0 | 0 | 0 | 0.1 |  |
| test_arena_watchdog.py | passed | 7 | 0 | 0 | 0 | 0.3 |  |
| test_auction_belief.py | passed | 3 | 0 | 0 | 0 | 0.1 |  |
| test_belief_model.py | passed | 5 | 0 | 2 | 0 | 0.1 | skips: TensorFlow optional |
| test_bidding_loop.py | passed | 11 | 0 | 1 | 0 | 1.8 | skips: TensorFlow optional |
| test_bidding_sampling.py | passed | 5 | 0 | 0 | 0 | 0.7 |  |
| test_bidding_systems.py | passed | 27 | 0 | 1 | 0 | 50.8 | skips: h5py is not installed |
| test_boxctl.py | passed | 4 | 0 | 0 | 0 | 4.3 |  |
| test_dds_cache.py | passed | 6 | 0 | 0 | 0 | 0.7 |  |
| test_direct_arena.py | passed | 3 | 0 | 0 | 0 | 1.0 |  |
| test_fork_audit.py | passed | 3 | 0 | 0 | 0 | 0.3 |  |
| test_gen4_ablation.py | passed | 2 | 0 | 0 | 0 | 0.9 |  |
| test_gen4_mix.py | passed | 1 | 0 | 0 | 0 | 0.3 |  |
| test_gen5.py | passed | 3 | 0 | 0 | 0 | 0.3 |  |
| test_gen5r.py | passed | 4 | 0 | 0 | 0 | 1.1 |  |
| test_gen5rz.py | passed | 6 | 0 | 0 | 0 | 0.6 |  |
| test_gen5rz_ben.py | passed | 2 | 0 | 0 | 0 | 0.5 |  |
| test_gen6.py | passed | 17 | 0 | 0 | 0 | 9.2 |  |
| test_gen6_cutover.py | passed | 3 | 0 | 0 | 0 | 0.9 |  |
| test_gen6_independent.py | passed | 1 | 0 | 0 | 0 | 0.3 |  |
| test_gen6_launch.py | passed | 5 | 0 | 0 | 0 | 0.3 |  |
| test_gen7.py | passed | 28 | 0 | 0 | 0 | 75.3 |  |
| test_gen7_alpha.py | passed | 15 | 0 | 0 | 0 | 77.8 |  |
| test_gen7_launch.py | passed | 11 | 0 | 0 | 0 | 17.9 |  |
| test_gen8_early_play.py | passed | 7 | 0 | 0 | 0 | 20.0 |  |
| test_gen8_tables.py | passed | 4 | 0 | 0 | 0 | 0.5 |  |
| test_gen9_player_model.py | passed | 14 | 0 | 0 | 0 | 0.1 |  |
| test_improvement.py | passed | 18 | 0 | 0 | 0 | 12.6 |  |
| test_layout_geometry.py | passed | 2 | 0 | 0 | 0 | 0.1 |  |
| test_layout_reduction.py | passed | 7 | 0 | 0 | 0 | 1.0 |  |
| test_loop_v2.py | passed | 3 | 0 | 0 | 0 | 4.9 |  |
| test_mixed_arena.py | passed | 3 | 0 | 0 | 0 | 0.9 |  |
| test_mixed_transition.py | passed | 3 | 0 | 0 | 0 | 0.2 |  |
| test_policy_selector.py | passed | 6 | 0 | 0 | 0 | 0.2 |  |
| test_prediction_promotion.py | passed | 3 | 0 | 0 | 0 | 0.1 |  |
| test_round5.py | passed | 3 | 0 | 0 | 0 | 0.1 |  |
| test_rule_bidder.py | passed | 5 | 0 | 0 | 0 | 5.2 |  |
| test_selfplay.py | passed | 7 | 0 | 0 | 0 | 21.0 |  |
| test_shared_bidding.py | passed | 1 | 0 | 0 | 0 | 0.1 |  |
| test_system.py | passed | 25 | 0 | 0 | 0 | 2.7 |  |
| test_three_engines.py | passed | 3 | 0 | 0 | 0 | 0.3 |  |

## Skipped, with reasons

| Reason | Count | Example |
| --- | ---: | --- |
| TensorFlow optional | 3 | `test_belief_model.BeliefTrainingTests.test_masked_loss_ignores_known_labels_and_gradients` |
| needs tensorflow | 2 | `test_auction_policy.AuctionPolicyTests.test_parent_preservation_and_trained_export` |
| h5py is not installed | 1 | `test_bidding_systems.BidderTests.test_neural_adapter_equals_the_engines_bidder_state` |


## Run 2: the five files with optional packages, `--prepare --with tensorflow,h5py`

| File | Status | Passed | Failed/errors | Skipped | Not run | Seconds | Note |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| test_auction_policy.py | passed | 3 | 0 | 0 | 0 | 9.8 |  |
| test_belief_capacity.py | passed | 3 | 0 | 0 | 0 | 9.9 |  |
| test_belief_model.py | passed | 7 | 0 | 0 | 0 | 9.8 |  |
| test_bidding_loop.py | passed | 12 | 0 | 0 | 0 | 11.1 |  |
| test_bidding_systems.py | passed | 28 | 0 | 0 | 0 | 57.8 |  |
