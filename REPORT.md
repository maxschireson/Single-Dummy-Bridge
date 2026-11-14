# Rollout review correction

Old recursive/selective results are invalid for inference. V2 correctness-only progress follows; source d82f9a7, native acceptance passed.

# Stu rollout mechanism screen

Development-only; these small samples do not establish strength.

| Run | Boards | IMP/board ± SE | Python CPU s/board (solver excluded) | Failures |
| --- | ---: | ---: | ---: | ---: |
| calibration-c1 | 16 | -2.4375 ± 1.1104 | 33.95 | 0 |
| extended-recursive32 | 110 | -0.1545 ± 0.3721 | 56.51 | 0 |
| smoke-flat32 | 16 | -2.0 ± 0.9129 | 23.86 | 0 |
| smoke-recursive32 | 16 | -0.4375 ± 0.8707 | 51.52 | 0 |
| smoke-selective32 | 16 | -0.9375 ± 0.7609 | 52.77 | 0 |

## calibration-c1 actor costs

| Actor | Action wall s | Worker CPU s | Solver CPU s | Child searches | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| rx2-recursive32-c1 | 305.85 | 297.31 | 8.39 | 548.0 | 0.0 |
| rx2-control | 250.16 | 239.40 | 11.07 | 0 | 0.0 |

## extended-recursive32 actor costs

| Actor | Action wall s | Worker CPU s | Solver CPU s | Child searches | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| rx2-recursive32 | 4405.95 | 4266.12 | 125.74 | 13833.0 | 8.0 |
| rx2-control | 2001.58 | 1917.27 | 77.46 | 0 | 3.0 |

## smoke-flat32 actor costs

| Actor | Action wall s | Worker CPU s | Solver CPU s | Child searches | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| rx2-flat32 | 141.78 | 137.23 | 4.42 | 0 | 0.0 |
| rx2-control | 248.23 | 238.07 | 10.45 | 0 | 0.0 |

## smoke-recursive32 actor costs

| Actor | Action wall s | Worker CPU s | Solver CPU s | Child searches | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| rx2-recursive32 | 591.61 | 571.77 | 19.98 | 2113.0 | 2.0 |
| rx2-control | 256.40 | 246.10 | 10.58 | 0 | 1.0 |

## smoke-selective32 actor costs

| Actor | Action wall s | Worker CPU s | Solver CPU s | Child searches | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| rx2-selective32 | 616.40 | 593.52 | 23.02 | 2025.0 | 2.0 |
| rx2-control | 254.98 | 244.29 | 10.98 | 0 | 1.0 |
