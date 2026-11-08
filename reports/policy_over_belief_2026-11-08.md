# Does the frozen policy net add to the frozen belief net? — 8 November 2026

A fixed 1,000-deal experiment compares belief-informed PIMC plus the frozen
policy selector against the same belief-informed PIMC with uniform near-tie
selection. **Collection is in progress.** The first 200 paired deals favor the
combined bot; this is a preliminary checkpoint, not the final result.

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

## Preliminary results

| Fixed cohort prefix | Complete games | Tricks / paired deal (95% CI) | IMPs / paired deal (95% CI) | IMP wins / ties / losses |
|---|---:|---:|---:|---:|
| First 200 deals | 400 | +0.165 [+0.030, +0.295] | +0.615 [+0.130, +1.110] | 61 / 102 / 37 |

These 400 games passed legal replay and the 32-world/batch/near-tie checks.
They contain 16,429 non-forced decisions. Zero failed attempts were observed
at this checkpoint. Full final auditing will also recompute selector predictions
from each pre-action observation, verify identical worlds/estimates on shared
histories, and independently recompute all paired scores and confidence intervals.

The result estimates the policy net's increment **with the belief net already
present on both sides**. It cannot be added to a previous effect estimate on
different deals to claim a measured total gain over the original bot. The policy
net was trained with bidding-blind PIMC estimates and synthetic auctions; this
frozen-transfer test does not establish that this is the best possible combined
model. The policy's own inputs remain public play and visible cards, with
belief-informed PIMC estimates; it has no newly trained auction encoder.

## Verification and provenance

Twelve focused unit tests pass, including nonuniform belief sampling with equal
worlds/estimates for both players, correct partnership returns, seat/suit
invariance, rejection of privileged encoder fields, and weighted-sampler
constraints/distribution checks. Existing runtime source files match research
commit `f26f975a5c197def5e203dd2da87d84dd54aadb9` exactly. The new evaluator changes
only which already-frozen components are combined and how their results are logged.

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
python3 scripts/evaluate_policy_over_belief.py --run <run> --mode play --workers 6
python3 scripts/summarize_policy_over_belief_checkpoint.py --run <run> --count 200
python3 scripts/summarize_policy_over_belief_checkpoint.py --run <run> --count 400
python3 scripts/evaluate_policy_over_belief.py --run <run> --mode audit
```

For a fresh reproduction, collect exactly 1,024 auctions using the existing
`collect_ben_auctions.py`, seed 20261501 and the archived exclusions/config, then
use `--mode prepare` before play. Do not include these evaluation deals in training.
