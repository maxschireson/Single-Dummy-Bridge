# Shape and honor layout geometry: 2026-11-10

A fixed 32-coordinate representation gives a stronger initial result than the learned embedding in this finite-pool diagnostic. Shape-plus-honor cosine has 27.4% lower family-balanced decision regret than random selection (18.8% lower when weighting positions equally). Ordinary distance is close. The comparison with the neural embedding remains inconclusive; its paired 95% interval includes zero. No production player has changed.

## Representation

Each player/suit contributes one remaining-card count and one honor-strength sum: 16 shape coordinates plus 16 strength coordinates. Honors use A=4, K=3, Q=2, J=1, T=0.5, lower spots=0. Known hands are masked before normalization. The same weighted-medoid reducer and cluster-mass weights are used for all deterministic geometries.

For a same-suit exchange between hidden hands, K–Q changes two strength coordinates by one point each; K–5 changes them by three points. Their squared Euclidean distances are 2 and 18 respectively. Exchanging diamond K with club A also changes suit lengths and the suits carrying strength. Two small spots of the same suit can be identical under this representation. These are similarity assumptions, not exact DDS equivalence guarantees: specific ranks, entries and combinations can still matter.

The cosine variant normalizes these 32 coordinates. Squared Euclidean distance between unit vectors equals twice cosine distance, so the existing reducer can use it directly. This baseline has zero learned parameters.

## Optional two-weight fit

A separate training-only fit uses two nonnegative coefficients on squared shape and strength distances. It fits squared differences of centered DDS legal-action values, with equal total weight per original deal family. It used 278,976 within-position pairs from 4,359 training groups / 396 families and completed in 1.12 seconds.

The fitted coefficients are 0.006502658790237348 for shape and 0.0028107690182863363 for strength. Only their ratio affects selection. This fit improves contrast MSE but does not improve decision regret over the fixed geometry. Better pair-distance prediction need not imply better action choice.

## Validation

The screen covers 709 early positions from 62 validation deal families. It reduces 32 to 8 or 64 to 16 saved distinct layouts, with uniform input mass. Regret is the loss of average DDS tricks from the selected action, evaluated against the same full candidate pool. Random selection is averaged over 64 draws per position. Confidence intervals resample whole deal families 5,000 times; the primary aggregate weights families equally.

All baseline definitions and the two-weight fitting procedure were fixed before their validation outcomes were inspected. This remains an exploratory comparison of several methods; individual intervals are not adjusted for multiple comparisons. The validation families were already used to select the neural checkpoint. The reserved test families remain untouched.

| Selector | Family-balanced regret | Group-balanced regret | Family delta vs random, 95% CI |
|---|---:|---:|---|
| Random | 0.017680 | 0.017481 | +0.000000 [+0.000000, +0.000000] |
| Card identity | 0.014725 | 0.015930 | -0.002955 [-0.005994, -0.000009] |
| Shape only | 0.015784 | 0.015613 | -0.001896 [-0.006868, +0.004657] |
| Honor strength only | 0.015860 | 0.017147 | -0.001820 [-0.005083, +0.001166] |
| Shape + honor strength | 0.013049 | 0.014259 | -0.004632 [-0.007739, -0.001703] |
| Shape + honor strength, cosine | 0.012829 | 0.014201 | -0.004851 [-0.008024, -0.001887] |
| Shape + honor strength, 2 fitted weights | 0.015717 | 0.016543 | -0.001963 [-0.004892, +0.001050] |
| Neural embedding, NumPy | 0.015414 | 0.014713 | -0.002266 [-0.006227, +0.002154] |
| Shape + honor, random representative per cluster | 0.017256 | 0.017056 | -0.000424 [-0.001498, +0.000643] |
| Oracle DDS labels | 0.001181 | 0.001184 | -0.016499 [-0.018366, -0.014741] |

The first 400 groups exactly match the prior screen, and the additional 309 are also included. Both subsets are tabulated separately in the JSON result; they are not independent deal-family test sets. Card-identity and oracle regrets reproduce exactly on the original 400 groups.

The neural comparator uses the exported NumPy model. In five of the first 400 groups, sub-1e-6 embedding differences between NumPy and PyTorch change deterministic medoid selections and action regret. The original PyTorch outcomes reproduce exactly when that inference path is used; the audit records these cases. Thus small differences from the earlier neural table are expected. The simpler geometry's comparison with random does not depend on this issue.

For cosine versus random, the family-balanced regret difference is -0.004851 tricks, with an individual 95% interval [-0.008024, -0.001887]. For cosine versus the neural embedding, it is -0.002585, with interval [-0.007394, +0.001927]. The evidence favors the simple geometry over random in this proxy, while its superiority over the neural model is not established.

## Runtime and next decision

One-thread timing for 128 layouts and 32 selected representatives, averaged over 300 repetitions:

| Method | Feature encoding | Selection | Total |
|---|---:|---:|---:|
| Fixed shape + honor | 0.201 ms | 1.205 ms | 1.405 ms |
| Fixed shape + honor, cosine | 0.217 ms | 1.209 ms | 1.426 ms |
| Two-weight fit | 0.200 ms | 1.197 ms | 1.398 ms |
| Neural embedding | 0.759 ms | 1.197 ms | 1.955 ms |

Timing rows span positions and measure computation only. Selection now dominates; the feature representation itself is roughly 3.5 times faster than the neural encoder.

Use fixed shape-plus-honor geometry as the next baseline, retaining ordinary and cosine distance as close alternatives. The decisive next comparison is weighted 128-to-32 selection using the current belief sampler, against current top-32 and random-32 selection, with an independent high-effort reference and paired play. This finite-pool experiment cannot establish playing strength or superiority to full 128. It also does not justify applying belief probabilities twice to samples already drawn from that distribution.

## Reproduction

Prepared data and neural checkpoint are in the first-fit bundle referenced by the previous report. Run from the repository root with NumPy and SciPy installed:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python scripts/screen_layout_geometry.py --data runs/layout-embedding-20261110/data --neural runs/layout-embedding-20261110/fit/best.npz --out runs/layout-embedding-20261110/simple-geometry --repeats 64
```

The screen and timing completed in 22 seconds on one low-priority CPU thread. Seven targeted tests pass, including the K/Q versus K/spot and cross-suit-ace examples, small-spot interchangeability, and the reducer/encoding tests from the first fit. See [machine-readable results](data/layout-geometry-baselines-20261110.json) for configuration, file hashes, training coefficients, validation subsets, confidence intervals, timing and the inference audit.
