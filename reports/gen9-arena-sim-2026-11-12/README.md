# Arena simulator: promotion rules, rating coverage and schedules (E9-5, 12 November 2026)

Gen 9 work in progress (dave, task G9-D2). **Evidence kind: simulation.** No board was played.
Per-board results are drawn from noise models fitted to the published feeds; the questions are
how often a stopping rule promotes a candidate that is not better, how many boards it needs when
the candidate is better, and which schedule gives a precise rating table soonest.

## Data and noise

- Every record of the 62 sources in `gh-pages:arena/gen6-sources.json` (43,239 rows), read by
  `scripts/arena_feed_rows.py`, with the dashboard's counting rules applied
  (`arena_sim.counted_rows`: snapshot cut-off, `ben32` and the accidental cohorts out, allowed
  pairs, a deal family once per pair, earliest wins): 43,031 boards. Common auction.
- Plus g8's fork-free `7s-32` (policy v4.1) against `7s-32` (v4) match, 3,200 boards on fresh
  random deals (`c2-7s-v41-v-v4*/results.jsonl` on `transfer/gen8-proto-azure4-20261112` and
  `transfer/gen8-proto-azure6-20261112`). Per-board results, not arena records.
- Three pools of per-board values, each pair centred on its own mean (`noise_pools.json.gz`):

  | Pool | Pairs | Boards | SD | Kurtosis | Flat boards |
  | --- | --- | ---: | ---: | ---: | ---: |
  | twin | `71s-32~7s-32` and g8's v4.1-against-v4 match | 3,439 | 2.64 | 18.9 | 80% |
  | sibling | `7s-32~6-32`, `6-32~6-256` | 4,216 | 3.30 | 13.1 | 72% |
  | unrelated | Gen 6 and 7 against BEN, Gen 5, 3, 2 and 1 | 12,297 | 4.25 | 7.4 | 52% |

- Every setting is run with a bootstrap of a pool (the true gap added to the centred values) and
  with Gaussian noise at SD 2.6, 3.2 and 4.2. `boot-unrelated-x2` is the unrelated pool doubled.

## G9-A4's rules (docs/gen9/arena-statistics.md), answering its section 5

The betting test is implemented as specified (`bridge_harness/arena_ratings.py`, `BettingTest`;
vectorised as `arena_sim.betting_first_crossings`, checked equal board by board in the tests):
`z = x / 24`, bets `clip(m / (v + m^2), 0, 0.5)` from earlier boards with one prior board at 0 and
second moment `(3/24)^2`, promote at `K >= 20`, futility by the mirror test of "leads by at least
d" at `L >= 10`, first bound crossed wins. 2,000 runs a setting, run once to 20,000 boards and read
at caps of 3,000, 6,000, 10,000 and 20,000, futility margins d of 0.05 and 0.1.

**1. An equal candidate is promoted in at most 5% of runs at any horizon: yes.** 1.5% to 3.5%
under the real per-board values (1.6% to 3.6% with Gaussian noise), rising slowly with the cap:

| Noise | Cap 3,000 | 6,000 | 10,000 | 20,000 |
| --- | ---: | ---: | ---: | ---: |
| boot-twin | 0.015 | 0.022 | 0.025 | 0.028 |
| boot-sibling | 0.017 | 0.020 | 0.022 | 0.025 |
| boot-unrelated | 0.026 | 0.029 | 0.032 | 0.035 |
| boot-unrelated-x2 | 0.029 | 0.033 | 0.034 | 0.035 |

The hand rule's rate on the same pools is 9.5% to 11.8% (section "Comparison" below).

**2. Boards to a decision and power** (d = 0.05; the last column runs to 20,000 boards and gives
the boards by which 80% of runs had promoted, against one fixed-sample test of 80% power):

