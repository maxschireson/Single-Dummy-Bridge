# ratings-v1 from every published paired result, Gen 5 to Gen 7.1 (G9-D3, 12 November 2026)

Gen 9 work in progress (dave). **Evidence kind: played boards** (published arena records), fitted
with g9's rating model (`docs/gen9/arena-statistics.md` section 1; `bridge_harness/arena_ratings.py`).
Read-only: nothing here changes a feed, the registry or the dashboard, and no number here decides
anything.

## Question

Does one strength per bot, fitted to every pair at once, reproduce each pair's own published
result? Where it does not, the pair is an out-of-order match-up (a style effect), and the rating
table needs a pair term.

## Data

- The 62 sources of `gh-pages:arena/gen6-sources.json` (Gen 6, 7 and 7.1) and the five Gen 5 feeds,
  which are not in that registry: `arena-gen5-codex-32-feed`, `arena-gen5-codex-feed`,
  `arena-gen5r-feed`, `arena-gen5rz-ben-feed`, `arena-gen5rz-feed`. 60,966 records, read by
  `scripts/arena_feed_rows.py` at each source's registered revision or branch head.
- The dashboard's counting rules within each table: records after the feed's snapshot ignored;
  `ben32` and the accidental fast-against-BEN cohorts out; allowed pairs respected; a deal family
  counted once per pair, earliest completion first. Self-play has no strength and is left out.
- **Three tables, because there are three conditions.** The common auction is bid by the cohort's
  common bidder, and that bidder changed: all Gen 5 feeds used the Gen 5 bidding network
  (`9ee52f3b...`, bots `5` and `5R32`), and Gen 6 to 7.1 used Gen 6's (`5b7ea255...`, `6-32`). The
  same two bots meet different contracts under the two, so common results are fitted per common
  bidder. The native auction (each side its own bidder) measures the whole bot and is one table
  across all feeds.
- Bots are pooled by id, as the dashboard does. Four ids carry two identities across feeds:
  `1` and `5RZ32` (the same artifacts under different folder paths: the identity hashes paths),
  `7s-32` (tree trust 0.25 in the pre-arena test, 0.3 since; Max asked for them not to be
  distinguished) and `ben64` (two different BEN configuration files). Only the last is a real
  difference, and it is not tested here.

## Method

Per pair: count, mean and variance of the per-board IMPs. Strengths by weighted least squares on
pair means with a shrunk per-pair variance, a pair-effect variance `t2` by moments and a weak
prior (A4 section 1), reference BEN (16). For each pair:

- **Reproduction:** is the fitted difference `s_i - s_j` inside the pair's own published 95%
  interval (the dashboard's: mean +- 1.96 sample SE)?
- **Out of line:** the pair's own mean against its leave-one-out prediction (the model fitted to
  every other pair, its pair-effect variance `t2` re-estimated without the pair under test),
  `z = (m - pred) / sqrt(e^2 + var(pred) + t2)`, Holm-adjusted over the testable pairs of the
  table. Re-estimating `t2` matters: a single large effect otherwise raises `t2`, widens its own
  prediction's interval and hides itself (a test with a planted effect of 1.0 IMP failed to flag
  it until this was changed). A pair that is a player's only link to the rest of the table has no
  independent prediction (the leave-one-out fit falls back on the prior) and is marked not
  testable.

## Results

**Every pair is reproduced.** In all three tables the fitted difference lies inside every pair's
own 95% interval (64 pairs).

**No pair is out of line.** Of 59 testable pairs none has a Holm-adjusted p below 0.05, and one has
a raw p below 0.05 (`7s-32~5RZ32` native: +1.41 own against +1.04 predicted, z = +2.31), where
chance alone would give about three. The moment estimate of the pair-effect variance is 0.010
(an SD of 0.10 IMPs) for common auctions under the Gen 6 bidder and 0 for the other two tables.

