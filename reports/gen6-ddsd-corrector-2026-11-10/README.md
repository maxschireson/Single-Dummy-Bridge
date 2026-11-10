# Gen 6 candidate: full-deal DD-to-single-dummy corrector

This first candidate improves prediction of actual continuation outcomes, but
has not demonstrated stronger card selection. It is not promoted and no arena
configuration changed. Max designated this approach Gen 6 if validated.

## Target and data

The supervised target is observed remaining acting-partnership tricks minus
the double-dummy value **on the actual deal for the actual chosen card**.
Training does not subtract a sampled PIMC average. At inference, the same critic
is applied separately to each sampled deal, then the corrected values are
averaged across common worlds for all candidate cards.

The existing policy-clean normalized corpus contains 5,679 canonical deal
families. A deterministic, outcome-blind sample takes up to 16 genuinely
executed decisions per family: six from the first four tricks, six from the
middle, and four from late play. Replayed branch prefixes are excluded and
duplicate trajectories are removed. No additional games or forks were collected.

- Training: 72,064 chosen-action examples, 4,504 contributing families.
- Validation: 9,488 examples, 593 contributing families.
- Test: 9,232 examples, 577 contributing families.
- Total: 90,784 examples; five families have no eligible play.
- Existing diagnostic forks: 1,373 validation and 1,370 test comparisons.
- True-deal labelling: 91,051 DDS solves, approximately 156 seconds wall time
  with two workers, including reconstruction and validation.

All active V4/V4p play remains excluded. V4 belief with a clean play policy is
allowed, as in the source corpus. Training uses older frozen continuation
policies, not current Gen5/5R play. This is an initial feasibility experiment;
current-generation adaptation remains necessary before deployment.

The source's canonical family split is preserved: hash modulo ten 0 is test,
5 is validation, otherwise training. Rotations, rooms, prefixes and descendants
stay grouped. Source file hashes, original policy provenance, labels and splits
are retained in the data archive. Every selected continuation is legally
replayed to its recorded final tricks and duplicate score.

## Model and selection

The critic has 107,421 parameters: full original card ownership relative to the
controller, remaining cards, ordered public history, current trick, candidate
card, legal moves, contract context, auction embeddings, DD value, and coarse
continuation-policy descriptors feed a 128/64 dense network. Hidden ownership
is explicitly permitted in the critic. Actual hands are never supplied to the
root chooser during sampled evaluation.

The output starts at zero. Training uses ordinary residual MSE with equal total
family weights; there is no fork or preference loss. Twenty epochs were run;
validation outcome MSE selected epoch one. Later epochs overfit. The correction
weight was selected from 0, 0.25, 0.5 and 1 using validation outcome MSE; it
selected 1. The test outcomes were read after this selection was fixed.

## Initial held-out results

| Test | DD baseline | Corrected | Interpretation |
|---|---:|---:|---|
| True-deal outcome MSE | 0.331672 | 0.322172 | 2.86% lower; paired change −0.009501 ± 0.003251 SE |
| First-four-trick outcome MSE | 0.651069 | 0.630605 | 3.14% lower |
| True-deal fork-difference MSE | 0.134785 | 0.134270 | Improvement inconclusive |
| Sampled fork-difference MSE | 0.141633 | 0.140974 | Improvement inconclusive |

After averaging over 32 common worlds using each recorded actor's original
belief model, selection among the two recorded cards gains **0.01044 IMP per
comparison**, SE 0.01484, 95% interval [−0.01864, +0.03953], within a 0.125-trick
pairwise window. This is not IMP per board or a whole-game strength result.
The test has 379 contributing fork families. Only 89 of 1,370 comparisons have
different realized trick outcomes; 1,239 are exact ties in the newly sampled
PIMC values. Baseline exact ties receive half credit for each recorded move.

## Hidden-ownership control

A second network uses the same architecture, labels, training procedure and
validation selection, while masking ownership of unseen cards. It retains all
observed cards and the **true-deal DD scalar**, which itself carries privileged
information. This is not the existing V5 policy model. It tests the added value
of explicit hidden-card arrangement beyond visible information and true DD.

Its test outcome MSE is 0.322093 versus 0.322172 for the full-deal network.
Full-deal minus control is +0.000079, SE 0.001316, with a 95% interval of
[−0.002501, +0.002659]. No incremental benefit from hidden ownership is
demonstrated by this first architecture and dataset. The control was added as
an exploratory diagnostic after seeing the primary candidate's results.

