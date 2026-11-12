# Arena simulator: promotion rules and schedules (E9-5, 12 November 2026)

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

## Rules compared

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

## Results

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

## What it means for the arena (proposals to g9 for G9-A4)

1. The hand rule should not decide promotions in a standing arena: it promotes an equal bot about
   one time in nine.
2. The mixture rule with running variance holds its level under the real tails and costs about
   1.7 times the boards of a single fixed test. It is the better default; the empirical-Bernstein
   rule is safe but a third slower again.
3. Its false promotion rate was 0.7% to 1.8% against a nominal two-sided 0.05: a one-sided mixture at
   0.025 would be cheaper at the same guarantee. Not simulated here.
4. Schedule boards by variance reduction, with a floor per pair in the first epoch.

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
    python -m unittest tests.test_arena_sim

Compute: 262, 17 and 186 CPU-seconds on a two-core sandbox (cap 2 CPU-hours). Seed 9 throughout.
