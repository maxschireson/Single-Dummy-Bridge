# Harvesting Stu rollout decisions and targeting the learning frontier

Status: recommendation for loop / Stu lead review, 14 November 2026. Requested by Max in the data-efficiency discussion. No collection, training recipe, model, or box allocation changes are made by this proposal.

Requested reviewer: **loop**, session_01N2EvxDPjdoFBFtyygdYP4j, the Stu owner identified on the coordination board and in [the review of PR #35](https://github.com/maxschireson/Single-Dummy-Bridge/pull/35#issuecomment-6883488008).

This is a focused addition to [PR #35](https://github.com/maxschireson/Single-Dummy-Bridge/pull/35), not a duplicate assignment of its P01/P03 implementation or perf's P02 batching work. P07's broader collection-mix change remains deferred by loop pending P10. The new finding here concerns **inside-rollout pairs already computed and recorded**, which are different from the arena's full-bot trajectory forks.

## Recommendation

First preserve and extract the existing internal fork pairs. Test their usefulness at fixed training compute before increasing collection volume or forks per decision. Compare broad extraction with a curriculum that emphasizes the boundary of competent play and one or two tricks before it. Reserve stronger, more expensive labels for a selected subset of those positions.

Max's direction in this discussion:
- “Can we usefully harvest more decisions from our rollout based bots?”
- “More decisions at and a trick or two before the frontier of where the bots are playing well?”
- Prepare recommendations in GitHub for the Stu leader to review, approve and act on.

The 60/20/20 allocation below is an experimental starting point, not an established optimum.

## 1. What is already there, and what has actually been verified

A read-only aggregation of every JSONL record in the pinned azure5 `sp3s` output gives:

| Measure | Total | Per table |
| --- | ---: | ---: |
| Completed records / tables | 3,166 | 1 |
| Distinct deal families | 3,166 | 1 |
| Main consulted rollout decisions | 116,403 | 36.77 |
| Recorded inside-rollout fork pairs | 640,974 | 202.46 |
| Reported CPU seconds | 55,773.27 | 17.62 |
| Net inference rows inside rollouts | 505,669,110 | 159,718.61 |

The internal pairs are about 5.51 times the main-decision count. This is a count of noisy paired observations, **not a 5.51x increase in equivalent independent training information**. Inference rows are computations, not additional searched policy targets.

Evidence is pinned to feed commit `2f969fe919159f53e536d8c8dfbc8746b1ec63fa`:
- [results.jsonl](https://github.com/maxschireson/Single-Dummy-Bridge/blob/2f969fe919159f53e536d8c8dfbc8746b1ec63fa/sp3s/results.jsonl), blob `c1e1048a0f650ab3cdbf0a1c1cfda97c570ed40c`. Totals sum `cpu`, `tables`, and `search[role].x8.{consulted,forks,net_rows}` over both roles and all records.
- [manifest.json](https://github.com/maxschireson/Single-Dummy-Bridge/blob/2f969fe919159f53e536d8c8dfbc8746b1ec63fa/sp3s/manifest.json): seed 9001, first index 360000, one room, frozen runtime `ba98377a97536e1324546da77831c2e9d86816ab`; both actors configure capture level 2, 128 retained layouts, and up to 8 internal pairs per rollout decision.
- [EPISODES.txt](https://github.com/maxschireson/Single-Dummy-Bridge/blob/2f969fe919159f53e536d8c8dfbc8746b1ec63fa/sp3s/EPISODES.txt) explicitly reports “3166 episode files, 107 MB, on azure5 under ~/work/loop/runs/sp3s/episodes”.

**Availability boundary:** the summary counts and episode-location notice are directly verified on GitHub. The raw episode payloads are reported on azure5; they are not uploaded in this run's feed. This review has not opened those remote files, checked their current survival after the resize, or validated every pair. The summary alone cannot reconstruct the pairs. H01 therefore checks and preserves the actual episodes before any claim that all 640,974 are recoverable training examples. No new games should be needed for this cohort if its advertised episode files are intact.

The runtime's summary counts `len(note['forks'])`; these are recorded pairs, not just a configured budget. Claims and lack of a genuine alternative can reduce the configured eight.

## 2. Why the current trainer misses them

The inspected research source is pinned to `5addd826af8b10d7343df51ada528a7327d059b6`:

- [x8_rollout.py](https://github.com/maxschireson/Single-Dummy-Bridge/blob/5addd826af8b10d7343df51ada528a7327d059b6/bridge_harness/x8_rollout.py) creates a later-position pair: the net-selected card versus a distinct alternative, with both continuations played to the end by the rollout net.
- [x8_capture.py](https://github.com/maxschireson/Single-Dummy-Bridge/blob/5addd826af8b10d7343df51ada528a7327d059b6/bridge_harness/x8_capture.py) writes each pair under the parent decision's `x8.forks`. It stores the imagined layout, root card, intervening prefix, seat, both cards, their probabilities and both final trick counts. `fork_view` reconstructs the acting seat's legal observation.
- [gen7_build_dataset.py](https://github.com/maxschireson/Single-Dummy-Bridge/blob/5addd826af8b10d7343df51ada528a7327d059b6/scripts/gen7_build_dataset.py) emits rows for explicit episode table actions. It uses the root's rollout candidate values but does not read `x8.forks` or call `fork_view`.
- [train_rollout_net.py](https://github.com/maxschireson/Single-Dummy-Bridge/blob/5addd826af8b10d7343df51ada528a7327d059b6/scripts/train_rollout_net.py) consumes those emitted rows; it has no separate internal-pair loss.

These pairs are distinct from full-bot audit/gap fork tables. The latter generate new searched decisions and are already supported by the ordinary builder. No claim is made that the internal pairs have never been used by any other experimental branch; the gap is in this inspected Stu training path.

## 3. Extract useful evidence rather than imitate the existing net

| Material | Value as extra training data | Proposed treatment |
| --- | --- | --- |
| Root decision, all candidate means | Already used by the gap loss | Preserve; do not count candidates as independent decisions |
| Ordinary internal rollout action | Selected by the existing net | Imitation alone supplies little new supervision; do not flood policy training with it |
| Internal alternative-action pair | Additional outcome evidence at a new position | Extract as a separate, noisy signed comparison |
| Full-bot continuation fork | New decisions evaluated by the complete bot | Separate future experiment; materially more expensive |

For a paired record, define the target as
`delta = sign * (main_declarer_tricks - alternative_declarer_tricks)`,
where sign is +1 for the declaring partnership and -1 for defenders, using the observation's **controller** (dummy is controlled by declarer).

Do not turn the winning card in one sample into an authoritative best-card target, clip negative evidence away, or mark the forced alternative as a naturally chosen policy action. A signed value-difference regression can learn the mean advantage across examples; a winner-only classifier generally learns a different quantity.

The current two continuations use the same imagined layout but have stochastic subsequent play. They are not eight independent re-evaluations of the same information state, nor values averaged over the new player's posterior. Retain ties and negative results.

Important implementation choices for loop:
- Initially use a separately weighted auxiliary pair objective/head, or explicitly reconcile the existing gap head's semantics. Root values can be claim-floored; the inspected internal continuations finish **without claims**. Their raw trick outcomes are not interchangeable with guaranteed-contract/floored targets.
- Model inputs remain the reconstructed player's own observation. Full sampled hands are reconstruction/label data only.
- Preserve parent family, episode hash, root action, fork ordinal, root and fork ply, role, contract, actor/net hashes, capture schema and target provenance.
- Family splitting follows the original parent deal, even when the imagined layout differs. No descendant of a held-out parent enters training.
- Exact duplicate pair/state records must not receive repeated credit. Do not blindly discard distinct histories that happen to leave the same remaining cards.
- The fork payload does not itself retain every inclusion propensity or layout weight. Recover what can be justified from parent capture; label the remainder as unknown. Do not invent importance weights or claim unbiased single-dummy values.
- Keep pair weight and source quotas explicit so 202 pairs do not automatically overwhelm 37 stronger root decisions.

## 4. Target the frontier, not merely the latest or noisiest tricks

Use separate profiles for declarer and defense, and at least trump contracts versus notrump. Trick number is a first organizing variable, not a complete measure of difficulty.

A frontier is the transition where later play is sufficiently reliable but earlier decisions still lose value. If that were trick 8, an initial focus would be tricks 6–8. This is illustrative; no fixed trick-8 frontier has been established.

Measure it using held-out or separate diagnostic families:
- Frequency and magnitude of decision losses, with uncertainty clustered by parent family.
- Whether the correct continuation was among the candidates.
- Whether the rollout/value ranking, the proposal net, or later execution caused the loss.
- Training response by phase: an error-rich region is not necessarily a learnable region with current labels.
- Contract relevance, alongside mean tricks; an apparent late mistake can have been forced by an earlier decision.

Suggested allocation of the **extra pair budget**, while keeping ordinary root data broadly distributed:

| Share | Target |
| --- | --- |
| 60% | Measured frontier and one or two tricks before it |
| 20% | Other consequential disagreements / failure regions |
| 20% | Broad random coverage to detect drift and unseen weaknesses |

Prefer diverse families and genuinely distinct alternatives. High policy entropy alone is a poor priority score because several cards may be equally good. Keep losses in both directions; do not select only surprisingly successful alternatives or one-sample large gains. Such selection can favor noise.

Existing forks are scheduled at random later turns. First simulate the proposed curriculum by stratifying/reweighting existing pairs, where support permits. Report realized phase counts and effective weights. If a desired cell is sparse, do not manufacture volume by repeating it; that becomes a targeted collection request.

Move the emphasis earlier only when the current band improves on separate diagnostic families without material regression elsewhere. Do not tune the frontier using the final BEN gate or the reserved squeeze tests.

## 5. Selectively improve the labels

After the cheap pair test, select a small subset for fresh analysis from the fork player's observation:
1. Resample hidden hands consistent with that player's information and the public history.
2. Evaluate both candidate cards on the same new layouts, with suitable coupled randomness where valid.
3. Keep signed mean differences, uncertainty, sample counts and target semantics.
4. Compare the result with the original single-layout pair to measure reliability by phase.

Masking hidden cards from inputs alone does not fix the sampling issue: the original imagined layout was conditioned on an earlier player's private information. Selective re-analysis addresses that and tests whether the initial pair is a useful learning signal.

Use independent verification for positions selected because their original outcome looked unusually favorable. A small random verification sample is needed too. Measure benefit per labeling CPU-hour before enlarging this budget.

## 6. Controlled experiment and acceptance

The first three-arm experiment can use already-collected games, conditional on H01:

| Arm | Training |
| --- | --- |
| A | Existing root/replay recipe; compute-matched control |
| B | Same recipe plus a broad sample of internal pair comparisons |
| C | Same recipe plus the same pair count, targeted by frontier strata |

Hold constant the starting net, architecture, base-data mix, target semantics and training compute. Match B/C's pair count and loss weight. Match A's compute with a stated baseline schedule rather than quietly giving B/C more optimization. Report actual root presentations, pair presentations and wall/CPU/device time. Use more than one training seed for finalists if the initial effect is near noise.

The width experiment remains loop's priority. Compare these arms within one selected architecture; do not confound harvesting with a width change. A lightweight inventory/extractor can precede P10's result, while the training experiment can wait for loop's chosen slot.

Evaluation order:
1. Reconstruction and provenance checks; original-root dataset remains identical.
2. Pair reliability on a separately re-evaluated sample, including raw-vs-claim-floored semantics.
3. Held-out decision regret and calibration by phase/role, plus candidate coverage and broad regression checks.
4. Nets-alone played comparisons as a cheap strength diagnostic.
5. A promising finalist inside the complete bot at equal decision time, with the existing blind BEN release/mechanism gate. Do not launch full gates for every candidate.

The objective is improvement per **total** compute, including extraction, label verification and training. No strength gain is inferred merely from more rows or lower training loss.

## 7. Reviewable actions

| ID | Requested decision and scope | Suggested owner | Acceptance / dependency |
| --- | --- | --- | --- |
| H01 | Verify and preserve the already-collected raw episodes; inventory internal pairs across Stu feeds | loop or assigned data owner | Current file counts, hashes, decoded-pair counts, failures/quarantine, durable restore manifest; no collector restart or recipe change |
| H02 | Build an offline internal-pair extractor and reconstruction checks on a separate branch | owner assigned by loop | Rebuild legal views; controller/sign and complete-outcome checks; stable family splits; base rows unchanged; bounded memory/disk |
| H03 | Run A/B/C at matched training compute, initially modest pair weight | loop / assigned trainer | Predeclared data cut and diagnostic splits; phase and overall results; no extra BEN gate unless finalist merits it |
| H04 | Apply the frontier curriculum first by sampling existing pairs | same as H03 | B/C equal pair counts and weight; broad holdout retained; realized strata and insufficient-support cells reported |
| H05 | Re-analyze a small selected and random subset from the fork player's information | loop / assigned experiment owner | Budget stated before execution; target reliability and gain per labeling cost measured |
| H06 | Increase internal forks, or add searched full-bot continuation forks, only after H03/H05 establish value | loop with perf coordination | Measured marginal gain per CPU-hour; batching and random-stream effects checked; changed actors/runs get new identities |

Please approve, modify, defer or reject individual H IDs, assign owners and any resource budget, and distinguish offline extraction approval from a training-recipe or deployment approval. No operational action is assumed authorized by merging this recommendations document.

## Verification performed for this recommendation

- Read the active Stu source and pinned the inspected revision.
- Recomputed the full 3,166-record cohort's counts from the GitHub results blob, with unique-family checks.
- Verified the frozen run's capture settings and the published raw-episode location notice.
- Checked the builder/trainer path for internal-pair consumption.
- Read loop's PR #35 review and ownership constraints.
- Did not access the remote raw episodes, run a training experiment, alter a collector, reserve a box, or claim approval.

Bot-only data remains the rule. Seed 131 deals and the reserved squeeze suite stay out of training, including all imagined descendants. Coordinate any box work with loop before execution.
