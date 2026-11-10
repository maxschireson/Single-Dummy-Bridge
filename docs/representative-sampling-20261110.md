# Representative sampling experiment — 2026-11-10

The implementation is an opt-in change to the PIMC sampling path. The active experiment is restricted to positions with **10–13 tricks remaining**, using **128 fresh belief draws and at most 32 DDS representatives**. Smaller positions retain the existing player. No production promotion has occurred.

## Completed 200-position screen

The screen is complete: 200 large positions from 200 independent validation families, with settings frozen in advance. The large-only execution took 950 seconds (15.8 minutes), reusing 22 verified cases from the earlier mixed-scope run. There is no production promotion.

| Method | Mean DDS solves | Mean regret, tricks | Mean total CPU |
|---|---:|---:|---:|
| Current random 32 | 32.00 | 0.011799 | 245.2 ms |
| Random, matched solve count | 28.11 | 0.011154 | 234.4 ms |
| Cluster masses | 28.11 | 0.008465 | 258.5 ms |
| Fit candidate-pool moments | 28.11 | 0.008243 | 260.0 ms |
| Fit exact belief moments | 28.11 | 0.007670 | 260.6 ms |
| All 128 draws | 128.00 | 0.003599 | 940.0 ms |

Exact-belief weighting has 35.0% lower mean regret than current random32 at 6.3% more CPU in this benchmark. The paired improvement is **+0.004130 tricks per position**, standard error **0.003354**, about **1.23 standard errors**. Its individual 95% family-bootstrap interval is **[-0.002359, +0.010863]**, so the improvement is not established.

Full128 remains stronger on this screen. Exact-belief representatives lose 0.004071 tricks per position relative to full128 (individual 95% interval [-0.009021, -0.000579]) while using 27.7% of its CPU time. The representatives recover about half the point-estimate gain from going from random32 to full128. These are offline DDS action-value results, not IMP gains.

The matrix calibration's advantage over simple cluster weights is small and inconclusive: +0.000795 tricks, interval [-0.004098, +0.004411]. All 200 fits converged; standardized feature-moment error fell from 0.009511 to 0.000355 on average. Better matching of linear features alone does not guarantee better nonlinear DDS decisions.

At the quarter-trick regret threshold, random32 had 2 mistakes, cluster masses had 0, pool-moment fitting had 1, exact-belief fitting had 1 and full128 had 0. These small counts do not establish tail-risk differences.

All 20 preselected reference checks completed. On that subset, doubling the reference from 512 to 1,024 changed the mean belief-versus-random32 comparison by -0.000057 tricks. Only three of those cases had nonzero paired value differences; this limited sensitivity check does not rule out reference noise elsewhere.

The saved-label audit reproduces every recorded representative estimate and reference value with zero error. Thirty-one targeted/regression tests passed, followed by the focused seven tests after removing the optional value-model dependency. A complete native-DDS game on a development deal also passed: 52 legal plays, 15 reduced decisions, 27 ordinary decisions and 10 forced plays.

The implementation is ready for further testing. This result does not yet justify enabling it by default, and it does not establish that fitted weights beat simple cluster weights. See [screen results](data/representative-large-200-result-20261110.json), [paired analysis and audit](data/representative-large-200-analysis-20261110.json), and [native integration check](data/representative-large-200-native-smoke-20261110.json).

## Selection and weighting

1. Draw all 128 layouts through the existing `WeightedSampler` at strength 1. Keep duplicate draws: their multiplicity already encodes belief probability. Do not multiply by belief probabilities a second time.
2. Encode the unknown hands with 32 linear features: suit lengths and suit honor-strength sums. A/K/Q/J/T weights are 4/3/2/1/0.5; lower spots have zero honor strength.
3. Apply average-linkage hierarchical clustering with cosine distance. Cut at a fixed distance tolerance, subject to a ceiling of 32 clusters. The number can be smaller; every draw belongs to a cluster. Choose an actual layout minimizing average within-cluster distance.
4. Solve only those representatives with DDS, and aggregate legal-action utilities with nonnegative weights summing to one.

Three weighting modes share exactly the same representative layouts:

- `cluster`: each cluster's fraction of the 128 draws.
- `pool`: fit the selected layouts to the 128 draws' mean features.
- `belief`: fit to expected features under the sampler's full constrained distribution.

The third mode addresses sampling imbalance in the 128. The sampler's dynamic program already computes ownership marginals conditioned on visible cards, remaining hand capacities and observed voids. Expected suit length is the sum of ownership probabilities in that suit; expected honor strength is the same sum multiplied by the honor values. These expectations are exact **under the sampler's factorized, legally conditioned belief model**, not under an unknowable true posterior.

