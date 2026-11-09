# Policy choices from matched branch continuations — 2026-11-09

The current Gen4 policy shows weak ranking on the recorded alternatives. A new
pairwise-ranking fit largely recovers Gen3's choices and makes a small additional
improvement on untouched test families. Its IMP advantage over Gen3 is not yet
statistically established. No arena model was replaced.

## Frozen evidence

The snapshot contains 3,046 distinct canonical deal families from the independent
supplemental and component arenas. It contains 129,250 nonidentical, completed,
audited action contrasts; 2,672 families supply at least one such contrast.
Every completed continuation was legally replayed, its score recomputed, the
matched prefix checked, and its reward oriented to the acting partnership.
Reconstructed Gen4 score differences agree with logged predictions to
2.980e-8.

| Partition | Families with contrasts | Contrast rows |
| --- | ---: | ---: |
| Train | 2137 | 103515 |
| Validation / model selection | 268 | 12941 |
| Untouched test | 267 | 12794 |

Split rule: the first eight hex digits of the canonical family modulo ten select
test for 0, validation for 5, and training otherwise. This preserves the existing
80/20 training/validation separation, while splitting the old validation pool
into tuning and untouched test. All rooms, rotations, positions and descendants
of a family remain together. Shared trajectories across bidding regimes are
counted once. Duplicate source families are rejected.

## Existing Gen4 policy

There are 31,036 nonidentical **mainline** comparisons between the Gen4-policy
choice and the Gen3-policy reference, across 2,533 independent families.
These include full Gen4 and the policy-only 4p variant.

- Raw outcomes: 1,920 wins, 2,175 losses and 26,941 ties for Gen4.
- Family-weighted win rate among decisive choices:
  47.81%;
  descriptive 95% CI [45.8250, 49.8011]%.
- Family-weighted gain: -0.0182
  IMP per audited mainline disagreement; 95% CI [-0.0470, 0.0105].
- Mean predicted gain: 0.003233 IMP.
- Prediction MSE: 4.011849,
  versus 4.011600 from predicting zero.
  The paired MSE difference is 0.000249,
  CI [-0.0001, 0.0006].

The ranking frequency is unfavorable, but the interval for average IMP loss
includes zero. There is no evidence of useful calibrated IMP prediction in these
data. These observations support investigating the policy; they do not by
themselves establish that it explains the whole arena regression.

| Current-policy setting | Mainline contrasts | Families | Mean audited gain | 95% CI |
| --- | ---: | ---: | ---: | --- |
| Full Gen4 | 25806 | 2080 | -0.0136 | [-0.0446, 0.0173] |
| Policy-only 4p | 5230 | 453 | -0.0394 | [-0.1150, 0.0363] |

## New fit

The 39,513-parameter network starts from Gen3's
auction/history representation, action scores and PIMC coefficient. Initialization
preserves Gen3's score contrasts to 9.090e-7.

The loss is pairwise logistic ranking, weighted by absolute observed IMP
difference and inverse number of contrasts in the family. Both winning and
losing deviations are included. Zero-IMP pairs provide no directional reward.
Only the two actually simulated moves are labeled. Hidden hands, future cards,
source IDs, family IDs and outcome labels are not model inputs.

All action/auction hidden layers are trainable; the shared state-value head
receives no policy gradient. AdamW uses learning rate 0.0001, weight decay
0.0001 and gradient clipping at 1. Twelve epochs were fixed in advance.
Minimum validation-family mainline regret selected epoch **11**;
the unchanged Gen3 initialization was also eligible. The test partition was
first loaded after epoch selection. No settings were changed after seeing it.

## Untouched test

The primary test has 3,077 mainline comparisons across 255 families. Of these,
414 have different outcomes, spread across 165 families. Accuracy averages the
decisive-choice accuracy within each contributing family before averaging
families equally.

| Scorer | Better-move accuracy on decisive comparisons | Regret to the better recorded move | IMP gain versus Gen3 |
| --- | ---: | ---: | ---: |
| Gen3 | 57.88% | 0.2720 | 0 |
| Gen4 | 42.12% | 0.3007 | -0.0288 |
| New ranking fit | 58.63% | 0.2634 | +0.0085 |