| Noise | True lead | Promoted by 6,000 | Futility | Undecided | Mean boards | Boards to 80% promoted, cap 20,000 (ratio to fixed) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| boot-twin | -0.10 | 0.000 | 0.969 | 0.031 | 1,953 | — |
| boot-twin | +0.00 | 0.022 | 0.263 | 0.715 | 4,997 | — |
| boot-twin | +0.05 | 0.164 | 0.048 | 0.789 | 5,260 | — |
| boot-twin | +0.10 | 0.632 | 0.006 | 0.361 | 3,965 | 8,539 (1.57) |
| boot-twin | +0.20 | 0.999 | 0.001 | 0.001 | 1,369 | 1,981 (1.46) |
| boot-twin | +0.40 | 1.000 | 0.000 | 0.000 | 487 | 623 (1.83) |
| boot-sibling | -0.10 | 0.002 | 0.864 | 0.134 | 2,674 | — |
| boot-sibling | +0.00 | 0.020 | 0.175 | 0.804 | 5,229 | — |
| boot-sibling | +0.05 | 0.127 | 0.047 | 0.826 | 5,353 | — |
| boot-sibling | +0.10 | 0.409 | 0.020 | 0.571 | 4,593 | 15,032 (1.76) |
| boot-sibling | +0.20 | 0.973 | 0.002 | 0.025 | 2,009 | 3,200 (1.50) |
| boot-sibling | +0.40 | 1.000 | 0.000 | 0.000 | 580 | 794 (1.49) |
| boot-unrelated | -0.10 | 0.004 | 0.630 | 0.365 | 3,727 | — |
| boot-unrelated | +0.00 | 0.029 | 0.134 | 0.837 | 5,291 | — |
| boot-unrelated | +0.05 | 0.088 | 0.052 | 0.860 | 5,397 | — |
| boot-unrelated | +0.10 | 0.231 | 0.029 | 0.741 | 5,083 | — |
| boot-unrelated | +0.20 | 0.808 | 0.008 | 0.183 | 3,145 | 5,896 (1.66) |
| boot-unrelated | +0.40 | 1.000 | 0.001 | 0.000 | 871 | 1,370 (1.54) |

The betting test needs 1.46 to 1.76 times the boards of a fixed-sample test at leads of 0.1 and
0.2 under the real values, a little less than the normal-mixture interval (1.62 to 1.91, below).
At the default cap of 6,000 it promotes a true lead of 0.1 in 63% (twin), 41% (sibling) and 23%
(unrelated) of runs, and a lead of 0.2 in 81% to 100%.

**3. A candidate that truly leads by d is stopped for futility in at most 10% of runs: yes.**
4.7% to 5.2% at d = 0.05 with the default cap; 5.1% to 7.2% at d = 0.1 with a cap of 20,000
(up to 7.7% with doubled noise).

**The cap and d.** At a true lead of 0 most tests with d = 0.05 run to the cap (71% to 84% at
6,000), so an equal candidate costs about 5,000 boards. With d = 0.1 the futility bound ends most
of them first, at the same power for leads of 0.1 and 0.2:

| Noise | Cap | d | Mean boards, equal candidate (undecided) | Promoted at a lead of 0.1 / 0.2 | Futility at a lead of d |
| --- | ---: | ---: | ---: | ---: | ---: |
| boot-twin | 6,000 | 0.05 | 4,997 (0.71) | 0.63 / 1.00 | 0.048 |
| boot-twin | 6,000 | 0.1 | 3,341 (0.25) | 0.63 / 1.00 | 0.044 |
| boot-twin | 10,000 | 0.05 | 7,609 (0.59) | 0.85 / 1.00 | 0.052 |
| boot-twin | 10,000 | 0.1 | 3,947 (0.08) | 0.83 / 1.00 | 0.047 |
| boot-twin | 20,000 | 0.05 | 12,376 (0.37) | 0.99 / 1.00 | 0.059 |
| boot-twin | 20,000 | 0.1 | 4,165 (0.00) | 0.94 / 1.00 | 0.051 |
| boot-sibling | 6,000 | 0.05 | 5,229 (0.80) | 0.41 / 0.97 | 0.047 |
| boot-sibling | 6,000 | 0.1 | 4,138 (0.47) | 0.40 / 0.97 | 0.056 |
| boot-sibling | 10,000 | 0.05 | 8,308 (0.73) | 0.61 / 1.00 | 0.051 |
| boot-sibling | 10,000 | 0.1 | 5,603 (0.28) | 0.60 / 0.99 | 0.060 |
| boot-sibling | 20,000 | 0.05 | 14,825 (0.58) | 0.90 / 1.00 | 0.054 |
| boot-sibling | 20,000 | 0.1 | 7,014 (0.05) | 0.87 / 0.99 | 0.062 |
| boot-unrelated | 6,000 | 0.05 | 5,291 (0.84) | 0.23 / 0.81 | 0.052 |
| boot-unrelated | 6,000 | 0.1 | 4,704 (0.66) | 0.23 / 0.81 | 0.065 |
| boot-unrelated | 10,000 | 0.05 | 8,567 (0.80) | 0.37 / 0.96 | 0.057 |
| boot-unrelated | 10,000 | 0.1 | 7,031 (0.50) | 0.36 / 0.96 | 0.068 |
| boot-unrelated | 20,000 | 0.05 | 16,195 (0.72) | 0.68 / 0.99 | 0.059 |
| boot-unrelated | 20,000 | 0.1 | 10,536 (0.22) | 0.66 / 0.99 | 0.072 |

