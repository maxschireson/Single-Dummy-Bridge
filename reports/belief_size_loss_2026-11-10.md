# Dense belief: size × consequence weighting

The current-size model is the better use of this training budget. Widening from
308,726 to 682,614 parameters did not improve either the fixed-epoch or selected
validation objective and increased training-plus-validation time by about 39%.
Consequence weighting produced a very small improvement in the composite score,
but this experiment does not establish an improvement on consequential cards.

All four cells selected epoch 1. The current-size weighted candidate has the
lowest selected composite (0.86762469 versus v4's 0.86795576), essentially tied
with the current-size ordinary candidate (0.86762543). Its recent weighted NLL
improvement over v4 is 0.00024872 with paired family SE 0.00036225. At fixed epoch
3, the average effect of weighting on consequential-card NLL is instead a small
worsening of 0.00007951 ± 0.00008613 SE. These results support keeping the current
width; they do not support claiming that consequential-card weighting improved
play or even reliably improved the targeted validation subset. No arena change
is recommended from this screen alone.

Four matched continuations from the v4 prediction function, using fresh AdamW in all four cells. The 308,726-parameter network is compared with a function-preserving widening to 682,614 parameters. Every cell receives the identical frozen clean dataset, three epochs, row ordering, learning rate, domain/family weighting and seed. Only dense width and card-level loss weights vary. The previous v5 run inherited Adam state; these matched controls deliberately reset it.

Frozen consequence weights are 1 + 3 × min(max(0, estimated value in IMPs), 1), from cross-fitted single-card owner information value under 24 v4 and 8 uniform legal worlds, with minimum owner-group size 4 and four-world prior shrinkage. They are applied only to the existing labeled recent clean-play positions; historical replay keeps weight 1. Recent families retain twice the training mass of historical families.

Primary comparisons use the final third epoch. Checkpoint selection uses the same frozen composite objective for every cell, with unchanged v4 eligible. The tables also report each selected checkpoint.

## Fixed epoch 3

| Cell | Epoch | Composite | Recent NLL | Weighted NLL | Consequential-card NLL | Accuracy | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| v4 baseline | 0 | 0.86795576 | 0.67132578 | 0.67280401 | 0.75468581 | 60.0982% | 0.46787222 |
| current_ordinary | 3 | 0.86764652 | 0.67119763 | 0.67267625 | 0.75557833 | 60.0374% | 0.46781243 |
| large_ordinary | 3 | 0.86781158 | 0.67138846 | 0.67285926 | 0.75681753 | 60.0747% | 0.46795928 |
| current_consequence | 3 | 0.86764297 | 0.67117027 | 0.67265188 | 0.75569532 | 60.0618% | 0.46778496 |
| large_consequence | 3 | 0.86781050 | 0.67136693 | 0.67284206 | 0.75685955 | 60.0765% | 0.46793844 |

| Cell | Weighted accuracy | Weighted Brier | Consequential-card accuracy | Consequential-card Brier |
|---|---:|---:|---:|---:|
| v4 baseline | 60.0639% | 0.46844577 | 57.6865% | 0.50236967 |
| current_ordinary | 59.9930% | 0.46838159 | 57.5149% | 0.50310151 |
| large_ordinary | 60.0132% | 0.46851986 | 56.6344% | 0.50422471 |
| current_consequence | 60.0205% | 0.46835654 | 57.6376% | 0.50319473 |
| large_consequence | 60.0163% | 0.46850239 | 56.6947% | 0.50423707 |

Paired differences from unchanged v4 on recent validation families:

| Cell | Ordinary NLL delta ± SE | Weighted NLL delta ± SE | Consequential-card NLL delta ± SE |
|---|---:|---:|---:|
| current_ordinary | -0.00012815 ± 0.00045691 | -0.00012776 ± 0.00045443 | +0.00089252 ± 0.00209922 |
| large_ordinary | +0.00006268 ± 0.00055631 | +0.00005525 ± 0.00055208 | +0.00213172 ± 0.00295166 |
| current_consequence | -0.00015551 ± 0.00045660 | -0.00015213 ± 0.00045401 | +0.00100951 ± 0.00208313 |
| large_consequence | +0.00004115 ± 0.00055575 | +0.00003805 ± 0.00055143 | +0.00217374 ± 0.00294187 |

Recent clean-play paired effects; negative NLL deltas favor the first/additive treatment.

| Contrast | Ordinary NLL delta ± SE | Weighted NLL delta ± SE | Consequential-card NLL delta ± SE |
|---|---:|---:|---:|
| size_with_ordinary | +0.00019082 ± 0.00017641 | +0.00018301 ± 0.00017477 | +0.00123920 ± 0.00116518 |
| size_with_consequence | +0.00019667 ± 0.00017601 | +0.00019018 ± 0.00017440 | +0.00116423 ± 0.00115771 |
| weighting_at_current | -0.00002737 ± 0.00001848 | -0.00002437 ± 0.00001864 | +0.00011699 ± 0.00008545 |
| weighting_at_large | -0.00002152 ± 0.00002119 | -0.00001720 ± 0.00002138 | +0.00004202 ± 0.00009867 |
| average_size_effect | +0.00019374 ± 0.00017611 | +0.00018660 ± 0.00017448 | +0.00120171 ± 0.00116098 |
| average_weighting_effect | -0.00002444 ± 0.00001897 | -0.00002079 ± 0.00001915 | +0.00007951 ± 0.00008613 |
| interaction | +0.00000584 ± 0.00001196 | +0.00000718 ± 0.00001195 | -0.00007497 ± 0.00006633 |

## Selected checkpoints

| Cell | Epoch | Composite | Recent NLL | Weighted NLL | Consequential-card NLL | Accuracy | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| v4 baseline | 0 | 0.86795576 | 0.67132578 | 0.67280401 | 0.75468581 | 60.0982% | 0.46787222 |
| current_ordinary | 1 | 0.86762543 | 0.67110251 | 0.67256106 | 0.75466307 | 60.1501% | 0.46767542 |
| large_ordinary | 1 | 0.86775367 | 0.67136200 | 0.67282280 | 0.75535807 | 60.1201% | 0.46791130 |
| current_consequence | 1 | 0.86762469 | 0.67109578 | 0.67255530 | 0.75459714 | 60.1732% | 0.46766872 |
| large_consequence | 1 | 0.86775268 | 0.67135214 | 0.67281395 | 0.75532007 | 60.1153% | 0.46790154 |

| Cell | Weighted accuracy | Weighted Brier | Consequential-card accuracy | Consequential-card Brier |
|---|---:|---:|---:|---:|
| v4 baseline | 60.0639% | 0.46844577 | 57.6865% | 0.50236967 |
| current_ordinary | 60.1076% | 0.46822935 | 57.9864% | 0.50224282 |
| large_ordinary | 60.0744% | 0.46846522 | 58.2251% | 0.50296927 |
| current_consequence | 60.1315% | 0.46822334 | 57.7982% | 0.50217559 |
| large_consequence | 60.0670% | 0.46845613 | 58.1083% | 0.50292105 |

Paired differences from unchanged v4 on recent validation families:

| Cell | Ordinary NLL delta ± SE | Weighted NLL delta ± SE | Consequential-card NLL delta ± SE |
|---|---:|---:|---:|
| current_ordinary | -0.00022328 ± 0.00036183 | -0.00024295 ± 0.00036152 | -0.00002275 ± 0.00176146 |
| large_ordinary | +0.00003622 ± 0.00045571 | +0.00001879 ± 0.00045524 | +0.00067226 ± 0.00240732 |
| current_consequence | -0.00023000 ± 0.00036265 | -0.00024872 ± 0.00036225 | -0.00008867 ± 0.00174575 |
| large_consequence | +0.00002636 ± 0.00045723 | +0.00000994 ± 0.00045676 | +0.00063426 ± 0.00238940 |

Recent clean-play paired effects; negative NLL deltas favor the first/additive treatment.

| Contrast | Ordinary NLL delta ± SE | Weighted NLL delta ± SE | Consequential-card NLL delta ± SE |
|---|---:|---:|---:|
| size_with_ordinary | +0.00025950 ± 0.00015598 | +0.00026174 ± 0.00015547 | +0.00069500 ± 0.00087193 |
| size_with_consequence | +0.00025636 ± 0.00015611 | +0.00025866 ± 0.00015557 | +0.00072293 ± 0.00087025 |
| weighting_at_current | -0.00000673 ± 0.00001141 | -0.00000577 ± 0.00001153 | -0.00006593 ± 0.00006452 |
| weighting_at_large | -0.00000986 ± 0.00001361 | -0.00000885 ± 0.00001375 | -0.00003800 ± 0.00006850 |
| average_size_effect | +0.00025793 ± 0.00015598 | +0.00026020 ± 0.00015545 | +0.00070896 ± 0.00087080 |
| average_weighting_effect | -0.00000829 ± 0.00001172 | -0.00000731 ± 0.00001185 | -0.00005196 ± 0.00006271 |
| interaction | -0.00000314 ± 0.00000905 | -0.00000308 ± 0.00000908 | +0.00002792 ± 0.00004449 |

## Fit and checks

One seed, conditional on this initialization. Family SE does not capture retraining uncertainty. Selected-epoch contrasts are descriptive after selection; primary contrasts use fixed epoch 3. This tests a short continuation after widening, not training a larger model from scratch or tuning its learning rate. No arena or reserved test evaluation.

| Cell | Epoch seconds | Total wall seconds | Initial max logit error vs v4 | Export max error |
|---|---|---:|---:|---:|
| current_ordinary | 35.8, 36.5, 36.5 | 145.2 | 7.15e-07 | 3.58e-07 |
| large_ordinary | 51.4, 50.9, 50.8 | 189.8 | 9.54e-07 | 2.38e-07 |
| current_consequence | 37.0, 36.1, 37.5 | 147.7 | 7.15e-07 | 4.77e-07 |
| large_consequence | 50.2, 51.2, 51.2 | 190.7 | 9.54e-07 | 3.58e-07 |

Each fit: 998,425 positions, 31,120,476 uncertain-card targets, 89,652 training families. Recent training: 22,467 positions, 345,490 targets, 1,408 usable families, including 11,413 upweighted targets. Recent validation: 3,063 positions, 192 usable families, 47,004 uncertain-card targets, 1,687 upweighted targets in 130 families. All 186 reserved test families remain unprepared and unevaluated. Every trajectory involving the bad v4/4p policy was excluded; 4b was retained.

Metrics average within each family, then across families. Consequential-card-only metrics use families with at least one upweighted target. Card targets and positions from the same deal are correlated; the 31.1 million targets are not 31.1 million independent examples. Epoch timings include training and validation, but exclude worker startup and initial baseline evaluation.

The complete controlled pipeline took 11.28 minutes, excluding earlier superseded work. All exported weight arrays exactly match their selected TensorFlow checkpoint. Prediction checks cover validation samples from historical play, bidding, BEN, and recent play; maximum errors and restored AdamW iteration counts are in the JSON.

Full domain metrics, all epoch curves, paired differences from v4 at every epoch, primary factorial contrasts and selected-checkpoint contrasts are in the companion summary JSON.
