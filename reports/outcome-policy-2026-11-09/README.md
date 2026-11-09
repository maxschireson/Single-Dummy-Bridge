# Outcome-trained policy and trick distribution — 2026-11-09

This experiment restores individual outcome prediction and compares a scalar
trick evaluator with a categorical trick distribution. Neither candidate is
trained on IMP differences. No arena model was replaced.

Neither candidate establishes an advantage over Gen3. The scalar retrain has
the larger point estimate: **+0.0203 IMP per audited mainline
decision**, descriptive family-clustered 95% interval **[-0.0233, +0.0639]**.
The primary distribution readout returns **+0.0075**, interval
**[-0.0429, +0.0579]**. These are offline comparisons of two recorded moves,
not estimates of full-game IMPs per board.

## Frozen data

| Partition | Deal families | Outcome rows |
|---|---:|---:|
| Train | 3,363 | 1,560,754 |
| Validation / checkpoint selection | 419 | 198,012 |
| Held-out test | 423 | 193,291 |

There are 4,205 canonical families, 177,945
complete trajectories, and 1,952,057
individual outcome labels. Of these, 169,329 are forced
alternative cards. Each trajectory contributes up to 16 newly executed eligible
positions, always including its forced alternative. Replayed prefixes are omitted;
completed continuations are legally replayed and their scores checked. All rooms,
positions and descendants of a family remain in one partition. Families with
no eligible positions do not contribute to prediction metrics.

Sources are the complete local supplemental and component arenas at the frozen
snapshot. The remote training feed supplies IMP contrasts but lacks individual
trick outcomes and the full search features needed for this recipe; it is not
silently counted as outcome training data. The Gen3 initialization retains the
earlier learning. Older raw training rows were not replayed in this fine-tune.

The hash-modulo-ten partition preserves the original 80/20 train/holdout boundary,
with buckets 0 and 5 reserved for test and validation. Total gradient weight is
equal per family. Multiple dependent positions are not independent boards.

## Training

Both candidates start from the same Gen3 checkpoint and use visible cards,
ordered public play, the auction, contract/vulnerability, and the existing PIMC
estimates. Hidden hands, future cards, outcomes and identifiers are excluded.
Both retain the current PIMC near-tie candidate filter (0.125 tricks), keeping the
comparison with Gen3 controlled. They do not yet test IMP-aware plays that this
trick-based candidate filter excludes.

- **Scalar:** unchanged 39,512-parameter architecture; predict
  actual remaining partnership tricks for the played/forced card using squared
  error. All layers train. Selected epoch 2 of 8 by
  validation-family MSE; epoch zero was eligible.
- **Distribution:** 40,101 parameters; 14 probabilities for remaining
  partnership tricks, with impossible counts masked. The Gen3 scalar estimate
  initializes a discrete Gaussian, with zero-initialized state/action categorical
  residual heads and a trainable global spread. Train categorical cross entropy;
  selected epoch 5 of 8 by validation-family negative log
  likelihood. No choice or IMP metric selects either checkpoint.

AdamW uses learning rate 0.0002, weight decay 0.0001 and gradient clipping at 1.
Batch size is 128. The first scalar attempt was killed before finishing an epoch;
the fit restarted from Gen3 with smaller batches and oneDNN disabled. Both final
fits use the same complete frozen dataset. Exported NumPy inference agrees with
TensorFlow within 9.54e-07 (scalar values) and
9.68e-07 (probabilities).

## Scoring distributions

The **primary IMP readout** first identifies the network's own expected-trick
choice, then freezes that move's predicted outcome distribution as the reference
for every candidate. Tied expected-trick choices contribute an equal mixture.
Each candidate is scored by averaging IMP(score(candidate outcome) minus
score(reference outcome)) across the two distributions. Contract, vulnerability,
doubles and redoubles enter exact bridge scoring.