So d = 0.1 is cheaper at no cost in power for leads the arena can resolve; its price is that a
real lead of 0.05 is usually stopped as not worth having. With d = 0.1 a longer cap buys power
cheaply: on twin noise a cap of 20,000 leaves no equal candidate undecided, costs 4,165 boards for
one on average, and promotes a lead of 0.1 in 94% of runs (63% at 6,000).

**Agreement of the displayed interval with the decisions.** The interval A4 shows beside a
running test (two-sided 95% asymptotic confidence sequence, tightest near 1,500 boards, shown from
board 300) is far wider than the betting test's own boundary. At the default cap and d:

| Noise | True lead | Promotions shown an interval | of which its lower end was at or below 0 | Futility stops shown | of which its upper end was at or above d |
| --- | ---: | ---: | ---: | ---: | ---: |
| boot-twin | -0.10 | 0 | — | 1,886 | 99% |
| boot-twin | +0.00 | 44 | 91% | 519 | 99% |
| boot-twin | +0.10 | 1,262 | 79% | 13 | 100% |
| boot-twin | +0.20 | 1,972 | 70% | 2 | 100% |
| boot-twin | +0.40 | 1,708 | 26% | 0 | — |
| boot-sibling | -0.10 | 4 | 100% | 1,624 | 98% |
| boot-sibling | +0.00 | 39 | 100% | 332 | 99% |
| boot-sibling | +0.10 | 808 | 77% | 31 | 100% |
| boot-sibling | +0.20 | 1,900 | 77% | 3 | 100% |
| boot-sibling | +0.40 | 1,669 | 78% | 0 | — |
| boot-unrelated | -0.10 | 7 | 100% | 1,114 | 96% |
| boot-unrelated | +0.00 | 47 | 98% | 221 | 97% |
| boot-unrelated | +0.10 | 435 | 70% | 28 | 96% |
| boot-unrelated | +0.20 | 1,551 | 64% | 2 | 100% |
| boot-unrelated | +0.40 | 1,704 | 83% | 0 | — |

At leads of 0.1 and 0.2, 64% to 79% of promotions happen while the shown interval still includes
zero, and nearly every futility stop happens while it still includes d. Someone reading the dashboard would see "not established" at the
moment the arena acts. Showing the betting test's own state instead (the capitals `K` toward 20 and
`L` toward 10, or the confidence sequence obtained by inverting the betting test over a grid of
means) would keep what is shown and what is decided the same.

**4. Coverage of the rating table's 95% intervals** (A4 section 1 as specified: shrunk per-pair
variance, a pair-effect variance by moments, a weak prior, cells as the precision-weighted mean of
the pair's own result and the leave-one-out prediction). 12 players, 150 boards a played pair,
1,000 runs a row; "sparse" plays the champion and two anchors against everyone plus a fifth of the
other pairs. The truth for a cell is the pair's true mean, pair effect included.