**What this can and cannot exclude.** A pair effect is detectable here at about three standard
errors of the residual: from 0.32 to 1.16 IMPs a board for pairs with at least 500 boards (median
0.51 native, 0.55 common under the Gen 5 bidder, 0.74 common under the Gen 6 bidder, where the
table's own pair-effect variance enters the test). Effects of 0.1 to 0.3 IMPs, the size that would
matter for promotions, are neither shown nor excluded. With the simulator's finding that a single
effect of 0.3 is covered only 67% of the time by its cell (E9-5), the rating table should keep
the per-pair residual test and report a flagged pair's own result.

**Tables.** Strengths are IMPs a board against BEN (16); "vs Gen 6 fast" is the same fit read
against `6-32`. Pairs are from the first-named side.

### common@5b7ea255

16,943 boards in 17 pairs; reference `ben`; pair-effect variance t2 = 0.0104 (Q = 12.12 on 8 degrees of freedom).

| Player | Strength vs BEN (16) | SE | vs Gen 6 fast | SE | Boards |
| --- | ---: | ---: | ---: | ---: | ---: |
| `7s-32` | +0.211 | 0.108 | +0.312 | 0.082 | 7,918 |
| `71s-32` | +0.208 | 0.190 | +0.309 | 0.176 | 430 |
| `6-256` | +0.141 | 0.137 | +0.241 | 0.120 | 1,705 |
| `ben64` | +0.040 | 0.180 | +0.141 | 0.166 | 954 |
| `ben` | +0.000 | 0.000 | +0.101 | 0.103 | 3,525 |
| `6-32` | -0.101 | 0.103 | +0.000 | 0.000 | 11,422 |
| `3` | -0.796 | 0.206 | -0.695 | 0.178 | 755 |
| `2` | -0.810 | 0.207 | -0.710 | 0.180 | 758 |
| `5RZ32` | -0.870 | 0.138 | -0.769 | 0.103 | 4,344 |
| `1` | -1.919 | 0.158 | -1.818 | 0.132 | 2,075 |

| Pair | Boards | Own result (95%) | Fitted | Leave-one-out prediction | z | Holm p | Out of line |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `7s-32~6-32` | 3,083 | +0.262 (+0.15 to +0.38) | +0.312 | +0.363 ± 0.129 | -0.52 | 1.000 | no |
| `6-32~5RZ32` | 3,025 | +0.730 (+0.58 to +0.88) | +0.769 | +0.838 ± 0.197 | -0.44 | 1.000 | no |
| `6-32~ben` | 1,835 | -0.106 (-0.31 to +0.10) | -0.101 | -0.094 ± 0.164 | -0.05 | 1.000 | no |
| `7s-32~1` | 1,319 | +2.238 (+1.99 to +2.48) | +2.130 | +1.944 ± 0.207 | +1.13 | 1.000 | no |
| `7s-32~5RZ32` | 1,319 | +1.139 (+0.92 to +1.36) | +1.081 | +1.026 ± 0.178 | +0.46 | 1.000 | no |
| `7s-32~ben` | 1,274 | +0.095 (-0.14 to +0.33) | +0.211 | +0.326 ± 0.159 | -1.01 | 1.000 | no |
| `6-32~6-256` | 1,133 | -0.134 (-0.34 to +0.07) | -0.241 | -0.466 ± 0.205 | +1.35 | 1.000 | no |
| `6-32~2` | 758 | +0.712 (+0.42 to +1.01) | +0.710 | none (only link) | | | not testable |
| `6-32~1` | 756 | +1.671 (+1.35 to +1.99) | +1.818 | +1.951 ± 0.178 | -1.07 | 1.000 | no |
| `6-32~3` | 755 | +0.698 (+0.41 to +0.99) | +0.695 | none (only link) | | | not testable |
| `7s-32~ben64` | 684 | +0.069 (-0.23 to +0.37) | +0.171 | +0.409 ± 0.280 | -1.02 | 1.000 | no |
| `6-256~ben` | 392 | +0.426 (+0.03 to +0.82) | +0.141 | -0.020 ± 0.151 | +1.71 | 1.000 | no |
| `71s-32~7s-32` | 239 | -0.201 (-0.51 to +0.11) | -0.003 | +0.380 ± 0.275 | -1.74 | 1.000 | no |
| `6-256~ben64` | 180 | +0.044 (-0.56 to +0.65) | +0.100 | +0.139 ± 0.235 | -0.23 | 1.000 | no |
| `71s-32~ben64` | 90 | +0.822 (-0.01 to +1.65) | +0.168 | -0.040 ± 0.222 | +1.81 | 1.000 | no |
| `71s-32~6-32` | 77 | +0.636 (-0.01 to +1.28) | +0.309 | +0.223 ± 0.197 | +0.95 | 1.000 | no |
| `71s-32~ben` | 24 | -0.458 (-2.17 to +1.26) | +0.208 | +0.250 ± 0.198 | -0.84 | 1.000 | no |

### common@9ee52f3b

17,727 boards in 15 pairs; reference `ben`; pair-effect variance t2 = 0.0 (Q = 0.77 on 5 degrees of freedom).

| Player | Strength vs BEN (16) | SE | vs Gen 6 fast | SE | Boards |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ben` | +0.000 | 0.000 | — | — | 1,220 |
| `5RZ192` | -0.444 | 0.214 | — | — | 426 |
| `5R192` | -0.534 | 0.192 | — | — | 738 |
| `5RZ32` | -0.557 | 0.183 | — | — | 2,499 |
| `5` | -0.564 | 0.142 | — | — | 1,549 |
| `5R32` | -0.719 | 0.170 | — | — | 10,432 |
| `3` | -0.775 | 0.182 | — | — | 2,669 |
| `4b` | -0.775 | 0.174 | — | — | 5,337 |
| `5-32` | -0.779 | 0.166 | — | — | 7,920 |
| `2` | -0.919 | 0.187 | — | — | 1,997 |
| `1` | -1.960 | 0.237 | — | — | 667 |

| Pair | Boards | Own result (95%) | Fitted | Leave-one-out prediction | z | Holm p | Out of line |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `5R32~4b` | 2,786 | +0.041 (-0.10 to +0.18) | +0.056 | +0.086 ± 0.098 | -0.38 | 1.000 | no |
| `5-32~4b` | 2,551 | +0.014 (-0.13 to +0.16) | -0.004 | -0.033 ± 0.095 | +0.39 | 1.000 | no |
| `5RZ32~5R32` | 2,499 | +0.162 (+0.03 to +0.30) | +0.162 | none (only link) | | | not testable |
| `5R32~5-32` | 1,845 | +0.100 (-0.05 to +0.25) | +0.060 | +0.027 ± 0.073 | +0.68 | 1.000 | no |
| `5R32~3` | 1,393 | +0.020 (-0.18 to +0.22) | +0.056 | +0.106 ± 0.121 | -0.54 | 1.000 | no |
| `5-32~3` | 1,276 | +0.035 (-0.17 to +0.24) | -0.004 | -0.053 ± 0.118 | +0.55 | 1.000 | no |
| `5R32~2` | 1,040 | +0.206 (-0.04 to +0.45) | +0.201 | +0.195 ± 0.134 | +0.06 | 1.000 | no |
| `5~5-32` | 972 | +0.212 (-0.01 to +0.43) | +0.215 | +0.246 ± 0.359 | -0.09 | 1.000 | no |
| `5-32~2` | 957 | +0.137 (-0.10 to +0.37) | +0.140 | +0.144 ± 0.136 | -0.04 | 1.000 | no |
| `5~ben` | 577 | -0.560 (-0.87 to -0.25) | -0.564 | -0.585 ± 0.341 | +0.07 | 1.000 | no |
| `5R32~5R192` | 521 | -0.209 (-0.52 to +0.10) | -0.185 | -0.065 ± 0.353 | -0.37 | 1.000 | no |
| `5RZ192~ben` | 426 | -0.446 (-0.87 to -0.02) | -0.444 | none (only link) | | | not testable |
| `5R32~1` | 348 | +1.279 (+0.81 to +1.75) | +1.241 | +1.199 ± 0.249 | +0.23 | 1.000 | no |
| `5-32~1` | 319 | +1.154 (+0.67 to +1.64) | +1.181 | +1.207 ± 0.242 | -0.16 | 1.000 | no |
| `5R192~ben` | 217 | -0.622 (-1.21 to -0.03) | -0.534 | -0.469 ± 0.253 | -0.40 | 1.000 | no |

### native

34,670 boards in 32 pairs; reference `ben`; pair-effect variance t2 = 0.0 (Q = 14.69 on 17 degrees of freedom).

| Player | Strength vs BEN (16) | SE | vs Gen 6 fast | SE | Boards |
| --- | ---: | ---: | ---: | ---: | ---: |
| `7s-32` | +0.472 | 0.086 | +0.318 | 0.050 | 7,918 |
| `71s-32` | +0.412 | 0.170 | +0.258 | 0.155 | 430 |
| `6-256` | +0.311 | 0.116 | +0.157 | 0.094 | 1,705 |
| `6-32` | +0.154 | 0.082 | +0.000 | 0.000 | 11,422 |
| `ben` | +0.000 | 0.000 | -0.154 | 0.082 | 4,745 |
| `ben64` | -0.098 | 0.177 | -0.253 | 0.163 | 954 |
| `5RZ192` | -0.399 | 0.232 | -0.553 | 0.246 | 426 |
| `5R192` | -0.567 | 0.162 | -0.722 | 0.155 | 738 |
| `5` | -0.582 | 0.119 | -0.736 | 0.116 | 1,549 |
| `5RZ32` | -0.679 | 0.097 | -0.833 | 0.064 | 6,843 |
| `5R32` | -0.779 | 0.099 | -0.934 | 0.073 | 10,432 |
| `5-32` | -0.820 | 0.102 | -0.975 | 0.081 | 7,920 |
| `4b` | -0.830 | 0.111 | -0.985 | 0.089 | 5,337 |
| `3` | -0.857 | 0.115 | -1.011 | 0.093 | 3,424 |
| `2` | -0.889 | 0.118 | -1.043 | 0.096 | 2,755 |
| `1` | -1.811 | 0.122 | -1.966 | 0.099 | 2,742 |

| Pair | Boards | Own result (95%) | Fitted | Leave-one-out prediction | z | Holm p | Out of line |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `7s-32~6-32` | 3,083 | +0.262 (+0.15 to +0.38) | +0.318 | +0.471 ± 0.096 | -1.85 | 1.000 | no |
| `6-32~5RZ32` | 3,025 | +0.821 (+0.65 to +0.99) | +0.833 | +0.848 ± 0.095 | -0.21 | 1.000 | no |
| `5R32~4b` | 2,786 | +0.046 (-0.10 to +0.19) | +0.051 | +0.060 ± 0.098 | -0.11 | 1.000 | no |
| `5-32~4b` | 2,551 | +0.016 (-0.13 to +0.17) | +0.010 | +0.001 ± 0.095 | +0.12 | 1.000 | no |
| `5RZ32~5R32` | 2,499 | +0.162 (+0.03 to +0.30) | +0.101 | -0.107 ± 0.126 | +1.87 | 1.000 | no |
| `5R32~5-32` | 1,845 | +0.100 (-0.05 to +0.25) | +0.041 | -0.006 ± 0.071 | +1.00 | 1.000 | no |
| `6-32~ben` | 1,835 | +0.054 (-0.19 to +0.30) | +0.154 | +0.235 ± 0.110 | -1.10 | 1.000 | no |
| `5R32~3` | 1,393 | +0.027 (-0.18 to +0.23) | +0.077 | +0.129 ± 0.105 | -0.68 | 1.000 | no |
| `7s-32~1` | 1,319 | +2.231 (+1.95 to +2.51) | +2.283 | +2.333 ± 0.138 | -0.52 | 1.000 | no |
| `7s-32~5RZ32` | 1,319 | +1.407 (+1.15 to +1.67) | +1.151 | +1.042 ± 0.086 | +2.31 | 0.639 | no |
| `5-32~3` | 1,276 | +0.049 (-0.16 to +0.26) | +0.036 | +0.023 ± 0.107 | +0.17 | 1.000 | no |
| `7s-32~ben` | 1,274 | +0.483 (+0.20 to +0.77) | +0.472 | +0.467 ± 0.107 | +0.09 | 1.000 | no |
| `6-32~6-256` | 1,133 | -0.134 (-0.34 to +0.07) | -0.157 | -0.252 ± 0.215 | +0.49 | 1.000 | no |
| `5R32~2` | 1,040 | +0.186 (-0.06 to +0.43) | +0.110 | +0.051 ± 0.110 | +0.80 | 1.000 | no |
| `5~5-32` | 972 | +0.212 (-0.01 to +0.43) | +0.239 | +0.331 ± 0.211 | -0.50 | 1.000 | no |
| `5-32~2` | 957 | +0.097 (-0.14 to +0.34) | +0.069 | +0.043 ± 0.116 | +0.32 | 1.000 | no |
| `6-32~2` | 758 | +0.859 (+0.53 to +1.19) | +1.043 | +1.135 ± 0.118 | -1.35 | 1.000 | no |
| `6-32~1` | 756 | +1.815 (+1.45 to +2.18) | +1.966 | +2.028 ± 0.118 | -0.98 | 1.000 | no |
| `6-32~3` | 755 | +1.133 (+0.77 to +1.50) | +1.011 | +0.969 ± 0.108 | +0.76 | 1.000 | no |
| `7s-32~ben64` | 684 | +0.551 (+0.17 to +0.93) | +0.571 | +0.615 ± 0.286 | -0.19 | 1.000 | no |
| `5~ben` | 577 | -0.520 (-0.87 to -0.17) | -0.582 | -0.635 ± 0.163 | +0.48 | 1.000 | no |
| `5R32~5R192` | 521 | -0.209 (-0.52 to +0.10) | -0.212 | -0.224 ± 0.331 | +0.04 | 1.000 | no |
| `5RZ192~ben` | 426 | -0.401 (-0.87 to +0.06) | -0.399 | none (only link) | | | not testable |
| `6-256~ben` | 392 | +0.500 (+0.01 to +0.99) | +0.311 | +0.257 ± 0.132 | +0.88 | 1.000 | no |
| `5R32~1` | 348 | +1.267 (+0.79 to +1.74) | +1.032 | +0.971 ± 0.121 | +1.11 | 1.000 | no |
| `5-32~1` | 319 | +1.179 (+0.69 to +1.66) | +0.991 | +0.941 ± 0.126 | +0.87 | 1.000 | no |
| `71s-32~7s-32` | 239 | -0.201 (-0.51 to +0.11) | -0.060 | +0.305 ± 0.284 | -1.51 | 1.000 | no |
| `5R192~ben` | 217 | -0.562 (-1.21 to +0.08) | -0.567 | -0.569 ± 0.189 | +0.02 | 1.000 | no |
| `6-256~ben64` | 180 | +0.294 (-0.38 to +0.97) | +0.410 | +0.455 ± 0.207 | -0.41 | 1.000 | no |
| `71s-32~ben64` | 90 | +0.878 (-0.13 to +1.89) | +0.511 | +0.427 ± 0.228 | +0.85 | 1.000 | no |
| `71s-32~6-32` | 77 | +0.636 (-0.01 to +1.28) | +0.258 | +0.179 ± 0.170 | +1.11 | 1.000 | no |
| `71s-32~ben` | 24 | +0.583 (-1.32 to +2.49) | +0.412 | +0.405 ± 0.173 | +0.21 | 1.000 | no |

## Provisional field score

`ratings-v1.json` also carries a field score per player against a provisional field (BEN 16,
BEN 64, Gen 5 (32) and Gen 1 in equal shares, where present). The field is a decision for Max;
this one is only there to exercise the code.

## Limits

- The native table pools two eras (Gen 5 feeds and Gen 6 to 7.1 feeds) through the bots they
  share (`ben`, `1`, `2`, `3`, `5RZ32`).
- `ben64`'s two configurations are pooled.
- Boards are taken as independent within a pair once a family counts once; deals shared between
  different pairs are not modelled.
- The common table under the Gen 5 bidder fits closer than chance (Q = 0.77 on 5 degrees of
  freedom; a chi-square that small has probability 0.021), which suggests some positive correlation between its
  pairs (shared deals or near-identical bots); its intervals may be a little wide.

## Reproduce

    python scripts/arena_feed_rows.py --out rows.jsonl.gz
    python scripts/arena_feed_rows.py --registry reports/gen9-ratings-v1-2026-11-12/gen5-registry.json --out rows-gen5.jsonl.gz   # the five Gen 5 feeds
    python scripts/arena_ratings_fit.py --rows rows.jsonl.gz --rows rows-gen5.jsonl.gz --out ratings-v1.json --markdown tables.md
    python -m unittest tests.test_arena_ratings_fit
