# Second policy and public-play belief networks

The new policy and belief networks improve held-out prediction. Neither result
alone establishes stronger play. This report uses component names explicitly:
`auction-policy-v2` is the new policy warm-start; `public-belief-v2` is the large
auction-and-public-play belief model. The older complete bot called `combined-v2`
is a different, retained historical version.

## Policy network

| Measure | Previous selector | New auction policy |
|---|---:|---:|
| Parameters | 25,170 | 39,512 |
| Validation chosen-return MSE | 0.90976017 | 0.81304822 |
| Relative MSE reduction | — | 10.63% |
| Training decision rows | — | 363,868 |
| Validation decision rows | — | 58,288 |
| Validation deal families | — | 2,466 |
| Selected epoch | — | 8 / 8 |
| Active fit time | — | 103.82 seconds |

The last predictive warm-start includes the stopped 8,315-board collection and
earlier completed play. All views and rotations of a deal remain together.
The net receives the public auction directly, relative bidder seats, visible
cards, ordered public play, contract/vulnerability, and PIMC estimates.
Hidden cards and future outcomes are labels only, never policy inputs.

Most of the improvement is shared state-value prediction: removing the action
correction gives MSE 0.813197 versus 0.813048. Greedy rankings change on 31.94%
of validation support, but that is not a demonstrated IMP gain. The selected
checkpoint has not yet been trained on audited IMP gains. The new arena supplies
that objective; ordinary play outcomes will no longer label policy updates.

Checkpoint SHA256:
`8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5`.
NumPy/TensorFlow export discrepancy: at most 9.54e-7.
Detailed methodology: [policy bootstrap](auction_policy_bootstrap_2026-11-09.md).

## Belief network

| Measure | Starting model | Small candidate | Selected large candidate |
|---|---:|---:|---:|
| Parameters | 46,582 | 80,054 | 308,726 |
| Public-play cross entropy | 0.698851 | 0.695413 | 0.694354 |
| Uncertain-card ownership accuracy | 54.41% | 55.38% | 55.66% |
| Public-play Brier score | 0.492033 | 0.488967 | 0.488026 |
| BEN completed-auction cross entropy | 1.053766 | 1.052941 | 1.051778 |
| DDS-bidding completed-auction cross entropy | 1.053569 | 1.052648 | 1.051588 |
| Selected epoch / completed epochs | 0 | 6 / 8 | 6 / 8 |

The frozen size study contains 963,304 training and 121,362 validation
observations, combining BEN auctions, DDS bidding data, and public-play
trajectories. The large model improves prediction in all three domains and was
adopted on lower cross entropy plus higher card-possession accuracy. The
validation recipe weights public play 50%, completed DDS-bidding auctions 25%,
and completed BEN auctions 25%. Model and Adam state are preserved.

Checkpoint SHA256:
`bb46241ed4270ac171354ca9b7d5146bf532f50fc08370c5a5ee07461bbceedb`.
NumPy/TensorFlow discrepancy: at most 2.98e-7.

A separate 50-board matched pilot, both versions at **16 samples**, yielded
+0.24 IMP/board (descriptive 95% interval -0.353 to +0.833) and 0.00 tricks/board
(-0.207 to +0.207). It is inconclusive about playing strength. The new mixed
arena uses **32 samples**, so these are separate experiments, not pooled scores.
Detailed results: [size study](belief_size_study_2026-11-09.md) and
[initial play pilot](large_belief_play_2026-11-09.md).

## Next experiment

The [40k bidder restart](bid40k_restart_2026-11-09.md) gives **every current and
historical play version the same latest bidding network**. It replaces the
initial original-BEN-auction launch. Cardplay promotion uses identical frozen
auctions in each pair, so bidding differences cannot drive the comparison.

The [mixed branching arena](../docs/mixed_fork_generations.md) combines training
trajectories, held-out belief validation, random policy audits, and matched
whole-bot play. Its first generation is 25,000 fresh contracted boards.
The newest validated version starts first in the roster; negative paired IMP
evidence can demote it. An inconclusive result does not postpone the next fit.