| Design | Slice | Strengths | Cells, played pairs | Cells, unplayed pairs | The affected pair's cell | Mean t2 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| equal | base | 0.956 | 0.965 | — | 0.969 | 0.0093 |
| equal | pair-effect-0.3 | 0.954 | 0.958 | — | 0.673 | 0.0101 |
| equal | pair-noise-x2 | 0.957 | 0.964 | — | 0.959 | 0.0094 |
| sparse | base | 0.958 | 0.958 | 0.966 | 0.953 | 0.0122 |
| sparse | pair-effect-0.3 | 0.957 | 0.956 | 0.963 | 0.848 | 0.0129 |
| sparse | pair-noise-x2 | 0.959 | 0.958 | 0.963 | 0.954 | 0.0130 |

Coverage is right for strengths and for cells, played or not, and with one pair's noise doubled.
**It fails for the pair that has a real pair effect: 67% (equal design) and 85% (sparse).** The
pair-effect variance is one number for all pairs, so a single effect of 0.3 among 66 pairs barely
moves it (0.0093 to 0.0101), the model's prediction from the other pairs is precise, and the cell
leans on it. A cell that is out of line needs its own test: compare the pair's direct result with
its leave-one-out prediction and, where they disagree beyond their joint interval, report the
direct result and flag the pair. G9-D3 does this on the published feeds.

**5. The gain rule for a field-score precision.** Champion's field score against five opponents
with equal shares; 12 players; 50 boards on each champion-field pair to start, then 100 boards at a
time; 300 runs.

| Schedule | Boards added | Reported SE of the field score | Its actual RMSE |
| --- | ---: | ---: | ---: |
| equal | 0 | 0.243 | 0.259 |
| equal | 1,000 | 0.178 | 0.203 |
| equal | 2,000 | 0.153 | 0.176 |
| equal | 4,000 | 0.124 | 0.132 |
| field | 0 | 0.243 | 0.265 |
| field | 1,000 | 0.113 | 0.114 |
| field | 2,000 | 0.084 | 0.090 |
| field | 4,000 | 0.061 | 0.066 |
| gain | 0 | 0.243 | 0.248 |
| gain | 1,000 | 0.116 | 0.115 |
| gain | 2,000 | 0.088 | 0.088 |
| gain | 4,000 | 0.066 | 0.065 |

The gain rule and a plain rotation of the champion over the field reach the same precision (both
about half the SE of equal shares over all pairs after 4,000 boards), and the reported SE matches
the actual error (0.066 reported, 0.065 actual). For a field score the gain rule finds what the
obvious schedule already does; its use is where the obvious schedule is not known (admissions,
panels, sparse tables).

## Comparison with the hand rule and two other always-valid intervals

This was run before G9-A4 was written, with dave's placeholder forms.

### Rules compared

