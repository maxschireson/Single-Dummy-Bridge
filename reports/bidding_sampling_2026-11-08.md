# Bidding-informed 32-world PIMC and dummy-reveal beliefs — 8 November 2026

This experiment evaluates the frozen 46,582-parameter auction belief model,
trained on 39,951 independent BEN neural-only auction deals. No retraining,
model selection or weight-temperature tuning was performed on these results.
The separate full-search BEN calibration remains unchanged.

## Baseline and candidate

The prior sampler was bidding-blind, but already uniform over deals consistent
with visible cards, remaining hand sizes and voids exposed by public play.
The candidate uses the same information boundary and adds frozen auction-model
ownership logits. Its distribution is proportional to the product of per-card
neural ownership weights, restricted to legal assignments. Weight strength is
1.0, fixed before evaluation. Dynamic programming samples that distribution
exactly with two or three unknown hands; it does not run rejection sampling,
MCMC, or extra double-dummy evaluations.

This is an approximation to the true joint belief distribution: neural marginal
scores are not a learned joint posterior. The network takes only the observer's
original hand and public auction/context. Dummy's cards, public plays, capacities
and voids enter as hard conditioning constraints; the network has not yet been
retrained to interpret dummy's complete hand or infer from discretionary plays.

## Frozen evaluation protocol

- The original 50,000-auction split has 5,026 test deals, of which 12 are passed
  out. All 5,014 playable deals are used for the dummy-reveal measurement.
- Before inspecting outcomes, 200 playable test deals were selected by sorting
  original-deal hashes and shuffling with seed 20261112. Each is played twice,
  swapping bidding-informed and uniform PIMC partnerships on identical deal,
  contract, vulnerability and auction. Each side chooses its own opening lead.
- Both use batch DDS, exactly 32 worlds for every non-forced move, expected-tricks
  objective and uniform selection among moves within 0.125 estimated tricks.
- Comparison is at equal sampled-world count, not imposed equal wall time.
  Both policies have the same exploration rule. Confidence intervals resample
  original deals, never individual cards, views or duplicate tables.
- These test data have now been inspected for this frozen model; they must not
  later be described as an untouched test set after tuning against these results.

## Dummy-only revelation

This diagnostic reveals the original own hand and original dummy hand, plus the
completed auction. It deliberately omits the opening lead and all later play
information, isolating the impact of dummy revelation. It does not give dummy
to a player before the opening lead in any played game. Each deal supplies one
declarer view and two defender views, excluding dummy as a decision-maker.

Known cards are excluded. The remaining 26 cards belong to two 13-card hands.
The exact uniform prior is 50% ownership accuracy, NLL log(2), Brier 0.5.
Accuracy gives equal credit for tied top probabilities to avoid floating-point
tie-breaking artifacts. Probabilities enforce both remaining hand sizes.

## Primary paired-play result

The informed partnership competes against the uniform partnership in each
table; they swap NS/EW between tables. The trick result is a swing over those
two tables: informed declarer tricks minus baseline declarer tricks against
informed defenders. Neither table has both partnerships upgraded. It is not
a claim of 0.18 extra declarer tricks when everyone uses the new sampler.

| Measure | Bidding-informed minus uniform |
|---|---:|
| Tricks / paired deal | +0.180 (95% CI [0.05, 0.32]) |
| IMPs / paired deal | +0.535 (95% CI [-0.045, 1.095]) |
| IMP wins / ties / losses | 62 / 95 / 43 |

All 200 pairs completed: 400 full games, zero failures, 20,800 legal plies,
16,399 non-forced decisions and 524,768 DDS world solves. Every non-forced
decision used exactly 32 worlds. Full replay, original-deal identity and test
split membership passed the independent audit.

The trick interval is positive in this initial test. The IMP interval includes
zero. This is evidence against the bidding-blind PIMC baseline on this
BEN-neural-auction population; it is not a comparison against full BEN or a
general strength claim across bidding systems. A larger fresh replication is
needed before treating the effect size as stable.

Total move time was 912.60 seconds informed versus 1060.59 uniform (0.860x).
Timings are descriptive: the jobs ran concurrently, and the different sampled
worlds also change DDS search difficulty. This is not a controlled solver-speed
benchmark. The comparison keeps sample count fixed, not wall time.

## Dummy-reveal ownership results

| Viewpoint | Uniform accuracy | Informed accuracy | Gain, percentage points (95% CI) | NLL: uniform → informed |
|---|---:|---:|---:|---:|
| declarer | 50.00% | 56.28% | +6.28 [6.00, 6.57] | 0.693147 → 0.672821 |
| defender | 50.00% | 62.32% | +12.32 [12.16, 12.48] | 0.693147 → 0.646465 |
| all | 50.00% | 60.31% | +10.31 [10.16, 10.45] | 0.693147 → 0.655250 |

