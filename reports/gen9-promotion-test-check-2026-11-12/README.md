# First check of the Gen 9 promotion test on synthetic boards (12 November 2026)

Evidence kind: simulation. It supports the defaults in
[docs/gen9/arena-statistics.md](../../docs/gen9/arena-statistics.md), section 3, until
experiment E9-5 repeats it on the real per-board values from the feeds.

`python3 bet_check.py` (NumPy only, about two minutes, seed fixed). Boards are 75% flat and
otherwise a swing of 1 to 17 IMPs with a long tail (SD 2.75, kurtosis 18.6), with the true lead
set by the chance that a swing favours the candidate. 4,000 runs at a lead of 0 and 2,000 at
each other lead, each of 6,000 boards.

| True lead | Betting test promotes | Median boards when it does | Futility stops | Undecided at 6,000 | Hand rule promotes |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2.4% | 1,226 | 24.1% | 73.4% | 12.2% |
| 0.05 | 15.8% | 2,144 | 5.8% | 78.4% | 46.6% |
| 0.10 | 57.8% | 2,492 | 0.9% | 41.2% | 89.1% |
| 0.20 | 99.8% | 1,168 | 0.1% | 0.2% | 100% |
| 0.40 | 100% | 455 | 0 | 0 | 100% |

The hand rule is: from 1,000 boards, at every 100 boards, promote if the 95% interval of the
mean excludes zero on the candidate's side. Not tested here: real per-board values, pair-specific
spreads, the panel check, several candidates at once.
