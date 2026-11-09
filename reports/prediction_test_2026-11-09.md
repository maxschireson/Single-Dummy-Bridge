# Frozen belief prediction test — 9 November 2026

Parent and selected epoch-eight weights were fixed and hash-verified before test predictions were inspected. No training or model selection used these results. Zero DDS solves and zero played games were required.

## Original validation cross-entropy

Cross-entropy is in natural-log units per unknown card.

| Distribution | Parent | Selected |
|---|---:|---:|
| ben | 1.053766443 | 1.052653125 |
| bidding | 1.053569411 | 1.052307410 |

These validation data selected the checkpoint and are not the confirmatory evidence below.

## Reserved test: observer hand and completed auction

| Distribution | Deals | Parent CE | Selected CE | Reduction, nominal 95% CI | Adjusted p |
|---|---:|---:|---:|---|---:|
| ben | 5,026 | 1.053148189 | 1.052015114 | 0.0011331 [0.0010289, 0.0012372] | 1.39e-95 |
| bidding | 3,960 | 1.053272335 | 1.051990643 | 0.0012817 [0.0011472, 0.0014162] | 1.28e-73 |

Cross-entropy and most-likely ownership accuracy improve significantly on both reserved distributions. This establishes a small predictive improvement of the frozen candidate; it does not attribute the improvement solely to new bidding data because no equal-update legacy-only control was run.

## Dummy visible: exact conditional ownership

| Distribution | Role | Deals | Parent accuracy | Selected accuracy | Gain, percentage points | Nominal 95% CI, pp | Adjusted p |
|---|---|---:|---:|---:|---:|---|---:|
| ben | declarer | 5,014 | 56.2763% | 56.4343% | 0.1580 | [-0.0158, 0.3319] | 0.89781 |
| ben | defender | 5,014 | 62.3247% | 62.4517% | 0.1270 | [0.0529, 0.2010] | 0.0093553 |
| bidding | declarer | 3,943 | 56.4380% | 56.5844% | 0.1464 | [-0.0293, 0.3220] | 1 |
| bidding | defender | 3,943 | 62.2730% | 62.3785% | 0.1054 | [0.0333, 0.1775] | 0.050068 |

The dummy diagnostic exposes the two original visible hands and omits opening-lead/play evidence, matching the earlier harness protocol. It has 26 unknown cards in two 13-card hands, so the uniform baseline is exactly 50% accuracy and ln(2) cross-entropy. All factorized network ownership weights are conditioned on exact capacities, as in the actual sampler. The vectorized dynamic program was checked against WeightedSampler marginals for all three roles and both models on each test source. This is not an accuracy average over a played hand.

Declarer top-choice accuracy gains are inconclusive on both sources. Defender accuracy is significant on BEN (adjusted p=0.00936); the bidding-distribution defender gain narrowly misses the conservative family threshold (adjusted p=0.05007). Cross-entropy improves significantly for both roles on both sources.

| Distribution | Role | Parent CE | Selected CE | Adjusted p |
|---|---|---:|---:|---:|
| ben | declarer | 0.672821359 | 0.672075966 | 5.43e-15 |
| ben | defender | 0.646464791 | 0.645611357 | 8.62e-27 |
| bidding | declarer | 0.673208408 | 0.672500653 | 5.53e-12 |
| bidding | defender | 0.646776358 | 0.645789628 | 2.68e-24 |

## Statistical scope and reproducibility

Paired differences use original deal clusters: all hidden cards, observers, both defenders, and both room auctions stay in one cluster. Cluster-robust Student-t intervals preserve the card-weighted estimand with unequal room counts. The twelve test comparisons (two sources, three conditions, two metrics) use Bonferroni correction at family alpha 0.05; JSON also includes simultaneous familywise intervals. The displayed 95% intervals are individual nominal intervals.

The 3,960 bidding-source test families were reserved from belief gradients but were seen by the upstream bidder. The 5,026 BEN-source test families are disjoint from both imported bidding training and legacy belief training/validation. Dummy diagnostics exclude passed-out auctions, leaving 3,943 and 5,014 playable families respectively.

Numerical audit reproduces validation cross-entropy within 1e-9. NumPy and the previous TensorFlow evaluation differ on one near-tied most-likely-owner decision among 783,588 BEN validation predictions; this is 0.000128 percentage points and does not affect the reported precision or conclusions.

No play-strength test or promotion has occurred. Test splits have now been inspected for this fixed candidate; do not tune another checkpoint on these results. Code: scripts/test_bidding_belief_predictions.py. Full summary: prediction_test_2026-11-09.json. Per-deal cluster arrays and the pre-result protocol are in runs/bidding-belief-prediction-test.
