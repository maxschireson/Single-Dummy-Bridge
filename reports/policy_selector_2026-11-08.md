# Small learned selector for near-equal PIMC plays — 8 November 2026

## Question and scope

Can the existing randomized self-play data teach a small network to choose
better among moves within 0.125 estimated tricks of the best 32-world PIMC
move? This experiment trains a 25,170-parameter action scorer and evaluates
actual play. It does not change the default bot.

The sampler remains the original bidding-blind uniform sampler, constrained
by visible cards, hand sizes and observed voids. This isolates move selection
from the separate [bidding-informed sampling experiment](bidding_sampling_2026-11-08.md).
Synthetic auctions are excluded from the model. Bidding-informed sampling
and this selector were not combined in this experiment. A separate
[follow-up test](policy_over_belief_2026-11-08.md) measures the frozen selector's
increment over the frozen belief-informed sampler on fresh auctioned deals.

## Data and learning target

The source is the independently audited collection of 10,000 complete,
distinct self-play deals, with no failed or duplicate games counted.

| Split | Original deals | Randomized selector decisions |
|---|---:|---:|
| Train | 7,993 | 259,299 |
| Validation | 1,008 | 32,554 |
| Test | 999 | 32,214 |

The effective independent sample size is deals, not decision rows. Each row
has only the eventual return for the card that was actually played. Unchosen
cards are not assigned invented win/loss labels. Simply imitating the logged
cards would reproduce the behavior policy's random tie-breaking.

The regression target is the acting partnership's remaining tricks. The
prediction consists of the pre-action PIMC estimate, a state-value correction,
and an action correction centered to have mean zero across the eligible moves.
Only the chosen action contributes to the loss. Uniform randomized behavior
provides coverage within the near-tie window, but one trajectory per deal
still leaves considerable outcome noise and limited counterfactual coverage.

At deployment the common state-value correction cancels when ranking cards.
The selector maximizes PIMC value plus its learned action correction, strictly
within the original 0.125-trick window. It performs no extra DDS solves.

## Small model and validation

The state encoder has 32 hidden units. A scorer shared across candidate cards
has 16 and 8 hidden units and a scalar output. Candidate features include
visible and played ranks in that card's suit, its rank, and trump/led-suit
indicators. State inputs include visible hands, public play, current trick,
voids, remaining counts and contract context. Seats are relative to the acting
hand; training uses suit permutations. True hidden hands and outcomes never
enter the encoder.

Training used AdamW, a batch size of 512 and fixed seed 20261120. The maximum
was 12 epochs with patience 3, selecting lowest validation chosen-action MSE.
It stopped after 6 epochs; epoch 3 was selected. Training plus validation took
52.58 seconds on the available CPU environment, excluding initial data checks.
There was no hyperparameter search or retraining after inspecting test results.

| Prediction error (MSE, tricks squared) | Validation | Held-out test |
|---|---:|---:|
| Raw PIMC estimate | 1.436839 | 1.423393 |
| PIMC plus learned state correction, action head removed | 1.363402 | 1.377557 |
| Full model including action correction | 1.363917 | 1.377694 |

The model learns some general correction to PIMC's outcome estimates. The
action head does not improve held-out prediction error in this experiment.
That distinction matters: better state-value prediction alone cannot choose
a better card, because it applies equally to all eligible cards.

## Frozen playing test

Before playing, 200 of the 999 original test deals were chosen by sorting
their deal hashes and shuffling with seed 20261120. They retain their original
contracts and synthetic auctions. The model was frozen after validation.

Two separate comparisons use those same 200 deals:

1. Selector versus uniform random choice inside the 0.125-trick window.
2. Selector versus highest PIMC mean, randomizing only among exact PIMC ties.

The second control distinguishes learning from merely favoring the top of the
PIMC window. Both comparisons swap candidate and control partnerships between
two tables. This totals 800 games over 200 independent deals, not 800 independent
deals. Neither comparison upgrades both partnerships simultaneously. Trick
differences are the candidate's swing over the two tables, combining declaring
and defending, rather than extra declarer tricks when everyone is upgraded.

All non-forced decisions use exactly 32 worlds and batch DDS. Both policies
receive identical PIMC random streams whenever they encounter the same public
history. This reduces avoidable sampling noise; divergent histories naturally
have different observations and subsequent streams. Original deals are the
unit of bootstrap resampling.

| Comparator | Candidate trick swing / paired deal (95% CI) | IMPs / paired deal (95% CI) | IMP wins / ties / losses |
|---|---:|---:|---:|
| Random near-ties | +0.160 [-0.015, 0.335] | +0.230 [-0.26, 0.71] | 69 / 81 / 50 |
| Highest PIMC mean | +0.100 [-0.045, 0.235] | +0.220 [-0.195, 0.645] | 54 / 101 / 45 |

