# G9-S5 learning curve: honesty learned from boards of experience

Gen 9 research (sam, signals), 12 November 2026. Part of E9-4 (`experiments/E9-4.md`) and G9-S5.
Kind of evidence: prediction. Nothing adopted.

**Method.** Same relabelled boards as E9-4 part 1 (`scripts/gen9_reading_gain.py --curve`), cells
std-80, ud-80 and std-50, readers at every assumed honesty 0, 0.1, ..., 1. The first N tables are
the experience: their `card.<key>` counts (`signal_experience.card_stats`, the true hands) give an
honesty estimate (`signal_experience.honesty`, prior 0.5 worth 8 occasions, floor 0.05, all keys
pooled). The last 96 tables are held out: the reader at the grid value nearest the estimate is
scored there, as reader minus Gen 8's unknown-opponent reading, nats per declarer decision (1,032
decisions; standard errors clustered by table, about ±0.09 to ±0.12 on each value, the same
decisions in every row so differences between rows are far more precise).

| Boards of experience | Occasions | std-80: h estimate -> gain | ud-80 | std-50 |
| ---: | ---: | --- | --- | --- |
| 0 | 0 | 0.50 ± 0.15 -> +0.601 | 0.50 ± 0.15 -> +0.715 | 0.50 ± 0.15 -> +0.380 |
| 10 | 48 | 0.62 ± 0.10 -> +0.637 | 0.67 ± 0.09 -> +0.800 | 0.58 ± 0.10 -> +0.356 |
| 25 | 114 | 0.76 ± 0.06 -> +0.668 | 0.74 ± 0.06 -> +0.800 | 0.53 ± 0.07 -> +0.380 |
| 50 | 216 | 0.72 ± 0.05 -> +0.660 | 0.77 ± 0.04 -> +0.826 | 0.42 ± 0.06 -> +0.388 |
| 100 | 424 | 0.71 ± 0.04 -> +0.660 | 0.79 ± 0.03 -> +0.826 | 0.45 ± 0.04 -> +0.388 |
| 200 | 858 | 0.75 ± 0.02 -> +0.660 | 0.79 ± 0.02 -> +0.826 | 0.47 ± 0.03 -> +0.380 |
| The bots' true honesty | | 0.8 -> +0.668 ± 0.114 | 0.8 -> +0.826 ± 0.115 | 0.5 -> +0.380 ± 0.091 |

- About four signalling occasions per board. After 25 to 50 boards the estimate is within 0.05 of
  where it settles and the held-out gain is within 0.01 to 0.03 nats of the true-h reader (E9-4's
  prediction was "within a tenth at 200 boards").
- The estimate settles a little below the bots' nominal honesty (0.72 to 0.78 for the 0.8 bots):
  it measures adherence against the whole class, and the bots signal only among their tied cards.
  That is the honesty a reader should use, and it reads at least as well as the nominal value.
- The prior of 0.5 already captures most of the gain (+0.60 of +0.67 for std-80, +0.72 of +0.83
  for ud-80, all of it for std-50), because assuming too little honesty costs little (E9-4 part 1).

**Data.** `curve.json` (the table above and the gain at every fixed honesty), `curve_rows.jsonl.gz`.
