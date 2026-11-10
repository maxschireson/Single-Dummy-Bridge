# Residual attention belief versus dense continuation

Both fits start from the selected dense v5 candidate, with the same frozen data, consequential-card weights, family/domain normalization, fresh AdamW, batch size 128, seed, three epochs and checkpoint-selection objective. The attention model adds a zero-initialized 64-wide, two-head cross-attention correction.

One seed; family SE omits retraining uncertainty. Fixed final epoch is primary. Selected-checkpoint comparisons are descriptive after selection. No reserved test evaluation or arena promotion.

## Fixed final epoch

| Model | Epoch | Composite | Recent ordinary NLL | Weighted NLL | Consequential-only NLL | Accuracy | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| Parent dense v5 | 0 | 0.86762469 | 0.67109578 | 0.67255530 | 0.75459714 | 60.1732% | 0.46766872 |
| dense | 3 | 0.86895007 | 0.67309092 | 0.67458847 | 0.75778885 | 59.9862% | 0.46947131 |
| attention | 3 | 0.86838093 | 0.67211037 | 0.67360182 | 0.75569667 | 60.2344% | 0.46854181 |

Attention minus dense on recent validation families (negative loss deltas favor attention):

| Metric | Paired delta ± family SE | Families |
|---|---:|---:|
| nll | -0.00098055 ± 0.00019185 | 192 |
| weighted_nll | -0.00098666 ± 0.00019128 | 192 |
| accuracy | +0.00248203 ± 0.00094550 | 192 |
| brier | -0.00092950 ± 0.00017351 | 192 |
| weighted_accuracy | +0.00269441 ± 0.00094470 | 192 |
| weighted_brier | -0.00093313 ± 0.00017318 | 192 |
| upweighted_card_nll | -0.00209218 ± 0.00199479 | 130 |
| upweighted_card_accuracy | +0.01106447 ± 0.00693133 | 130 |
| upweighted_card_brier | -0.00200976 ± 0.00188952 | 130 |

Recent validation accuracy and Brier details:

| Model | Weighted accuracy | Weighted Brier | Consequential-only accuracy | Consequential-only Brier |
|---|---:|---:|---:|---:|
| Parent dense v5 | 60.1315% | 0.46822334 | 57.7982% | 0.50217559 |
| dense | 59.9868% | 0.47003553 | 58.4721% | 0.50437261 |
| attention | 60.2563% | 0.46910240 | 59.5785% | 0.50236285 |

## Selected checkpoints

| Model | Epoch | Composite | Recent ordinary NLL | Weighted NLL | Consequential-only NLL | Accuracy | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| Parent dense v5 | 0 | 0.86762469 | 0.67109578 | 0.67255530 | 0.75459714 | 60.1732% | 0.46766872 |
| dense | 0 | 0.86762469 | 0.67109578 | 0.67255530 | 0.75459714 | 60.1732% | 0.46766872 |
| attention | 0 | 0.86762469 | 0.67109578 | 0.67255530 | 0.75459714 | 60.1732% | 0.46766872 |

Attention minus dense on recent validation families (negative loss deltas favor attention):

| Metric | Paired delta ± family SE | Families |
|---|---:|---:|
| nll | +0.00000000 ± 0.00000000 | 192 |
| weighted_nll | +0.00000000 ± 0.00000000 | 192 |
| accuracy | +0.00000000 ± 0.00000000 | 192 |
| brier | +0.00000000 ± 0.00000000 | 192 |
| weighted_accuracy | +0.00000000 ± 0.00000000 | 192 |
| weighted_brier | +0.00000000 ± 0.00000000 | 192 |
| upweighted_card_nll | +0.00000000 ± 0.00000000 | 130 |
| upweighted_card_accuracy | +0.00000000 ± 0.00000000 | 130 |
| upweighted_card_brier | +0.00000000 ± 0.00000000 | 130 |

Recent validation accuracy and Brier details:

| Model | Weighted accuracy | Weighted Brier | Consequential-only accuracy | Consequential-only Brier |
|---|---:|---:|---:|---:|
| Parent dense v5 | 60.1315% | 0.46822334 | 57.7982% | 0.50217559 |
| dense | 60.1315% | 0.46822334 | 57.7982% | 0.50217559 |
| attention | 60.1315% | 0.46822334 | 57.7982% | 0.50217559 |

## All epochs

| Model | Epoch | Composite | Recent ordinary NLL | Weighted NLL | Consequential-only NLL | Accuracy | Brier | Active epoch seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 1 | 0.86851248 | 0.67225705 | 0.67373626 | 0.75868274 | 60.0822% | 0.46884313 | 67.0 |
| dense | 2 | 0.86830327 | 0.67223300 | 0.67375343 | 0.75572558 | 59.9684% | 0.46878918 | 66.7 |
| dense | 3 | 0.86895007 | 0.67309092 | 0.67458847 | 0.75778885 | 59.9862% | 0.46947131 | 64.9 |
| attention | 1 | 0.86793306 | 0.67145833 | 0.67292931 | 0.75648531 | 60.4039% | 0.46808744 | 620.7 |
| attention | 2 | 0.86769118 | 0.67140316 | 0.67293452 | 0.75424381 | 60.1261% | 0.46804558 | 866.0 |
| attention | 3 | 0.86838093 | 0.67211037 | 0.67360182 | 0.75569667 | 60.2344% | 0.46854181 | 711.3 |

Paired recent-play differences from the unchanged starting dense v5:

| Model | Epoch | Ordinary NLL delta ± SE | Weighted NLL delta ± SE | Consequential-only NLL delta ± SE |
|---|---:|---:|---:|---:|
| dense | 1 | +0.00116127 ± 0.00063301 | +0.00118096 ± 0.00062605 | +0.00408560 ± 0.00268763 |
| dense | 2 | +0.00113722 ± 0.00065788 | +0.00119813 ± 0.00065408 | +0.00112843 ± 0.00305132 |
| dense | 3 | +0.00199514 ± 0.00079823 | +0.00203318 ± 0.00080362 | +0.00319171 ± 0.00465776 |
| attention | 1 | +0.00036255 ± 0.00062672 | +0.00037401 ± 0.00061823 | +0.00188817 ± 0.00346372 |
| attention | 2 | +0.00030738 ± 0.00067614 | +0.00037923 ± 0.00067631 | -0.00035334 ± 0.00321002 |
| attention | 3 | +0.00101459 ± 0.00080693 | +0.00104652 ± 0.00081580 | +0.00109953 ± 0.00443125 |

## Fit and export checks

| Model | Parameters | Active epoch minutes | Elapsed minutes | Selected Adam steps | Maximum NumPy prediction error |
|---|---:|---:|---:|---:|---:|
| dense | 308,726 | 3.31 | 6.00 | 0 | 5.96e-07 |
| attention | 357,754 | 36.63 | 55.78 | 0 | 5.96e-07 |

Active epoch time includes training and validation, excluding worker startup and interrupted downtime. Elapsed time includes those interruptions. Export checks cover all four validation domains.

dense: epoch zero won; this fit did not improve its validation objective.

attention: epoch zero won; this fit did not improve its validation objective.

Each fit uses 998,425 positions, 31,120,476 uncertain-card targets, and 89,652 training families.
Validation contains 11,273 distinct families in total. Recent play contributes 192 families and 47,004 uncertain-card targets, including 1,687 consequential targets in 130 families. Positions and targets within a family are correlated; SEs use families as the sampling unit.
All domain metrics, every epoch, export checks and paired differences from the parent are in summary.json. Hybrid inference requires bridge_harness.residual_attention_belief.Weights; legacy loading deliberately rejects hybrid files.
