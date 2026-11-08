# Match report

Completed 1000 of 1000 paired boards; 0 failures. Positive IMPs favor the candidate.

Mean: **1.214 IMP/board**. Wins/ties/losses: 499/303/198.

Independent board/family clusters: 10. 95% cluster bootstrap interval: [0.713, 1.668].

Intervals measure deal sampling uncertainty, not systematic engine or corpus bias. Failures are excluded from scores and reported separately. Synthetic auctions do not represent a realistic bidding population.

| Player | Decisions | Mean ms | p95 ms | DDS calls |
|---|---:|---:|---:|---:|
| greedy | 77000 | 0.02 | 0.05 | 0 |
| pimc | 25000 | 4.46 | 22.57 | 39178 |

## Largest differences

| Board | IMPs | NS scores | Declarer tricks | First differing ply (0-based) |
|---|---:|---|---|---|
| 565 | 12 | [-250, 400] | [4, 9] | 4 |
| 708 | 12 | [-200, 420] | [6, 10] | 2 |
| 718 | 12 | [-250, 420] | [5, 10] | 2 |
| 753 | 12 | [-200, 420] | [6, 10] | 4 |
| 775 | 12 | [-250, 420] | [5, 10] | 2 |
| 555 | 11 | [-150, 400] | [6, 9] | 2 |
| 560 | 11 | [-100, 400] | [7, 9] | 5 |
| 574 | 11 | [-150, 400] | [6, 9] | 2 |
| 587 | -11 | [400, -100] | [9, 7] | 2 |
| 596 | -11 | [400, -100] | [9, 7] | 4 |
