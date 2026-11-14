# Rollout review correction

Old recursive/selective results are invalid for inference. V2 correctness-only progress follows; source d82f9a7, native acceptance passed.

# Stu rollout mechanism screen

Development-only; these small samples do not establish strength.

| Run | Boards | IMP/board ± SE | Python CPU s/board (solver excluded) | Failures |
| --- | ---: | ---: | ---: | ---: |
| smoke-flat32 | 16 | -2.0 ± 0.9129 | 23.86 | 0 |
| smoke-recursive32 | 16 | -0.4375 ± 0.8707 | 51.52 | 0 |
| smoke-selective32 | 5 | 0.4 ± 0.2449 | 49.97 | 0 |

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
| rx2-selective32 | 175.33 | 172.10 | 3.20 | 590.0 | 0.0 |
| rx2-control | 74.16 | 72.66 | 1.53 | 0 | 0.0 |