## Current V5 policy on matched sampled forks

The deployed V5 attention selector is also evaluated using the same 32 newly
sampled worlds and the same frozen continuation outcomes. Its SHA-256 is
`03e70a6f6021c8bed471dc9de53f462b0e991320ff4ad7734bcc20f54c5aff18`.
V5 receives its normal observation and sampled PIMC values, with every action
inside the normal global 0.125-trick window encoded. The primary comparison
requires both recorded alternatives to be eligible under that rule; it retains
1,332 test forks across 378 canonical families and excludes 38 forks. All three
methods are compared on exactly those retained forks. This is a two-alternative
ranking diagnostic, not a replay of each method's preferred action among all
legal cards. Those other actions do not all have recorded continuation labels.
The PIMC column therefore selects the higher value of the two recorded cards;
it is not necessarily the global PIMC maximum. The follow-up
[fresh 256-board study](../gen6-ddsd-fresh-256-2026-11-10/README.md) explicitly
plays out the global PIMC best and each network's actual selected alternative.

| Test metric | PIMC | Sampled DD + new corrector | Current V5 policy |
|---|---:|---:|---:|
| Absolute-outcome MSE | 0.532690 | 0.532198 | 0.511841 |
| Fork-difference MSE | 0.124860 | 0.124458 | 0.126593 |
| IMP gain per comparison vs PIMC | 0 | +0.011133 | −0.008929 |
| 95% interval for that IMP gain | — | [−0.018652, +0.040918] | [−0.040464, +0.022607] |

The corrector's direct advantage over V5 is +0.020062 IMP per comparison,
SE 0.017875, 95% interval [−0.014974, +0.055098]. No test choice advantage is
established. V5's absolute-outcome MSE is lower, while its difference MSE is
higher; both paired MSE differences versus PIMC are inconclusive. This pattern
is consistent with better state calibration without better action selection,
but does not by itself establish that mechanism.

There are only 80 forks with unequal realized outcomes in this subset, and
1,227 of the 1,332 are exact PIMC ties. Exact ties receive half credit. The
reported uncertainty uses equal-weight canonical-family means, not independent
fork rows. The validation subset also cautions against a strength conclusion:
V5 gains +0.041775 IMP/comparison versus PIMC there, whereas the corrector gains
+0.010173. V5 is therefore ahead on validation and behind on test.

The true-deal MSE near 0.322 above and sampled-world MSE near 0.532 here answer
different questions on different example sets; they must not be compared as a
head-to-head result. The former exposes the actual hidden layout (or its DD
scalar in the masked control), while the latter averages over uncertainty.
Canonical test families were excluded from fitting both candidates, but some
were inspected during previous policy experiments. These are diagnostic
held-out results, not a fresh independent confirmation of Gen 6 strength.

## Validation and practical limits

Focused tests verify DDS before/after-card horizon and partnership conversion,
that hidden hands affect full inputs but not masked inputs, and zero-residual
initialization. The sampled test reconstructs each information set, samples
without access to the true hidden hands, and supplies identical worlds to both
card evaluations. Full and masked models use matched test examples.

Neural inference for 416 rows (32 layouts × 13 cards) takes approximately
1.2 ms on one CPU thread, excluding encoding, sampling and DDS.

The present evidence supports learning a residual, but does not establish that
the model learns the action-specific consequences of hidden-card arrangements.
The immediate research question is how to represent those consequences more
effectively. Additional forks are not a prerequisite for further training.

## Reproduction and artifacts

Source: `bridge_harness/ddsd_corrector.py`, `scripts/prepare_ddsd_corrector.py`,
`scripts/train_ddsd_corrector.py`, and `scripts/evaluate_ddsd_sampled.py`.
The fitter needs PyTorch and NumPy; extraction needs NumPy and the existing DDS
binary. The baseline V5 scorer remains the existing NumPy implementation.

Use `--help` for explicit source, model, output and library arguments. Output
directories are immutable and must be new. The saved data archive contains
labelled inputs, source provenance, model checkpoints, predictions, sampled
fork positions, training histories and checksums. It is sufficient to retrain
without recalculating DDS. Rerunning sampled comparisons also requires the
original clean episode files and their frozen belief weights.

[Data and candidate checkpoints](https://chatgpt.com/library?file_id=libfile_fde3_f-92806d46076c8191a97cedf19c89a832_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).
