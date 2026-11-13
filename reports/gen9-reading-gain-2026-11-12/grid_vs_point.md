# Honesty carried as a grid through the board, against its posterior mean

Gen 9 research (sam, signals), 12 November 2026; g9's question of 08:25 UTC, part of E9-4 and G9-S5.
Kind of evidence: prediction. Nothing adopted.

**Question.** One honesty per opponent makes the signal likelihood of a board a product over its plays.
With h uncertain, the exact reading averages that product over the posterior of h, which is not the product
at the posterior mean. Does carrying h as a grid (0, 0.1, ..., 1) through the board read better?

**Method.** `scripts/gen9_honesty_mixture.py`. Cells std-80 and std-0 (relabelled defenders, as E9-4 part 1).
The posterior over h comes from the first N tables' card statistics (flat prior, the reader's floor allowed
for exactly). Both readers are scored on 198 held-out tables (2,136 declarer decisions each cell), class
term at factor 1: `point` (signal term at the posterior mean) and `grid` (the posterior mixture over h of
the board's product). Difference in nats per decision, paired, clustered by table.

| Boards of experience | std-80: posterior mean (sd) | grid minus point | std-0: posterior mean (sd) | grid minus point |
| ---: | --- | ---: | --- | ---: |
| 0 | 0.50 (0.32) | +0.0135 ± 0.0079 | 0.50 (0.32) | +0.0458 ± 0.0141 |
| 5 | 0.53 (0.17) | +0.0047 ± 0.0022 | 0.12 (0.12) | +0.0006 ± 0.0013 |
| 10 | 0.67 (0.11) | +0.0007 ± 0.0012 | 0.13 (0.10) | +0.0006 ± 0.0010 |
| 20 | 0.79 (0.07) | -0.0000 ± 0.0009 | 0.18 (0.09) | +0.0008 ± 0.0008 |

**Answer.** Only while the posterior is wide. With no experience (flat prior, sd 0.32) the grid reads
+0.014 ± 0.008 (std-80) and +0.046 ± 0.014 (std-0) nats per decision better. After 5 boards the
difference is under 0.005; after 10 it is within noise. So the point value stays; the grid is worth having
only for the first boards against a player, and costs one signal evaluation per grid point.

**Data.** `grid_vs_point.json`, `grid_vs_point_priors.json`, `grid_vs_point_rows.jsonl.gz`.
