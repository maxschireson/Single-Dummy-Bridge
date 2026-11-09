# DDS value network quick test — 2026-11-09

## Added cost frontier check

A follow-up screen directly compares 16/32/64 exact layouts with net-assisted sampling. It also tests a fixed, untuned residual-correction estimator: average the net over 128 layouts, then add the average exact-minus-net error on the first 16 or 32 randomly drawn layouts. These audits are random rather than selected for uncertainty. With identically distributed draws and paired predictions, this corrects model bias in expectation; it does not guarantee lower move regret or eliminate finite-sample noise.

The evaluation uses 100 further test deals (seed families 400–499), disjoint from the preceding 200-deal sampled-world screen, producing 180 nonforced decisions at 13 and 11 tricks remaining. A separate independent set of 128 belief samples supplies the common reference. No candidate layouts are reused in the reference, and no estimator coefficient or threshold was fitted on these results. CPU includes belief inference and sampling as well as evaluation.

| Method | CPU vs 32 exact layouts | Mean move regret vs independent reference |
|---|---:|---:|
| 16 exact | 50.8% | 0.01679 |
| 32 exact | 100.0% | 0.01385 |
| 64 exact | 195.8% | 0.01160 |
| 32 net-assisted, light proof | 6.2% | 0.06150 |
| 64 net-assisted, light proof | 11.8% | 0.06215 |
| 128 net-assisted, light proof | 22.9% | 0.06345 |
| 128 net + 16 exact residual corrections | 53.5% | 0.01354 |
| 128 net + 32 exact residual corrections | 102.7% | 0.01523 |

The promising candidate is 128 net evaluations plus 16 exact residual corrections: 53.5% of the CPU of exact-32, with similar overall mean regret. Its paired family difference versus exact-32 is -0.00065 tricks/decision, 95% interval [-0.00541, +0.00412]. That permits a meaningful loss relative to these small baseline regrets, so equivalence is not established. Exact-32 plus correction shows no improvement in this small screen; there is no demonstrated general superiority of the estimator.

The stage split matters. At 13 remaining, corrected-16 has regret 0.01047 versus exact-32 0.01653, using 52.4% of its CPU. At 11 remaining, corrected-16 has regret 0.01668 versus 0.01110, using 61.6% of its CPU. The latter paired interval is slightly above zero. These small, exploratory subgroup results favor focusing the next test on expensive opening positions while retaining exact search later.

Adding approximate layouts alone did not help: net-assisted 32/64/128 had regret 0.06150/0.06215/0.06345. This is consistent with systematic approximation errors dominating sampling noise. The previous full-information advantage therefore does not establish an improvement over the exact-search cost–strength frontier.

The independent-reference regret numbers here have a different definition from the preceding same-32-layout regret screen below and should not be compared across tables. The reference itself has finite-sample error. This is a candidate for a paired IMP test, not a replacement for the existing arena evidence that 64 exact samples can improve play. No candidate is promoted.

Reproduce with `scripts/screen_dds_value_frontier.py`; `bridge_harness.dds_value.corrected_mean` implements and tests the fixed residual estimator. Full records are in `cost-frontier-decisions.json.gz`.

## Initial approximation experiments

The useful first candidate is a learned DD estimate plus a small proof budget. On a frozen 32-world decision screen it uses 39.6% less CPU than the existing rollout-based approximation, with a nearly unchanged point estimate of move regret. The net alone is weaker after averaging hidden hands. Selective full solving improves the point estimate but exceeds the intended budget. No candidate is promoted.

## Most relevant comparison: 32 belief samples

200 fresh test deals produced 369 nonforced decisions from 197 contributing families, at 13 and 11 tricks remaining. Every method sees exactly the same 32 Gen3 belief samples, legal moves and contract. The reference is exact DDS averaged across those same samples. Regret is the expected trick loss from the selected move relative to that reference; it is not IMPs and does not establish playing strength. All methods use expected-trick argmax without a policy tie-breaker.

| Method | CPU relative to current approximation | Mean PIMC regret | Paired family regret change, 95% CI |
|---|---:|---:|---:|
| Current rollout + 1,000 visits/move | 100.0% | 0.06390 | +0.00000 [+0.00000, +0.00000] |
| Network alone | 10.0% | 0.09282 | +0.03518 [+0.00608, +0.06427] |
| Network + 100 visits/move | 60.4% | 0.06470 | +0.00083 [-0.01916, +0.02082] |
| Network + 1,000 visits/move | 105.7% | 0.05886 | -0.00408 [-0.02210, +0.01393] |
| Network + 100 visits/move + selected full solves | 115.9% | 0.05886 | -0.00520 [-0.02383, +0.01344] |

Negative regret changes favor the candidate. Intervals are paired Student-t intervals on per-family mean differences. The table's mean regret weights decisions; paired differences weight independent families. The screen does not establish equivalence: the interval for network + 100 visits/move permits roughly 0.02 trick/decision loss or gain.

