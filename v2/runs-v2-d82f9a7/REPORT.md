# Stu rollout mechanism screen

Development-only; these small samples do not establish strength.

| Run | Boards | IMP/board ± SE | Python CPU s/board (solver excluded) | Failures |
| --- | ---: | ---: | ---: | ---: |
| calibration-c1 | 16 | -2.4375 ± 1.1104 | 33.95 | 0 |
| extended-recursive32 | 192 | -0.2812 ± 0.3025 | 56.04 | 0 |
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
| rx2-recursive32 | 7616.10 | 7368.05 | 223.65 | 24136.0 | 9.0 |
| rx2-control | 3495.67 | 3338.61 | 145.33 | 0 | 8.0 |

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