These results use 5,014 independent deals, 15,042 observer views and 391,092
hidden-card targets. The confidence intervals cluster by original deal.
Defenders place cards between partner and declarer; declarer places them
between the two defenders. The combined row weights the two defender views
and one declarer view equally per deal.

## Actual played positions

Both beliefs were evaluated on the identical legal information in the recorded
games, at 1/12/24/36/44 cards played. True remaining hands were targets only.
Cards already determined by hard constraints are excluded. Metrics average
eligible views within each original deal, then average deals.

| Cards played | Viewpoint | Uniform accuracy | Informed accuracy |
|---|---|---:|---:|
| 1 | declarer | 52.00% | 57.13% |
| 1 | defender | 51.00% | 62.38% |
| 12 | declarer | 51.17% | 58.11% |
| 12 | defender | 51.68% | 63.67% |
| 24 | declarer | 52.96% | 59.47% |
| 24 | defender | 54.54% | 64.34% |
| 36 | declarer | 56.53% | 62.19% |
| 36 | defender | 57.59% | 63.95% |
| 44 | declarer | 55.48% | 60.07% |
| 44 | defender | 56.04% | 62.27% |

At one card played, dummy is genuinely exposed and the actual opening lead
is public. Uniform prediction can exceed 50% because the unseen hands can
have different remaining card counts. Later positions also incorporate public
voids and hand-capacity deductions. These measurements share the 200 paired
play deals; they are not additional independent games.

## Declarer and defensive effects

After seeing the primary result, we added an all-uniform table for every one
of the same 200 deals. This is an exploratory decomposition, not a new set of
independent deals. The model, sampling weight and PIMC settings remain fixed.

| Upgrade relative to all-uniform | Beneficiary | Extra tricks / deal | 95% deal-bootstrap interval | IMPs / deal (95% interval) |
|---|---|---:|---:|---:|
| Declarer only | Declarer | +0.110 | [-0.015, +0.235] | +0.520 [-0.020, +1.065] |
| Defenders only | Defenders | +0.070 | [-0.065, +0.210] | -0.015 [-0.620, +0.610] |

The two trick effects sum to the primary 0.180-trick swing. Their individual
intervals include zero, so this sample does not yet establish a separate
playing-strength gain for either role. The defensive IMP point estimate is
approximately zero despite the positive trick point estimate. IMP conversion
is nonlinear, so separately converted IMP effects need not sum to the primary
paired IMP result.

The defensive comparison includes opening leads: 172 of 200 changed. The
upgrade-to-declarer comparison has the identical blind opening lead on every
deal. We have not isolated defensive decisions after a shared opening lead,
and have not measured the both-partnerships-upgraded configuration. All four
players getting better cannot create more than 13 tricks: who benefits would
require that additional comparison, including interactions between policies.

All 600 games over the 200 original deals completed without failures and passed
legal replay and fixed-32-world checks. The extra 200 all-uniform games took
267.51 seconds with four concurrent workers.


## Verification and provenance

- Dynamic-program marginals match exhaustive weighted allocation enumeration
  for small positions with two and three unknown hands.
- Zero neural weights reproduce uniform feasible allocations.
- A 6,000-draw check verifies sampling frequencies, no duplicated/missing cards,
  all visible hands, remaining hand counts and observed voids. Nonfinite scores
  are rejected. Equal-probability accuracy ties are tested.
- NumPy deployment inference matches Keras on 2,048 validation rows, maximum
  absolute logit error 1.55e-6. No test labels were used for that conversion.
- The model checkpoint SHA256 is
  `9818128bef759d51dffc097d73f09f59ce0c688dd29cb8ea44a4acdd0418c45f`;
  exported NumPy weights SHA256 is
  `c070981c21cc79eed2205b5dbe6693e5804641a05d7ce32948df10bf15a1e96a`.
- Parent research source: `a185c204b0b9882c673b90f523ed3fcdc9e3e4fb`.
  All raw paired games, test protocol, per-deal diagnostic measurements, audits,
  exact code/weights and native binary provenance are archived outside Git.

Run `scripts/evaluate_bidding_sampling.py --mode prepare`, then `--mode play`
and `--mode dummy`, with the same `--corpus`, `--weights` and `--out` paths.
The protocol freezes the selected deals and weight hash before play. The play
mode can resume completed pairs. Then run
`scripts/audit_bidding_sampling_play.py --run <output-directory>`.
The latter replays both tables and measures beliefs on actual public histories.

For the exploratory role decomposition run
`scripts/evaluate_bidding_roles.py --run <output-directory> --workers 4`.
It reuses the two completed tables and adds only the all-uniform table.

[Complete evaluation archive](https://chatgpt.com/library?file_id=libfile_fde3_f-0d56a65a5f9481919ee20b533f271f62_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).
