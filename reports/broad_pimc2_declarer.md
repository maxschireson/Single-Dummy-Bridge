# Match report

Completed 1000 of 1000 paired boards; 0 failures. Positive IMPs favor the candidate.

Mean: **1.999 IMP/board**. Wins/ties/losses: 529/317/154.

Independent board/family clusters: 1000. 95% cluster bootstrap interval: [1.764, 2.263].

Intervals measure deal sampling uncertainty, not systematic engine or corpus bias. Failures are excluded from scores and reported separately. Synthetic auctions do not represent a realistic bidding population.

| Player | Decisions | Mean ms | p95 ms | DDS calls |
|---|---:|---:|---:|---:|
| pimc | 26000 | 5.44 | 25.62 | 41444 |
| greedy | 76000 | 0.02 | 0.05 | 0 |

## Largest differences

| Board | IMPs | NS scores | Declarer tricks | First differing ply (0-based) |
|---|---:|---|---|---|
| 266 | 15 | [-630, 500] | [10, 4] | 3 |
| 516 | 15 | [-600, 500] | [9, 4] | 1 |
| 726 | 15 | [-630, 500] | [10, 4] | 3 |
| 32 | 14 | [-620, 300] | [10, 7] | 1 |
| 125 | 14 | [600, -400] | [11, 7] | 1 |
| 215 | 14 | [600, -300] | [11, 8] | 1 |
| 336 | 14 | [-600, 300] | [9, 6] | 8 |
| 383 | 14 | [620, -300] | [10, 7] | 1 |
| 554 | 14 | [-600, 300] | [11, 8] | 1 |
| 711 | 14 | [630, -400] | [10, 5] | 1 |
