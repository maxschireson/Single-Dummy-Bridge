# E9-21: field choice and the Nash average on the ladder's cells (g9, 13 November 2026)

Gen 9 experiment E9-21 (`team/gen9:experiments/E9-21.md`), for [the arena design note](../../docs/gen9/arena-selfplay.md),
section 5.2. Read-only; decides nothing.

**Data.** The rows of every registered feed collected at 07:14 UTC with `scripts/arena_ladder.py collect`
(`feature/gen9-ladder` at 7f08ad91): 104,386 rows from 113 sources. The Gen 9 cohort's feed (`gen9azure4`, 92 boards
at the time) is left out, which gives the ladder's 22 points and 67,582 native boards. Points, variant merging,
counting rules and bench priors are the ladder's own (`e9_21.py` calls its functions).

**Method.** Cells as in A4 (a played pair's own mean mixed with the leave-one-out prediction; an unplayed pair's
prediction). Field scores: the mean cell against (a) every other point, (b) a declared example field of BEN 64,
`8s-32`, `71s-32` and `6-32`. The Nash average (Balduzzi et al. 2018, https://arxiv.org/abs/1806.02643): each
point's expected cell against the maximum-entropy Nash equilibrium of the cells matrix. Standard errors from 200
bootstrap replicates, boards resampled within each pair. Run with and without the bench priors.

## Result (with priors)

| Point | Strength | Field: whole population | Field: BEN 64, 8s-32, 71s-32, 6-32 | Nash average |
| --- | ---: | ---: | ---: | ---: |
| `8s-32` | +0.654 +- 0.060 | +1.431 +- 0.055 | +0.599 +- 0.033 | +0.000 +- 0.000 |
| `7s-32` | +0.244 +- 0.062 | +1.007 +- 0.051 | +0.055 +- 0.032 | -0.410 +- 0.025 |
| `71s-32` | +0.214 +- 0.060 | +0.968 +- 0.051 | +0.026 +- 0.032 | -0.497 +- 0.048 |
| `6-256` | +0.051 +- 0.118 | +0.801 +- 0.113 | -0.150 +- 0.104 | -0.602 +- 0.111 |
| `ben64` | +0.000 +- 0.000 | +0.747 +- 0.080 | -0.253 +- 0.054 | -0.565 +- 0.070 |
| `6-32` | -0.080 +- 0.070 | +0.662 +- 0.050 | -0.371 +- 0.039 | -0.734 +- 0.038 |
| `8c-32` | -0.133 +- 0.118 | +0.607 +- 0.114 | -0.330 +- 0.106 | -0.856 +- 0.131 |
| `ben` | -0.232 +- 0.103 | +0.503 +- 0.080 | -0.422 +- 0.086 | -0.863 +- 0.105 |
| `5RZ192` | -0.638 +- 0.278 | +0.078 +- 0.262 | -0.835 +- 0.266 | -1.292 +- 0.266 |
| `5R192` | -0.781 +- 0.176 | -0.071 +- 0.154 | -0.978 +- 0.165 | -1.434 +- 0.166 |
| `5` | -0.787 +- 0.130 | -0.078 +- 0.109 | -0.984 +- 0.114 | -1.440 +- 0.113 |
| `ben64#41c8c9` | -0.797 +- 0.441 | -0.089 +- 0.443 | -0.994 +- 0.439 | -1.451 +- 0.441 |
| `5RZ32` | -0.932 +- 0.088 | -0.229 +- 0.067 | -1.128 +- 0.062 | -1.599 +- 0.090 |
| `5R32` | -0.985 +- 0.098 | -0.285 +- 0.060 | -1.181 +- 0.076 | -1.638 +- 0.077 |
| `5-32` | -1.017 +- 0.105 | -0.318 +- 0.069 | -1.213 +- 0.083 | -1.670 +- 0.084 |
| `4b` | -1.039 +- 0.114 | -0.342 +- 0.079 | -1.236 +- 0.093 | -1.692 +- 0.092 |
| `2` | -1.050 +- 0.108 | -0.354 +- 0.072 | -1.242 +- 0.087 | -1.704 +- 0.085 |
| `3` | -1.095 +- 0.107 | -0.401 +- 0.067 | -1.297 +- 0.085 | -1.749 +- 0.085 |
| `4` | -1.457 +- 0.119 | -0.780 +- 0.082 | -1.654 +- 0.100 | -2.111 +- 0.100 |
| `4p` | -1.714 +- 0.136 | -1.049 +- 0.106 | -1.911 +- 0.118 | -2.368 +- 0.118 |
| `1` | -1.964 +- 0.103 | -1.311 +- 0.090 | -2.147 +- 0.082 | -2.573 +- 0.101 |
| `1#330e78` | -2.143 +- 0.278 | -1.498 +- 0.259 | -2.339 +- 0.270 | -2.796 +- 0.272 |

- The order of the top five is the same under both fields; Spearman 0.999 over all 22 points.
- The equilibrium is `8s-32` alone, in the point estimate and in all 200 replicates, so each point's Nash average is
  its cell against `8s-32`. Its order swaps BEN 64 and `6-256` (fourth and fifth, within one standard error).
- The Nash averages' bootstrap standard errors are about those of the field scores (median ratio 1.09; 1.17 without
  priors), not twice as large.
- Pair-effect variance t2 = 0.0067 (a standard deviation of 0.08 IMPs a board): the population is close to transitive.
- Without priors: the same orders, t2 = 0.0074, the same equilibrium.

Predictions as registered: (1) top-five order unchanged: met; (2) equilibrium on three members or fewer: met (one);
(3) Nash standard errors at least twice the field scores': not met.

**What it means for the design.** In today's population the field choice moves the levels, not the order, and the
Nash average is the cell against the champion. Both will diverge from equal weights once the population holds cycles
or several strong styles, which is when the declared field matters.

```
python3 e9_21.py --ladder-wt <checkout of feature/gen9-ladder> --rows rows.jsonl.gz --out e9_21_priors.json \
    --boot 200 --exclude-source gen9azure4            # add --no-priors for the second run
```