The combined fallback variant executed 487 full solves out of 11,808 sampled-world evaluations (4.12%). Its confidence cutoff was frozen on the separate full-information validation set before this screen. Its 115.9% CPU expenditure shows that a confidence threshold calibrated on independent full-information positions does not enforce the intended budget on belief-sampled worlds. The next gate must account for solve cost on the actual sampling workload and limit cumulative expenditure. No threshold was retuned on these test results.

Network inference is batched across the 32 worlds. Timing uses process CPU and includes position encoding, the network, probability conversion, exact-equivalence pooling, budgeted search, and actual selected full solves. It excludes belief sampling (identical for all methods), bidding, model construction and the unchanged opponent. The exact reference uses the production batch DDS API. The full fallback solver uses a separate context from the solver generating test trajectories.

## Full-information screen

800 independent test families contribute 3,200 early positions; 2,863 have multiple legal cards, and 2,723 have more than one distinct DD-equivalent choice. Training covers only 10–13 tricks remaining. No 8- or 9-trick positions were trained or tested.

| Method | CPU relative to current approximation | Mean selected-move DD regret |
|---|---:|---:|
| Network alone | 8.5% | 0.11385 |
| rollout100 | 57.0% | 0.15816 |
| Current rollout + 1,000 visits/move | 100.0% | 0.13421 |
| Network + 100 visits/move | 60.6% | 0.10135 |
| Network + 1,000 visits/move | 104.5% | 0.09138 |
| Validation-selected reinvestment policy | 101.2% | 0.09489 |

Regret excludes positions whose legal cards are all DD-equivalent; CPU covers positions with more than one legal card. Ties are scored by uniform choice among tied estimates. Independent-position network inference assumes batches of 32 and includes measured equivalence-pooling cost. The full-information fallback CPU is replay accounting using measured exact-solve time; the sampled-world screen above actually executes its full fallbacks. Every completed proof bound was checked against exact DDS. Approximate values remain explicitly unproved and do not enter the exact answer cache.

The independent-position advantage does not fully survive averaging across sampled hidden hands: in the 32-world screen the net-alone variant is worse. This is why the sampled-world check, rather than full-information accuracy alone, determines the conclusion.

## Model and data

The candidate has 509,912 parameters: a 373-feature full-information representation, 512/256-unit ReLU layers and 52 x 14 trick logits. Seats are rotated to the current actor. Inputs contain all four remaining hands, ordered current-trick cards, trump and remaining tricks. There is no auction or belief head. Output distributions represent uncertainty about a deterministic exact DD value. Variance is a heuristic uncertainty estimate, not a certified probability of correctness.

The source cache contains 6,207,053 positions with 10–13 tricks remaining. Uniform random-priority sampling retains 150,000 per stage: 600,000 positions and 3,394,317 exact legal-action labels. The cache has no originating-deal provenance, so no random row split is used for validation. A separate seed range generates 1,000 new deals: 200 validation and 800 test families, with balanced strains and current-trick offsets. Zero exact position keys overlap the source cache. Fresh trajectories follow exact-DD best moves with deterministic random tie-breaking. Synthetic fixed contracts and these trajectories are a distribution limitation. The 32-world screen uses the first 200 test families, without training or tuning on them.

Training uses legal-action cross entropy, mean squared value error, centered action-value error and a best-move probability term. Random suit permutation augments each batch. Six epochs took about 178 seconds on this CPU environment. Epoch 5 was selected by validation nonforced move regret; epoch 6 was not selected despite better value MAE. NumPy export differs from TensorFlow by at most 1.15e-5 in logits.

A single cheap DDS value is converted to the correct child partnership and adjusted for immediately won tricks before seeding threshold proofs. Certified bounds, strict visit budgets and abort cleanup remain intact. Tests cover this sign/reward conversion, seat and suit symmetries, packed-state round trips, proof containment and exact solver reuse. All 44 relevant tests passed.

## Reproduce

Build the existing native library with `python scripts/build_dds.py`. Reassemble the model with:

```sh
python scripts/assemble_model_parts.py models/dds/value-2026-11-09
```

The frozen dataset is `DDS_Value_Quick_Test_Data_2026-11-09.zip`; its identity and hashes are in the accompanying manifests. `scripts/prepare_dds_value.py` produces cache samples and independent holdouts. `scripts/train_dds_value.py` fits the candidate. `scripts/screen_dds_value.py` calibrates on validation before evaluating independent-position test data. `scripts/screen_dds_value_pimc.py` runs the 32-world comparison. The model is [here](../../models/dds/value-2026-11-09). All complete screening records and configurations accompany this report.

The net-assisted approximation is the recommended candidate for a later paired whole-game test. The next experiment should calibrate the allocation of full solves on sampled-world decisions and enforce an actual CPU budget. No actual-play IMP result is claimed here.