Paired new-minus-Gen3 gain is **+0.0085 IMP per audited
decision**, 95% CI **[-0.0045, 0.0216]**.
The paired accuracy increase over Gen3 is
0.76 percentage points,
95% CI [-0.64, 2.15].
The new model changes 114 of 3,077 tested choices from
Gen3 (3.70%). Thus most of the improvement
over Gen4 comes from retaining Gen3, not a demonstrated large gain beyond Gen3.

New-minus-Gen4 gain is 0.0373 IMP per audited decision,
95% CI [-0.0517, 0.1264]. Its decisive-choice accuracy advantage is
16.51 percentage points,
CI [4.33, 28.69].

Including recursive held-out comparisons gives 12,634 comparisons over the same
255 families and new-minus-Gen3 gain
0.0041, CI
[-0.0014, 0.0095]. This is a secondary result;
descendants are not independent boards.

## Limits and interpretation

These are comparisons between two recorded continuations. They cannot measure
the outcome of an unaudited third move, or the cumulative effect of deploying
the new policy throughout a game. Continuation policies were frozen during
collection. Consequently, per-audit IMP differences must not be multiplied by
the number of decisions to claim an arena IMP-per-board improvement.

Audit draws are independent of predicted gain, but compute-budget admission
still filters the sample: 10,825
Gen4-policy mainline comparisons were skipped for budget reasons. No
inverse-propensity claim is made for that unknown final inclusion probability.
All uncertainty estimates use family-level means and Student-t intervals;
they are descriptive and do not adjust for repeated exploratory looks.

The saved candidate outputs **ranking scores, not calibrated IMP advantages**.
Use the rank scorer in `scripts/policy_choice_data.py`; it includes the learned
`rank_q_scale`. It is an offline experimental artifact, not a drop-in arena
promotion. Full-game evaluation on fresh families is still required.

## Artifacts and reproduction

- [Candidate weights](../models/cardplay/policy-branch-ranking-2026-11-09/candidate.npz)
- [Fit result](policy-branch-choices-2026-11-09/result.json)
- [Additional diagnostics](policy-branch-choices-2026-11-09/analysis.json)
- [Training configuration](policy-branch-choices-2026-11-09/config.json)
- [Epoch history](policy-branch-choices-2026-11-09/training.json)
- [Dataset manifest](policy-branch-choices-2026-11-09/dataset.json)

Candidate SHA256: `2b34b31f6e47ddce0382e89fbe7979a813d0a97cc4cc7e31cf34550dca35b715`.
Parent Gen3 policy SHA256: `8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5`.
Current Gen4 policy SHA256: `e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed`.

The derived dataset archive preserves source file checksums, split assignments,
features, rewards and source manifests. Separate incremental recovery archives
retain the newly collected full episodes, including all branches and audits.
They do not substitute public root-only replays for training records.

Run extraction with `scripts/policy_choice_data.py`, fit with
`scripts/train_policy_choices.py --epochs 12`, and report with
`scripts/report_policy_choices.py`. Their CLI arguments require explicit
frozen source runs, dataset/output directories and parent checkpoint paths.
Re-running extraction on a later live snapshot creates a different experiment.
Three focused integrity tests cover family partitions, reward/prefix corruption
and family-weighted choice metrics. Every source continuation passes replay,
and exported NumPy ranking agrees with TensorFlow to
1.557e-6.

## Gen4 self-play cancellation

The supplemental collector now skips 3,993 unplayed 4-versus-4 slots, retains
1,007 completed self-play episodes, and continues every other frozen slot.
Its active endpoint is 6,007 complete records instead of the original 10,000
scheduled slots. Its source manifest remains unchanged; a separate immutable
cancellation plan and the recovery automation enforce the exclusion.
The 10,000-board component arena already has no 4-versus-4 slots.

The inaccessible Codex primary/recovery hosts have not been changed by this
session. Their remaining 4-versus-4 games still require the same operational
cancellation on those hosts.