The product of the marginal probabilities defines a virtual comparison table;
it does not claim to capture correlations between two lines on the same hidden
deal. A move compared with its own distribution has zero expected IMPs.
The fixed-contract-making reference is retained only as a prespecified diagnostic.

A regression check covers the user's hopeless doubled-contract example: when
the reference is 99% down one, the self-reference objective protects the
undertrick against an unjustified gamble for making. The fixed-making reference
can reverse that preference in the constructed example.

The same probabilities also expose a **matchpoint readout**: probability of a
better duplicate score plus half the probability of a tie, using the same frozen
reference distribution. This is a starting point, not a field-calibrated or
full-game-validated matchpoint player.

## Held-out move choices

The primary sample contains 4,156
mainline disagreements over 349
families, including 560 nonzero outcomes.
Accuracy is averaged within decisive families, then across families equally.
Regret and gain use all audited disagreements, including zero swings.

| Scorer | Better-move accuracy | IMP regret to better recorded move | IMP gain vs Gen3 | 95% interval for gain |
|---|---:|---:|---:|---|
| Gen3 outcome policy | 55.25% | 0.2772 | +0.0000 | [+0.0000, +0.0000] |
| Gen4 IMP-difference policy | 44.75% | 0.3094 | -0.0322 | [-0.1155, +0.0511] |
| IMP-weighted ranking repair | 55.71% | 0.2722 | +0.0050 | [-0.0051, +0.0152] |
| New scalar outcome fit | 58.27% | 0.2569 | +0.0203 | [-0.0233, +0.0639] |
| New distribution: expected tricks | 55.43% | 0.2726 | +0.0046 | [-0.0455, +0.0547] |
| New distribution: self-reference IMPs | 54.97% | 0.2697 | +0.0075 | [-0.0429, +0.0579] |
| New distribution: contract-made reference | 55.10% | 0.2690 | +0.0082 | [-0.0422, +0.0586] |

Earlier held-out families were previously examined for the separate ranking
experiment. On families added after that experiment's snapshot, the primary
distribution readout gains -0.0067 IMP per decision, interval
[-0.0952, +0.0818], across 94 families and 1,079
mainline choices. This subset was not used to change training or select a model.

## Held-out prediction

| Measure | Gen3 / initial distribution | New model |
|---|---:|---:|
| Scalar trick MSE | 0.437453 | 0.443110 |
| Distribution mean trick MSE | 0.437453 | 0.496047 |
| Distribution negative log likelihood | 0.966254 | 0.890301 |

The distribution's probability loss improves relative to its initialization,
while its mean-trick error worsens. The NLL baseline is Gen3's mean wrapped in the declared initial Gaussian;
Gen3 itself did not output a categorical distribution. Prediction improvements
must not be treated as proof of better action choices.

## Limits and artifacts

Continuation policies were frozen mixed bots. These fits forecast their observed
outcomes, not optimal future play. Recorded comparisons label two moves; an
unaudited third move has no measured counterfactual outcome. Admission to fork
collection was compute-budget limited. Confidence intervals cluster by canonical
family and are descriptive; they do not correct for comparisons across variants.
Full-game evaluation on fresh families is required before promotion.

- [Scalar weights](../../models/cardplay/outcome-policy-2026-11-09/scalar.npz)
- [Distribution weights](../../models/cardplay/outcome-policy-2026-11-09/distribution.npz)
- [Scalar results](scalar-result.json)
- [Distribution results](distribution-result.json)
- [Frozen dataset manifest](dataset.json)

The frozen encoded dataset is preserved as
[Outcome_Policy_Training_Data_2026-11-09.zip](https://chatgpt.com/library?file_id=libfile_fde3_f-22ef5bd53ac88191867de52f7905ade9_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).
Reproduce with `prepare_outcome_policy.py`, `train_outcome_policy.py`,
`train_distribution_policy.py`, and `report_outcome_policy.py`, supplying the
frozen source runs and checkpoint paths. `mixed_arena.selector` recognizes
distribution checkpoints in this experimental branch; no running arena changed.
