# Does the frozen policy net add to the frozen belief net? — 8 November 2026

**Final: 1,000 independent paired deals / 2,000 complete games, fully audited.**
Adding the frozen policy selector to the frozen bidding belief sampler improves
paired results by **+0.221 tricks per deal** (95% original-deal bootstrap
interval [+0.163, +0.277]) and **+0.669 IMPs per deal**
([+0.436, +0.894]). There are zero per-pair failure records; three process
interruptions were recovered by resuming only missing pairs.
Both intervals exclude zero. This is evidence of incremental value over belief-only
PIMC in this fixed experiment, with both models frozen throughout.

## Frozen comparison

Both sides use the existing 46,582-parameter auction belief model, exact
weighted legal-deal sampling, 32 worlds per non-forced decision, native batch
DDS, expected-tricks objective and a 0.125-trick eligibility window. Only the
candidate adds the existing 25,170-parameter policy scorer. Both models are
frozen; no retraining, weight tuning or model selection occurs in this test.
The default bot is unchanged by this evaluation.

Each independent deal is played at two tables with candidate/control
partnerships swapped. The deal, contract, vulnerability and frozen auction are
identical; each side selects its own opening lead. Identical public positions
receive identical sampled worlds and PIMC estimates under a common random
stream. Hashes of the actual sampled layouts are recorded to audit this.
Scores and trick swings are oriented toward the combined bot.

The primary outcome is paired tricks per original deal; IMPs per original deal
are secondary. Confidence intervals bootstrap original deals. The horizon is
fixed at 1,000 deals. At Max's request, preliminary checkpoints are reported at
200 and 400 deals, using fixed generation-order prefixes rather than completion
order. Their nominal 95% intervals are not adjusted for interim looks. Neither
checkpoint changes the stopping rule or either frozen model.

## Fresh evaluation corpus

BEN's pinned neural-only bidder generated 1,024 new independent auctions with
seed 20261501: 1,022 playable and two passed out, zero auction failures. Generation
took 4.17 seconds excluding model startup. The first 1,000 playable deals in
generation order were selected before card play; decision seed is 20261502.
The remaining 22 playable deals are unused, and passed-out deals are reported
separately. This is BEN neural-only bidding, not a BEN card-play opponent.

All 1,024 source deals are evaluation-only. Their generic collector hash-split
labels do not grant permission to train on them; `RESERVED_EVALUATION.json`
explicitly overrides those labels. Exclusion checks confirm no overlap with
the original 10,000-play corpus, the entire 50,000-auction corpus, the 1,000
auction-development deals or the 200 reserved full-search BEN calibration
deals (61,200 excluded original deals in total). Original-card hashes are unique.

## Final results and interim history

| Cohort | Complete games | Tricks / paired deal (95% CI) | IMPs / paired deal (95% CI) | IMP wins / ties / losses |
|---|---:|---:|---:|---:|
| First 200, preliminary | 400 | +0.165 [+0.030, +0.295] | +0.615 [+0.130, +1.110] | 61 / 102 / 37 |
| First 400, preliminary | 800 | +0.1675 [+0.0825, +0.2550] | +0.5925 [+0.2625, +0.9525] | 113 / 220 / 67 |
| **All 1,000, final** | **2,000** | **+0.221 [+0.163, +0.277]** | **+0.669 [+0.436, +0.894]** | **319 / 516 / 165** |

The final intervals use 2,000 bootstrap resamples of the 1,000 independent original
deals (seed 194). Each resample keeps both tables together. Each deal contributes
one candidate-oriented paired trick swing and one IMP swing; table games are not
treated as independent observations. Interim intervals were nominal and were not
adjusted for repeated looks; the predeclared final horizon and settings never changed.

## Final audit and selector diagnostics

All 2,000 games passed complete legal replay: **104,000 card plays**,
**82,255 non-forced decisions**, and **2,632,160 sampled-world
DDS solves**. Every non-forced decision used exactly 32 worlds through native batch
DDS; the solve count counts worlds, not separate Python/native calls.

- 33,506 candidate decisions used the policy to select among multiple eligible moves,
  out of 41,237 candidate non-forced decisions.
- 842 policy selections chose a move below the highest sampled PIMC estimate,
  always within the predeclared 0.125-trick window. Exact PIMC ties can also be resolved by the policy.
- 1,501 non-forced positions shared by the two tables had identical recorded
  sampled-world hashes and estimates.
- 1,000 paired deals had a first play divergence; each was traced
  to policy selection with identical sampled worlds at that position.

The audit recomputed every logged selector prediction from its true pre-action
observation, checked legal support and behavior probabilities, validated both belief
tags, partnership assignments, contract scores and IMP orientation, and independently
recomputed the final effects and confidence intervals to match `play-summary.json`.
The supplemental verification rechecked the exact 1,000-deal cohort, uniqueness,
all 1,024 auction identities/contracts and their zero overlap with the 61,200 exclusions.
The archived first 576 pairs are byte-for-byte unchanged in the final dataset.