If A contains the selected layouts' feature vectors as columns and mu is the desired feature mean, the fit minimizes

```text
||D(Aw - mu)||² / 32 + 0.001 * k * ||w - 1/k||²
subject to w >= 0 and sum(w) = 1.
```

D scales each coordinate by the inverse of its candidate-pool standard deviation, with a 0.5-unit floor. The small ridge discourages concentrated solutions; it is toward uniform selected weights, not noisy cluster counts. Cluster masses initialize the optimizer and serve as a failure fallback. Residual error and weight concentration are logged.

These are **quadrature weights**, not exact probabilities of geometric clusters. Matching linear moments does not match all joint patterns or nonlinear DDS values. If the selected layouts cannot represent the target mean, the residual remains visible. No weighting can recover a qualitatively different layout missing from the candidate pool.

## Fixed settings

The cosine distance tolerance is **0.04214601748644102**. It was set from the median 32-cluster cut distance on fresh pools from 12 training deal families, without DDS labels. The solver budget, tolerance, feature weights, ridge and sampling seeds were frozen before the expanded evaluation.

The optional 64-to-16 middle-stage code is retained for later experimentation but `medium_enabled` is false. It is outside the current test.

Enable through `layout_reduction` on `PIMCPlayer`, `CombinedPlayer` / public-belief descendants, or the corresponding arena bot specification. The checked-in [experiment configuration](../configs/representative-sampling-experiment.json) supplies the settings. Omitting the option uses the original code path; below the cutoff the RNG stream and decisions are unchanged.

Weighted action estimates preserve the existing trick/score/make objectives, defender orientation, near-tie window and policy-reranking interface. IID standard errors are deliberately unavailable for deterministic representatives with calibrated weights.

## Evaluation protocol

The expanded screen uses **200 positions from 200 independent validation deal families**, all with 10–13 tricks remaining. It excludes every family in the earlier geometry corpus and all reserved test families. Actual public trajectories are replayed from checksummed clean sources; v4/v4p play remains excluded.

Each position has a complete fresh 128-layout candidate pool and an independently seeded **512-layout reference**. Twenty families, selected before results, get **1,024 reference layouts** to assess reference noise. Primary evaluation still uses the first 512; the doubled result is a sensitivity check.

Compare current random32, full128, clustering with each of the three weight modes, and random sampling matched to the actual cluster count. Current32 and random32 are the same sampler; no top-probability truncation is used. Report expected action value, regret, variability, quarter-trick mistakes, whole-family confidence intervals, representative count and total CPU cost.

Choices and weights are fixed before any candidate or reference DDS values are read. Sampling, exact moment calculation, feature construction, clustering, weight fitting and DDS costs are included. DDS timing uses separate fresh contexts and disables persistent caches; production cache reuse can change the tradeoff. The matched-count control approximates its draw time proportionally; other draw counts are timed directly.

The 512-layout reference is noisy, but paired value differences share that independent reference. The same-pool average is not treated as ground truth. This is an offline action-choice screen without policy reranking, not an IMP or whole-play result.

## Implementation pilot

The 72-position development pilot (24 deal families at three stages) completed in 225 seconds. At large positions, mean regret was 0.007372 tricks for random32, 0.004557 for full128, 0.012166 for cluster weights and 0.012085 for exact-belief moment weights. The belief-versus-random32 improvement was -0.004713 tricks with a 95% interval [-0.030478, +0.012716]. This did **not** establish a gain.

All 72 exact-moment optimizations converged. Mean standardized moment error at large positions fell from 0.008500 to 0.000714, demonstrating that matching features better need not improve action decisions. Smaller-stage results also did not support enabling that reduction. They are outside the user's simplified large-only experiment.

The larger screen replaced an initially mixed-stage run after the scope correction. Twenty-two completed large-position cases were reused only after verifying identical public states, seeds, model, solver, settings and reference sizes. Original records remain available; the reuse manifest records provenance.

## Reproduction

The checkpoint bundle contains the frozen observations, model, solver, candidate/reference labels, configuration and per-position records. Code is in this research branch. NumPy and SciPy are required; no neural training framework is needed for inference or weight calibration.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python scripts/test_representative_sampling.py \
  --data runs/layout-embedding-20261110/data \
  --belief /path/to/belief.npz --library /path/to/libbridge_dds.so \
  --out runs/representative-large-200-20261110 \
  --context-file runs/representative-large-200-20261110/frozen-contexts.json \
  --config-file configs/representative-sampling-experiment.json \
  --extended --large-only --validation-families 200 --reference 512
```

Completed positions are checkpointed individually and skipped on resumption. Input hashes and paths must match the recorded inputs. The reserved test families are not evaluated. The job uses one low-priority CPU thread, preserving the concurrent belief-net research priority.

