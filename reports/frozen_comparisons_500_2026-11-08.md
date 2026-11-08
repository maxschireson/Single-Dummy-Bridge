# Frozen policy+belief versus best PIMC and BEN — 8 November 2026

Two fixed 500-deal paired evaluations are authorized and prepared. Card play is
running for the best-PIMC comparison. The full-search BEN comparison has a live
worker waiting for memory; it must not be described as playing until records exist.
Results will be reported after the fixed first 200 deals and after all 500 in each
comparison. Play continues while the interim audit runs in a separate process.

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