- **Hand rule** (today's): from 1,000 boards, every 100 to 5,000, promote when the lower end of a
  two-sided 95% t-interval is above zero; otherwise no decision at 5,000.
- **Mixture**: always-valid interval, two-sided level 0.05, normal-mixture boundary with the
  running sample variance plugged in (asymptotic), tuned for 2,000 boards at SD 3.5, first look
  at 200 boards, a look every 50.
- **Empirical Bernstein**: always-valid interval, two-sided level 0.05, predictable plug-in
  empirical-Bernstein confidence sequence for values bounded in [-24, 24] (exact for bounded
  data), a look every 50.
- Both always-valid rules promote when the lower end passes zero, stop for futility when the
  upper end falls below 0.05 IMPs, and stop at 40,000 boards. These are dave's forms, written
  before G9-A4; A4's replace them.

2,000 runs a setting. Standard error of a rate near 0.1 is about 0.007; near 0.02, about 0.003.

### Results

**(a) Promotion of a candidate exactly equal to the champion.** The hand rule promotes 9.5% to
12.4% of the time, about four to five times the 2.5% a single look at that interval would give.
Both always-valid rules stay under their level with the real tails, the twin pool's included:

| Noise | SD | Hand rule | Mixture | Empirical Bernstein |
| --- | ---: | ---: | ---: | ---: |
| gauss-2.6 | 2.60 | 0.124 | 0.016 | 0.001 |
| gauss-3.2 | 3.20 | 0.114 | 0.015 | 0.004 |
| gauss-4.2 | 4.20 | 0.117 | 0.017 | 0.004 |
| boot-twin | 2.63 | 0.115 | 0.017 | 0.003 |
| boot-sibling | 3.30 | 0.118 | 0.018 | 0.004 |
| boot-unrelated | 4.25 | 0.097 | 0.012 | 0.003 |
| boot-unrelated-x2 | 8.51 | 0.095 | 0.007 | 0.004 |

**(b) Boards to a decision when the candidate is better.** The fair comparison is the number of
boards by which 80% of runs have promoted against the size of one fixed-sample test with 80%
power at one-sided level 0.025, from the noise's SD (ratio in brackets). The hand rule's power is
capped by its 5,000-board horizon and its ratio is not comparable, since it is not holding its
level; its column is the share of runs it promotes by 5,000.

| Noise | Gap | Fixed test, boards for 80% power | Hand rule: promoted by 5,000 | Mixture: boards to 80% promoted (ratio) | Emp. Bernstein: boards to 80% (ratio) |
| --- | ---: | ---: | ---: | ---: | ---: |
| boot-twin | 0.1 | 5,446 | 0.88 | 9,050 (1.66) | 13,900 (2.55) |
| boot-twin | 0.2 | 1,362 | 1.00 | 2,360 (1.73) | 3,550 (2.61) |
| boot-twin | 0.4 | 340 | 1.00 | 750 (2.20) | 1,300 (3.82) |
| boot-sibling | 0.1 | 8,524 | 0.73 | 14,700 (1.72) | 23,700 (2.78) |
| boot-sibling | 0.2 | 2,131 | 1.00 | 3,450 (1.62) | 5,110 (2.40) |
| boot-sibling | 0.4 | 533 | 1.00 | 1,000 (1.88) | 1,500 (2.81) |
| boot-unrelated | 0.1 | 14,193 | 0.53 | 27,150 (1.91) | — |
| boot-unrelated | 0.2 | 3,548 | 0.95 | 6,100 (1.72) | 9,150 (2.58) |
| boot-unrelated | 0.4 | 887 | 1.00 | 1,500 (1.69) | 2,200 (2.48) |
| boot-unrelated-x2 | 0.1 | 56,772 | 0.26 | — | — |
| boot-unrelated-x2 | 0.2 | 14,193 | 0.55 | 30,550 (2.15) | — |
| boot-unrelated-x2 | 0.4 | 3,548 | 0.96 | 6,760 (1.91) | 11,360 (3.20) |

The mixture rule needs 1.6 to 1.9 times the boards of a fixed-sample test at gaps of 0.1 to 0.2
IMPs. The prediction was at most 1.7. At 80% power the bootstrap cells are 1.62 to 1.73, except
the unrelated pool at 0.1 (1.91); only two of the six are under 1.7. At 90% power they are 1.58
to 1.65, except that same cell (1.81). So about 1.7, not reliably under it. Retuning the mixture for 8,000 boards instead of 2,000 moves single cells (unrelated
at 0.1: 1.91 to 1.71; twin at 0.2: 1.73 to 2.13) without lowering the range
(`promotion_mix_plan8000.json`). The empirical-Bernstein rule needs 2.4 to 2.8 times.

For 7.1 against 7.0 (twin noise): a true lead of 0.1 IMPs takes about 9,000 boards to promote
four times in five under the mixture rule; the hand rule gets there by 4,000 but also promotes an
equal bot about one time in nine.

**(c) Schedules.** Arenas of 8, 12 and 20 players, strengths drawn from the published ones (Gen 1
to 7.1 and BEN, relative to Gen 6 fast) with a spread of 0.15, four lineages (a pair in one
lineage uses the sibling pool, otherwise the unrelated one), epochs of 2,000 boards, one arrival
and one departure every second epoch (anchors stay), ratings refitted after each epoch by
weighted least squares with per-pair variance shrunk toward 16. Root-mean-square error of active
players' fitted strengths against the truth, both centred; 200 runs a setting (standard error of
the mean RMSE about 0.002).

- `equal`: equal shares over all pairs of active players.
- `star`: equal shares over pairs with the champion or one of two anchors.
- `variance`: boards in chunks of 50 to the pair that most reduces the summed variance of the
  fitted ratings.