There are zero per-pair failure records and no partial records in the delivered
dataset. Three process interruptions required resumption, at 576, 913 and 969 complete
pairs. The third logged `BrokenProcessPool` after a worker exited abruptly; the underlying
causes were not established. These operational interruptions are distinct from completed
match results, and all available logs are preserved. Only missing pairs resumed. Work on an
unfinished pair may have been lost, and is not counted as a completed game or deal.
The two passed-out source auctions are separate from the 1,000 playable paired deals.

## Collection throughput

Six workers with `OPENBLAS_NUM_THREADS=1` completed the four execution segments
as follows. Times run from invocation start to the last saved pair in that segment,
excluding gaps between invocations and the final summary/audit.

| Segment | Previously complete | Newly completed pairs | Seconds to last saved pair |
|---|---:|---:|---:|
| 1 | 0 | 576 | 1020.1 |
| 2 | 576 | 337 | 569.9 |
| 3 | 913 | 56 | 135.0 |
| 4 | 969 | 31 | 54.2 |

These measured segments total 29.7 minutes,
approximately 2023 paired
deals/hour (4047 table games/hour).
The first launch to the last saved pair took 42.8
minutes including intervening gaps. The sum of recorded table durations is
2.92 hours across workers. These are descriptive shared-worker
measurements; they exclude final auditing and may omit work lost after the last saved
pair of an interrupted segment. They are not controlled hardware benchmarks or
Mac Studio forecasts.

## Interpretation and limitations

The result estimates the policy net's increment **with the belief net already
present on both sides**. It cannot be added to a previous effect estimate on
different deals to claim a measured total gain over the original bot. The policy
net was trained with bidding-blind PIMC estimates and synthetic auctions; this
frozen-transfer test does not establish that this is the best possible combined
model. The policy's own inputs remain public play and visible cards, with
belief-informed PIMC estimates; it has no newly trained auction encoder.
No combined retraining was done. This is not a full-search BEN card-play comparison,
and it does not show that a standalone policy can replace PIMC. The intervals describe
deal sampling uncertainty for this particular bidder, frozen models and decision seed;
they do not measure robustness to other bidding systems, opponents or repeated seeds.

## Verification and provenance

Twelve focused unit tests pass, including nonuniform belief sampling with equal
worlds/estimates for both players, correct partnership returns, seat/suit
invariance, rejection of privileged encoder fields, and weighted-sampler
constraints/distribution checks. Existing runtime source files match research
commit `f26f975a5c197def5e203dd2da87d84dd54aadb9` exactly. The new evaluator changes
only which already-frozen components are combined and how their results are logged.
Evaluator/reporting tooling is published at `a01e3c2ea995bd678a9c3580a00b375d7eaa98e8`.
The initial launch preceded a prepare-only provenance fallback for source trees without
Git metadata; gameplay/audit semantics were unchanged. Exact invocation hashes and the
runtime file hashes are retained in the archive.

- Belief NumPy weights SHA256: `c070981c21cc79eed2205b5dbe6693e5804641a05d7ce32948df10bf15a1e96a`.
- Policy NumPy weights SHA256: `02b6885e8f07da473970052d7f9ea9dc2a10fa34505ad60186e4a14d02218c60`.
- Native DDS SHA256: `7c76508d7082e5665872d89bcc580915ff90f8cd434a39d3704d762e72dc9870`.
- BEN bidding revision: `9b5f43104aeac713a80b73513f2f2d6daf9f8769`; exact bidder/config hashes in the auction manifest.

Raw records, weights and binary artifacts stay outside Git. Scripts and this
report are published on the research branch. Execution uses six workers alongside
other work; elapsed time is not a controlled hardware or inference-speed comparison.

## Reproduce and resume

Restore the archived run directory, including both frozen NumPy weight files,
exclusions, frozen auctions, protocol and any completed paired episodes. The play
mode validates and resumes completed pairs instead of regenerating them.

```sh
OPENBLAS_NUM_THREADS=1 python3 scripts/evaluate_policy_over_belief.py --run <run> --mode play --workers 6
python3 scripts/summarize_policy_over_belief_checkpoint.py --run <run> --count 200
python3 scripts/summarize_policy_over_belief_checkpoint.py --run <run> --count 400
python3 scripts/evaluate_policy_over_belief.py --run <run> --mode audit
```

For a fresh reproduction, collect exactly 1,024 auctions using the existing
`collect_ben_auctions.py`, seed 20261501 and the archived exclusions/config, then
use `--mode prepare` before play. Do not include these evaluation deals in training.


## Complete artifact

`Bridge_Policy_Over_Belief_1000_2026-11-08.zip` contains the complete raw paired episodes,
all source auctions, both frozen weights, protocol, evaluation-only reservation,
exclusion registry, audits, invocation/provenance records and this final report.
Source remains Git-backed; records, logs, binaries and weights are not committed.
All 1,024 evaluation deals remain excluded from future training.
