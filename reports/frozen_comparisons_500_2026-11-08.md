# Frozen policy+belief versus best PIMC and BEN — 8 November 2026

**The zero-band PIMC comparison is complete: 500 independent paired deals,
1,000 complete table games, fully audited.** The full-search BEN comparison is
still pending, with zero played deals while its worker waits for memory. Both
comparisons use the same frozen BEN neural-only auctions and unchanged models.

## Added follow-up: total improvement versus bidding-blind PIMC

Max clarified that the desired total-improvement control has **neither belief nor
policy inference**. A third fixed 500-deal paired comparison is now running on the
same already-reserved cohort and unchanged neural-only BEN auctions. It has priority
over the queued BEN card-play comparison. Its records live separately under `blind/`;
the original strict and BEN records, settings and protocol remain unchanged.

The candidate remains frozen policy+belief, 32 worlds and a 0.125-trick window.
The new control samples uniformly from deals consistent with visible cards, card
counts and observed voids, ignores the bidding sequence for hand placement, and
chooses the highest 32-world PIMC expected-trick estimate (zero band, uniform exact
ties). Both use native batch DDS. They share the decision seed but their sampled
worlds should differ because their samplers differ; identical-world assertions are
not applied between these two players. This directly estimates the combined change
from bidding-blind best PIMC to policy+belief, rather than adding earlier effects.

The new frozen `total-protocol.json` records 500 pairs, first-200 interim analysis,
and the original cohort/protocol hash. All 512 source deals remain evaluation-only.
This follow-up was requested after the prior result on this cohort, so it is not a
fresh independent confirmation; no model, budget or policy was tuned in response.
Report nominal original-deal bootstrap 95% intervals and retain the fixed horizon.

A focused test verifies that the control's 32 worlds match the uniform legal sampler,
that changing only the auction leaves its worlds and decision unchanged, and that
its selected PIMC gap is zero. Existing strict/BEN configurations were checked for
exact equality before and after adding this mode. All three focused tests pass.
The first real new paired deal passed full legal replay and policy/settings audit;
the auditor independently regenerates every non-forced control sample to verify
the uniform sampler hash. That completed pair is preserved on resume.

The priority run holds the shared BEN resource lock through its final audit, without
interrupting a running server. Newly launched BEN workers also check that the total
comparison has completed before starting a server. Do not start duplicate workers
or retrain models. Resume with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -u scripts/evaluate_frozen_comparisons.py --run <run> --mode play --opponent blind --workers 4
```

### Preliminary total-improvement result: first 200 deals

The fixed first 200 generation-order pairs passed full audit while play continued
toward 500. These are 200 independent deals and 400 complete table games, with
zero failed-pair records. Positive results favor frozen policy+belief.

| Outcome | Mean per paired deal | Nominal 95% deal-cluster interval |
|---|---:|---:|
| Tricks | +0.095 | -0.035 to +0.230 |
| IMPs | +0.450 | -0.095 to +1.020 |

IMP wins/ties/losses: **56 / 103 / 41**. Both intervals include zero: the direction
is positive but the preliminary result is inconclusive. Intervals have no adjustment
for interim looks or multiple comparisons. The fixed horizon and models are unchanged.
The audit verified 20,800 legal plays, 16,482 non-forced PIMC decisions, 527,424
sampled-world solves, 6,685 policy selections and 182 selections below the sampled
PIMC maximum within the authorized band. It regenerated every non-forced blind
control sample, verified pre-action policy predictions and found no overlap with
the 63,724 exclusions. The analysis was delivered directly at this milestone.

## Authorized follow-up: 500 more deals against belief-informed best PIMC

After the bidding-blind total-improvement comparison finishes and passes its audit,
play 500 fresh independent paired deals against the same frozen belief sampler
with zero-band PIMC. This brings the belief-informed comparison to 1,000 deals and
has priority over the queued BEN card-play comparison. Neither model, the 32-world
budget, nor either player's selection rule changes.

The extension generated 512 new deals with seed 20261701 and BEN neural-only
auctions: two passed out, the first 500 playable deals were frozen for evaluation,
and ten unused playable deals remain reserved. The collector made 5,455 calls in
1.96 seconds excluding startup; 16 scalar/batch checks agreed exactly. Decision
seed remains 20261602. All 512 new deals were checked against 64,486 prior/reserved
original-deal hashes and registered as evaluation-only in the training ledger.
They cannot be used for training. Existing auctions and completed matches are retained.

The extension lives under `results/strict-belief-extension-500`. Its queue waits for
the total-comparison audit, then reserves the shared BEN server slot through play
and audit, without interrupting a running server. A focused test verifies that no
play subprocess starts before the prerequisite audit exists. All three scheduling
and player-setting tests pass.

Report the new 500 independently, plus the pooled 1,000 with original-deal bootstrap
intervals. An interim at the first 200 new deals may also show the pooled 700.
**The extension was selected after seeing the original 500-deal result.** Pooled
intervals are nominal follow-up estimates, not an originally predeclared 1,000-deal
test or a correction for optional extension. The new cohort and fixed 500-deal
horizon were frozen before its play; no outcome-dependent tuning is permitted.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -u scripts/run_belief_extension.py --base results/frozen-comparisons-500 --extension results/strict-belief-extension-500
```