| Players | Slice | Schedule | RMSE after 2,000 | after 10,000 | after 30,000 | Boards to RMSE 0.10 | to 0.08 |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 8 | base | equal | 0.142 | 0.085 | 0.073 | 4,505 | 7,745 |
| 8 | base | star | 0.186 | 0.097 | 0.087 | 7,086 | 15,442 |
| 8 | base | variance | 0.151 | 0.071 | 0.051 | 4,630 | 7,391 |
| 12 | base | equal | 0.190 | 0.106 | 0.082 | 10,612 | 15,871 |
| 12 | base | star | 0.251 | 0.123 | 0.100 | 15,457 | — |
| 12 | base | variance | 0.199 | 0.088 | 0.059 | 7,490 | 12,500 |
| 20 | base | equal | 0.244 | 0.124 | 0.093 | 15,848 | — |
| 20 | base | star | 0.347 | 0.171 | 0.121 | — | — |
| 20 | base | variance | 0.281 | 0.120 | 0.074 | 14,571 | 23,842 |

The variance-directed schedule reaches an RMSE of 0.08 in fewer boards than equal shares once
the arena has 12 players or more (12,500 against 15,871 at 12; 23,842 against not within 30,000
at 20) and ends lower in every arena (0.051 to 0.074 against 0.073 to 0.093 after 30,000). It is
slightly worse after the first epoch, when it has no variances to go on, and no better at the
coarse target of 0.10 with 8 players. The champion-and-anchors schedule is worst throughout. The
slices (one pair 0.3 better than the model predicts; one player with twice the noise) change the
ordering nowhere; the pair effect barely moves the RMSE because it touches one pair of many.

## What it means for the arena (proposals to g9)

1. The hand rule should not decide promotions in a standing arena: it promotes an equal bot about
   one time in nine.
2. G9-A4's betting test stands: it holds its level and its futility guarantee under the real tails
   at every cap tried, and costs 1.5 to 1.8 times the boards of one fixed test.
3. Raise the futility margin d from 0.05 to 0.1, and the cap from 6,000 to 10,000 or more: equal
   candidates end sooner, real leads of 0.1 are promoted more often.
4. Show the betting test's own state beside a running test, not the asymptotic interval, which
   disagrees with most decisions.
5. Flag pairs whose direct result is out of line with the leave-one-out prediction; the shared
   pair-effect variance does not catch a single real pair effect.
6. Schedule boards by variance reduction, with a floor per pair in the first epoch; for a known
   contrast (a test, a field score) the direct schedule is as good.

## Limits

- Boards are independent draws from a pool's marginal distribution; no deal-to-deal correlation
  between pairs, no drift within a match.
- Noise classes in the schedule study are two (sibling, unrelated); real pairs differ more.
- The twin pool is mostly g8's fork-free match on fresh random deals, not arena records.
- The schedule study used 200 runs a setting, not the 2,000 the experiment file named: the
  standard error of the mean RMSE was already about 0.002. Logged in E9-5.
- The pair-effect slice tests the rating error only. Whether the rating table flags an
  out-of-order pair is G9-D3's question, on the real feeds.

## Reproduce

    python scripts/arena_feed_rows.py --out rows.jsonl.gz
    python scripts/arena_sim.py pools --rows rows.jsonl.gz --twin <g8 results.jsonl files> --out noise_pools.json.gz
    python scripts/arena_sim.py promotion --pools noise_pools.json.gz --runs 2000 --out promotion.json
    python scripts/arena_sim.py promotion --pools noise_pools.json.gz --runs 2000 --rules mix --plan-boards 8000 \
        --noise boot-twin boot-sibling boot-unrelated --gaps 0 0.1 0.2 --out promotion_mix_plan8000.json
    python scripts/arena_sim.py schedule --pools noise_pools.json.gz --runs 200 --out schedule.json
    python scripts/arena_sim.py bet --pools noise_pools.json.gz --runs 2000 --out bet.json
    python scripts/arena_sim.py coverage --pools noise_pools.json.gz --runs 1000 --out coverage.json
    python scripts/arena_sim.py gain --pools noise_pools.json.gz --runs 300 --out gain.json
    python -m unittest tests.test_arena_sim tests.test_arena_ratings

Compute: 262, 17, 186, 289, 34 and 20 CPU-seconds on a two-core sandbox (cap 2
CPU-hours). Seed 9 throughout.
