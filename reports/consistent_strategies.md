# Consistent-strategy prototype: measured results

8 November 2026. Base repository commit: `63a4aa4`. Python reference implementation;
DDS source remains pinned at the revision in `vendor/DDS_SOURCE.md`. Exact
commands and assumptions are in [the design document](../docs/consistent_strategies.md).
Research attribution and license verification are in [CREDITS](../CREDITS.md).

Follow-up: the [1,000-board study](strategy_cost_and_partitions.md) supersedes the
100-board full-hand strength estimates below. These pilot measurements remain
recorded for provenance; their small positive point estimates did not persist.

## Result

The prototype finds and executes strategies whose values match independent
exhaustive policy enumeration in tiny games. It corrects demonstrable PIMC
valuation and move-choice errors. Full-hand playing-strength gains remain
unestablished: the stronger-continuation trial is statistically inconclusive,
and a cheap greedy continuation performs substantially worse than PIMC.

## Exact endings

Every family fixes North/South and uses eight alternative East/West layouts.
All four trump suits and NT are represented. Half the families use two suits
and half use the full deck; these are intentionally synthetic tactical tests.
The score objective is final tricks. All reported searches completed.

| Per-hand cards | Families | PIMC best-value overvaluation | Inferior chosen PIMC root | Mean PIMC time | Mean exact time |
|---|---:|---:|---:|---:|---:|
| 3 | 1000 | 40 | 8 | 3.94 ms | 52.16 ms |
| 4 | 100 | 9 | 2 | 5.48 ms | 1705.23 ms |

The largest best-value overvaluation was 0.50 tricks in the three-card set and
0.375 in the four-card set. The largest first-move loss was respectively 0.25
and 0.125 expected tricks. First-move loss gives PIMC optimal consistent play
*after* its selected card; it does not blame the first card for later mistakes.
PIMC ties are broken deterministically in this experiment, so the inferior-root
counts include failures to distinguish tied double-dummy alternatives. They are
not counts of strictly wrong PIMC rankings.

All selected exact strategies were executed against every legal defensive reply
in all 8,800 sampled layouts; the resulting vectors matched their advertised
values. Exactness is restricted to the supplied layouts, deterministic declarer
strategies and omniscient defence. It does not remove sampling uncertainty or
solve realistic information-limited defence.

The maximum retained Pareto-front sizes were eight and six. Increasing ending
size from three to four cards increased mean exact runtime about 33-fold in
these samples. Native-code optimization, additional pruning and selective
expansion are necessary before treating this as a general full-hand exact solver.
Timings are exploratory measurements in a shared execution environment, not
controlled hardware benchmarks or a reproduction of the papers' performance.

## A concrete failure preserved as a regression fixture

In generated three-card family 516, with spades trump and South on lead:

| South's lead | PIMC estimate | Best achievable consistent value after the lead |
|---|---:|---:|
| Spade ten | 12.875 | 12.625 |
| Heart four | 11.875 | 11.750 |
| Heart queen | 12.875 | 12.875 |

PIMC's best aggregate value happens to be correct, but it cannot distinguish
the good heart-queen lead from the inflated spade-ten alternative. The exact
policy chooses the queen. The full layouts are in
`tests/fixtures/strategy_fusion.json`; a separate unresolved-guess fixture
preserves the 0.50-trick valuation gap. These are generated examples, not copied
examples from the papers.

## Full-hand paired experiments

Every row uses 100 full deals, fixed opening leads and common greedy defenders.
Contracts are assigned synthetically; no BEN or tournament-strength claim is
made. The objective is tricks; IMPs are an additional paired reporting measure.
Positive differences favor the new planner.

| Candidate versus control | Tricks/board | IMPs/board (95% bootstrap interval) | Candidate/control seconds per hand |
|---|---:|---:|---:|
| Two-choice plan + greedy tail versus PIMC-8 | -1.00 | -2.29 [-3.06, -1.51] | 0.144 / 0.550 |
| PIMC-8 + exact small endings versus PIMC-8 | +0.02 | +0.04 [+0.00, +0.10] | 0.649 / 0.598 |
| One-choice plan + PIMC-2 tail versus the identical PIMC-2 tail | +0.05 | +0.08 [-0.30, +0.47] | 1.601 / 0.114 |

The first two rows use seed 730001. The last uses fresh deals with seed 740101,
following a separate 20-deal pilot (seed 740001, +0.15 tricks/board). The fresh
result is smaller and statistically inconclusive. The PIMC-2 control uses the
same view-based deterministic seeds and actions as the planner's continuation.
It is not the standard eight-sample PIMC player. Each plan uses eight outer
layouts, and the two PIMC samples are drawn anew from each actor's permitted view.

For the exact-ending comparison, both players share the PIMC random stream
before alpha-mu takes over. A preliminary run without that coupling was excluded
because earlier sampling differences confounded the comparison. The final run
recorded 110 completed alpha-mu plans, 36 observations outside sampled support,
and no search-budget fallback. Out-of-support events are explicit and trigger
resampling/fallback; they demonstrate why exactness on a sample is not certainty
about the real deal. The small positive result does not establish broad strength.

Full-hand plans commit to their searched prefix and explicit continuation.
They do not silently substitute DD values at the horizon, and they do not claim
a fixed-policy value for a different replanning policy. Unseen observations use
the documented fallback. All recorded full games replayed legally with matching
scores. The existing hard-constraint belief sampler remains a limitation.

## Verification and next implementation priorities

The 35-test suite passes, including the original harness tests, independently
enumerated information-set policies, execution of retained strategy witnesses,
weighted/reordered/duplicate worlds, input rejection, DDS depth-one equivalence,
single-world equivalence, trump and seat rotations, legal defender perspectives,
PIMC continuation execution, random-stream restoration on budget exhaustion,
paired-table resets and committed-policy replay.

The useful next work is to improve the quality/cost of the continuation policy,
allocate deeper search to unresolved decisions, add the remaining alpha-mu cuts,
and broaden evaluation to stronger defender policies and calibrated auctions.
The generic architecture is now available for those comparisons. No learned
model, inferred opponent population or generalized DDS proof cache was added.

Only source, documentation, compact summaries and two small regression fixtures
are committed. Bulk records, corpora, generated summaries, logs and binaries are
excluded and can be regenerated using the documented commands.