The sequence worker and each play worker own separate nonblocking locks. Resume
only missing episodes if an owner exits; do not duplicate a healthy writer. Final
combined auditing checks that the two cohorts are disjoint and legally replays all
2,000 table games after both cohorts have passed their full setting/prediction audits.

## Completed first 500: policy increment over belief-informed best PIMC

| Outcome | Mean per paired deal | Nominal 95% deal-cluster interval |
|---|---:|---:|
| Tricks | +0.062 | −0.014 to +0.142 |
| IMPs | +0.080 | −0.234 to +0.408 |

IMP wins/ties/losses: **113 / 299 / 88**. Positive values favor the policy+belief
candidate. Both intervals include zero: **this test does not establish an improvement
over strict PIMC maximization with the same belief model**. It also does not establish
equivalence or rule out a modest benefit. No model or setting was changed after
the 200-deal preliminary look.

The full audit verified 52,000 legal card plays, 41,217 non-forced PIMC decisions
and 1,318,944 sampled-world DDS solves. There were 16,768 policy decisions, including
446 choices below the sampled PIMC maximum within the unchanged 0.125 window.
All 1,024 shared non-forced positions had identical sampled-world hashes and
estimates. Exact pre-action selector predictions, legal support, zero-band maxima,
partnership orientation, scores, IMPs, exclusions and all 500 unique cohort identities
passed. Zero per-pair failure records occurred. One process interruption was recovered
at 332 pairs; its cause was not established. All 390 pairs from the recovery checkpoint
are byte-for-byte unchanged.

Measured execution segments, from invocation start to each segment's last saved pair,
were 10.6 seconds for the first smoke-validation pair, 752.9 seconds for the next
331 pairs and 424.2 seconds for the final 168 pairs. These sum to **19.8 minutes**,
about **1,516 paired deals/hour** on four shared workers. First launch to final saved
pair was 27.7 minutes including intervening gaps. These descriptive timings exclude
final auditing and may omit lost work after the last saved pair of the interrupted
process; they are not a controlled hardware benchmark.

The earlier 1,000-deal gain against uniform selection inside a 0.125 window does
not establish a gain against this stronger zero-band control. The experiments use
different deals, so their effect estimates must not be added or subtracted as a
direct paired measurement of the controls. Policy training remains frozen and was
originally based on bidding-blind PIMC; no combined retraining was performed.

The complete strict-comparison records and the pending BEN cohort are preserved in
`Bridge_Strict_PIMC_500_Complete_BEN_Pending_2026-11-08.zip`. This is **not** a completed
BEN evaluation. BEN still requires approximately 5 GiB free memory and the shared
server slot; no other campaign was stopped to obtain those resources.

