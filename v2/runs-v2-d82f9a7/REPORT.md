# Stu rollout mechanism screen

Development-only; these small samples do not establish strength.

| Run | Boards | IMP/board ± SE | Python CPU s/board (solver excluded) | Failures |
| --- | ---: | ---: | ---: | ---: |
| smoke-flat32 | 16 | -2.0 ± 0.9129 | 23.86 | 0 |
| smoke-recursive32 | 16 | -0.4375 ± 0.8707 | 51.52 | 0 |
| smoke-selective32 | 10 | -1.4 ± 1.1944 | 50.1 | 0 |

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
| rx2-selective32 | 362.93 | 351.36 | 11.61 | 1231.0 | 2.0 |
| rx2-control | 148.56 | 143.88 | 4.82 | 0 | 0.0 |