All 800 complete games passed legal replay: 41,600 plies, 32,942 non-forced decisions and 1,054,144 DDS world solves. There were no failed completed games. Every non-forced decision used exactly 32 worlds; every selector choice stayed within 0.125 estimated tricks.

Both point estimates favor the selector, but every trick and IMP interval includes zero. This initial test does not establish a playing-strength improvement. The default bot is unchanged; the frozen checkpoint is retained for larger fresh evaluation.

Execution began with four workers and resumed with eight, reusing 148 completed pairs. In-flight incomplete attempts were discarded and rerun; they are not counted as completed games. The final invocation took 413.29 seconds, in addition to the earlier work.

The learned scorer was used on 13,099 candidate decisions across the two comparisons. It selected below the highest PIMC mean on 338 of them (2.58%); its other changes mostly chose among exact PIMC ties.

## Offline policy diagnostic

On all 999 held-out test deals, a contextual-bandit doubly robust estimate
uses the known logged action probabilities. It asks what would happen if
one decision changed and the rest of play followed the old behavior policy.
It is not a full-game estimate with the selector active throughout play.
Eligible decisions are averaged within each original deal, then across deals.

| Comparator | Estimated acting-partnership tricks per changed decision | 95% deal-bootstrap interval |
|---|---:|---:|
| Random near-tie policy | +0.00428 | [-0.01733, +0.02614] |
| Highest PIMC mean | +0.00054 | [-0.01948, +0.02044] |

Both intervals include zero. The selector chooses below the highest PIMC mean
on 2.66% of these states; it also breaks many exact PIMC ties differently.
These test deals overlap the playing test and are not additional independent
evidence to be combined as if they came from a separate population.

## Verification and provenance

- Unit checks cover partnership-return conversion on both sides, action identity
  and local features under suit permutations, exact seat-rotation invariance,
  rejection of empty support, and exclusion of privileged fields.
- Live versus serialized observation encoding agrees on every ply of one full
  archived game; PIMC residual targets agree on its 29 selector decisions.
- Six selector/cluster unit tests, seven self-play regression tests and 25
  system tests pass. They include native batch/serial
  solve agreement, information boundaries, complete labels and split grouping.
- NumPy inference agrees with Keras on validation observations, maximum absolute
  output difference 9.54e-7 tricks. TensorFlow is not loaded by the playing bot.
- The shared tensor encoder now accepts legal-card tuples from live observations
  as well as lists from JSON. Existing serialized training features are unchanged.
- Match uncertainty now groups by original-card identity, matching dataset split
  boundaries. Local display board numbers repeat between collection chunks and
  must not accidentally merge independent deals into one bootstrap cluster.
- Checkpoint SHA256:
  `f81b14d449901fe5903df136acc5eeb6568d86700e5fd39bbb3cfa618fa742e8`.
- NumPy weight SHA256:
  `02b6885e8f07da473970052d7f9ea9dc2a10fa34505ad60186e4a14d02218c60`.

Raw episodes, weights, protocol, per-deal observations and audit outputs are
preserved outside Git. Source and reports are on the research branch. The
999-deal test split has now been consumed for this frozen model; future changes
tuned to these results need fresh evaluation deals.

## Reproduce

Use the audited ten-chunk data root with `audit-10000.json`. Training needs
NumPy and TensorFlow; evaluation needs NumPy and the built native DDS library.

```sh
python3 scripts/train_policy_selector.py --data <data-root> --out <run>/training
python3 scripts/evaluate_policy_selector.py --data <data-root> --run <run> --workers 4
python3 scripts/evaluate_policy_selector_offline.py --data <data-root> --run <run>
python3 scripts/audit_policy_selector.py --run <run>
```

Restore the archived protocol into the run directory before preparing evaluation.
Completed paired games are resumed rather than regenerated. The sampled-world
budget is fixed; these timings are not a controlled hardware comparison.

## Toward a standalone neural player

The longer-term target is policy, value and belief networks that can choose all
plays without PIMC/DDS at inference. This selector experiment is one intermediate
test, not a commitment to keeping PIMC permanently. A full policy can first learn
from the existing evaluations of every legal move, then train through neural
self-play against a retained opponent pool. That changes the learning problem
from extracting tiny differences between nearly tied moves to reproducing useful
play across the whole decision space. Teacher imitation alone does not guarantee
exceeding PIMC or correcting its strategy-fusion errors.