## Preliminary result: first 200 deals versus zero-band PIMC

The fixed first 200 original deals (400 complete table games) have passed the
full audit. Positive results favor policy+belief.

| Outcome | Mean per paired deal | Nominal 95% deal-cluster interval |
|---|---:|---:|
| Tricks | +0.060 | −0.055 to +0.185 |
| IMPs | +0.180 | −0.310 to +0.700 |

IMP wins/ties/losses: 40 / 129 / 31. This is **inconclusive**: both intervals include
zero. The control has the same frozen belief sampler and chooses only sampled
PIMC maxima. The fixed 500-deal horizon is unchanged; no model or setting has been
tuned in response to this result.

The audit verified 20,800 legal card plays, 16,444 non-forced PIMC decisions and
526,208 sampled-world solves. The selector acted on 6,663 decisions; 175 selections
were below the sampled PIMC maximum, within the unchanged 0.125 window. All 407
shared non-forced positions had matching sampled-world hashes and estimates.
Zero per-pair failure records were present at this checkpoint.

The strict comparison later reached 332 complete pairs before its process ended.
No exit reason was available, and successful records were retained. The remaining
168 pairs were resumed without regenerating completed deals. The BEN comparison
still has zero completed pairs; its waiting worker was also restarted and continues
to wait for sufficient memory. An enabled scheduled monitor had no recorded run
at this inspection, so the 200-deal result was delivered in the direct status reply.

## Comparisons

The candidate is the same frozen 46,582-parameter bidding belief sampler plus
25,170-parameter policy selector evaluated in the preceding 1,000-deal experiment.
It uses 32 sampled worlds per non-forced decision, native
`bridge_dds_all_moves_batch`, expected tricks, belief strength 1, and a 0.125-trick
near-tie window. There is no retraining or model selection.

1. **Best PIMC:** same frozen belief sampler and 32-world budget, choosing only
   moves with the highest sampled PIMC value. Its near-tie window is zero;
   uniform randomization remains only among exact maxima. This interpretation
   was stated before play. It isolates whether the policy and its nonzero
   eligibility window improve on strict maximization with the belief model present.
   Both players have identical sampled worlds and estimates at shared public histories.
2. **BEN:** pinned revision `9b5f43104aeac713a80b73513f2f2d6daf9f8769`, original
   portable full neural/DDS card-play search, IMP configuration, two DDS threads.
   Proprietary BBA/BGA/ACE/SuitC integrations are disabled as in the existing baseline.
   The card-play search is not replaced with a neural-only player.

Best PIMC here means maximizing an estimate from 32 sampled worlds; it is not
an oracle. The 0.125 window is a play-selection rule, not a statistical confidence interval.

## Shared neural-only auctions and fresh cohort

**All deals are bid by BEN's neural network only**, with search, rescue bidding
and auxiliary bid-information networks disabled. The collector loads only the
bidder. It generated 512 auctions from deal seed 20261601, with 5,323 calls in
1.89 seconds excluding startup. Sixteen scalar/batch inference comparisons agreed
exactly. One deal passed out; the first 500 playable deals in generation order
were frozen before any card-play outcomes. Eleven unused playable deals remain
reserved. Decision seed is 20261602.

The same 500 deals, auctions, contracts and vulnerabilities are used in both
comparisons. Each comparison plays two tables with candidate/control partnerships
swapped, and each player chooses its own opening lead: 1,000 table games per
comparison, 2,000 table games in total. Outcomes favoring the candidate are positive.

All 512 generated deals are evaluation-only and must not enter future training.
They were checked against 63,724 prior/reserved original-deal hashes: the previous
61,200 exclusions, all 1,024 source deals from the finished policy-over-belief test,
and the current card-play self-improvement ledger. All 512 were also registered as
external evaluation deals in that ledger. This does not alter any training setting
or model. The exclusion snapshot and reservation are retained in the raw artifact.

## Analysis and audit

