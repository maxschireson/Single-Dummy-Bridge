# Opening-lead attribution under equal later-play gains

This is an assumption-based decomposition of existing matched 192-versus-32 results. No new games or lead counterfactuals were run.

Sources:
- Original Gen5: commits 231647b297ba7b05ee28e720d7f395bacbcff818 and 759365035cddadd6b5586bd8f10995aff40d9be3, 972 distinct deal families.
- Gen5R: commit 8f386190b57714f94c904c922cbcdf36ab7791a2, 147 distinct deal families.
- Verified the two model-family cohorts have no overlapping deal families. Combined 1,119 deals. One passed out in each cohort.
- Positive IMPs favor 192 samples. All figures use common-auction root duplicate games. 5RZ is not included because no direct RZ192/RZ32 result is published in the checked feeds.

## Observed group outcomes

Shares below exclude passed-out boards, so there are 971, 146, and 1,117 played boards. Rate errors are one standard error of the deal mean, in IMP per board within that group.

| Comparison | Same lead count/share | Same-lead IMP/board | Different lead count/share | Different-lead IMP/board |
|---|---:|---:|---:|---:|
| Gen5 | 687 / 70.7518% | 0.085881 ± 0.108928 | 284 / 29.2482% | 0.517606 ± 0.284228 |
| Gen5R | 88 / 60.2740% | 0.022727 ± 0.334758 | 58 / 39.7260% | 0.327586 ± 0.479708 |
| Pooled | 775 / 69.3823% | 0.078710 ± 0.103697 | 342 / 30.6177% | 0.485380 ± 0.249426 |

## Attribution assumption and estimator

Assume expected IMP gains from subsequent play on different-lead boards equal those on same-lead boards, within each model variant. Let s and d be the mean IMP gains in same- and different-lead groups, pD the different-lead fraction of ALL deals, and pPlay the played fraction.

Opening-lead contribution per original deal = pD * (d - s).
Later-play contribution per original deal = pPlay * s.
These sum to the observed total mean; passed-out boards contribute zero.

| Comparison | Opening lead IMP/deal | Later play IMP/deal | Total IMP/deal |
|---|---:|---:|---:|
| Gen5 | 0.126142 ± 0.089060 | 0.085792 ± 0.108793 | 0.211934 ± 0.113331 |
| Gen5R | 0.120284 ± 0.230141 | 0.022573 ± 0.331717 | 0.142857 ± 0.274910 |
| Combined, stratified | 0.125372 ± 0.083058 | 0.077487 ± 0.104064 | 0.202860 ± 0.104859 |

Combined attribution averages the two within-variant estimates with fixed weights 972/1119 and 147/1119. This avoids requiring the same later-play gain across original Gen5 and Gen5R. A naive pooled estimate is nearly identical: opening lead 0.124291 ± 0.082674, later play 0.078569 ± 0.103491.

Point estimates attribute 59.52% of original Gen5 gain, 84.20% of Gen5R gain, and 61.80% of the stratified combined gain to opening lead. These fractions are unstable because the total advantage is noisy and near zero. A normal approximate 95% interval on the combined absolute lead contribution is [-0.0374, 0.2882] IMP/deal. Do not treat 61.8% as a precisely established fraction.

The lead/later errors are correlated because the same estimated same-lead baseline enters both components. Do not add their standard errors in quadrature without their covariance.

## Timing

Time is charged to each bot across both duplicate tables: one opening lead and 51 subsequent decisions per played deal. Shares are ratios of summed times, not averages of per-board percentages. Errors below are one standard error in percentage points.

| Comparison | Fraction of 192 bot time on lead | Fraction of extra 192-versus-32 time on lead |
|---|---:|---:|
| Gen5 | 35.8202% ± 0.6233 pp | 37.2582% ± 0.6822 pp |
| Gen5R | 52.4192% ± 1.4959 pp | 60.5486% ± 1.7124 pp |
| Combined observed workload | 37.6138% ± 0.6103 pp | 39.4685% ± 0.6817 pp |

The incremental-time column is the appropriate comparison for the benefit of increasing the sample budget. Combined timing aggregates actual recorded wall time across both cohorts; different deals and source-time conditions prevent interpreting cross-cohort timing as a controlled sampler experiment.

## Uncertainty method

Each deal family is one sampling unit; neither tables nor individual moves are treated as independent observations. Mean SEs use sample variance. For lead attribution A, the influence value for each deal is:
I_D*(Y-s) - (pD/pS)*I_S*(Y-s) - A.
The SE is the sample standard deviation of those influence values divided by sqrt(N), accounting for uncertainty in the group fractions and same-lead baseline.

For a time ratio r=mean(X)/mean(Z), SE = sample_sd(X-r*Z) / (sqrt(N)*mean(Z)). The incremental ratio retains the pairing of 192 and 32 timings within each deal.

20,000 whole-deal bootstrap resamples corroborated the attribution SEs: original Gen5 0.08986, Gen5R 0.22769, naive pooled 0.08275. The assumption of equal later-play gains cannot be verified from these subgroup results; different-lead boards may differ in difficulty or opportunities for later gains.