Primary: candidate-oriented paired tricks per original deal. Secondary: paired
IMPs per original deal. Report 95% original-deal bootstrap intervals with 2,000
resamples. Both table games remain together in each resample. Intervals are nominal
per comparison; no claim of familywise adjustment across the two comparisons or
interim looks is made. Both fixed 500-deal horizons remain unchanged by interim results.

The 200-deal analysis uses the first 200 in generation order, never the fastest
200 completed games. Full auditing replays every card, validates scores and IMP
orientation, re-evaluates policy predictions from true pre-action observations,
checks 32-world/native-batch settings, legal support, zero-band maxima and sampled
world/estimate agreement. BEN requests are reconstructed to verify they include
only the acting controller's hand, visible dummy and public history/auction.
Failures and interrupted attempts are retained separately and never counted as
complete pairs. Existing successful episodes are validated and preserved on resume.

Two focused tests passed, including a constructed 1/32-trick gap: zero-band PIMC
retains only two exact maxima while the policy can select a different eligible move,
using exactly the same nonuniform belief-weighted worlds. A real first paired deal
also passed the full audit (104 legal card plays, 82 non-forced decisions, 2,624
sampled-world solves). That smoke-validation deal remains part of the fixed cohort
and is not regenerated; its outcome is not an interim strength claim.

## Resources and expected time

The best-PIMC comparison uses four clean spawned worker processes, avoiding a fork
of previously loaded episode records. The BEN worker waits for at least 5 GiB of
available memory and an exclusive shared BEN resource lock before launching one
server. It never stops or reconfigures another campaign's server. Other training,
BEN calibration and bidding-improvement workers are left running.

Initial estimates are 20–40 minutes of play for 500 best-PIMC pairs and 6–10 hours
for 500 BEN pairs, plus resource waiting. The BEN estimate uses 32 previously
completed baseline pairs averaging 42.64 seconds per pair (5.92 hours for 500 at
that rate); this is an extrapolation, not a completed measurement of the new bot.
Actual throughput and all failures will be reported with the results.

## Provenance and resumption

- Frozen runtime modules: `f26f975a5c197def5e203dd2da87d84dd54aadb9`.
- Existing coupled-sampler evaluator: `a01e3c2ea995bd678a9c3580a00b375d7eaa98e8`.
- Neural-only auction collector: `scripts/loop_collect_auctions.py` from the
  self-improvement checkout, SHA256 `91b8aeb3a019cfc58089a3c28e754683c074876fd26d668336e8562da7ee157c`.
- Belief weights: `c070981c21cc79eed2205b5dbe6693e5804641a05d7ce32948df10bf15a1e96a`.
- Policy weights: `02b6885e8f07da473970052d7f9ea9dc2a10fa34505ad60186e4a14d02218c60`.
- Native DDS: `7c76508d7082e5665872d89bcc580915ff90f8cd434a39d3704d762e72dc9870`.
- Full-search BEN portable config: `960d3b316967f22ed5c251a94b8e6714a249cc1851a02f193cc1f15e8f1dbfab`.

```sh
OPENBLAS_NUM_THREADS=1 python3 scripts/evaluate_frozen_comparisons.py --run <run> --mode play --opponent strict --workers 4
OPENBLAS_NUM_THREADS=1 python3 scripts/evaluate_frozen_comparisons.py --run <run> --mode play --opponent ben --workers 1
OPENBLAS_NUM_THREADS=1 python3 scripts/evaluate_frozen_comparisons.py --run <run> --mode audit --opponent strict --count 200
OPENBLAS_NUM_THREADS=1 python3 scripts/evaluate_frozen_comparisons.py --run <run> --mode audit --opponent ben --count 500
```

Each comparison owns its own nonblocking `worker.lock`. Never start a duplicate
writer, change the frozen models, regenerate completed pairs, or count the initial
checkpoint as a finished evaluation. Source and reports are Git-backed; raw data,
logs, native binaries and weights remain outside Git.
