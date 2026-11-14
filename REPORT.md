# Rollout review correction

Old recursive/selective results are invalid for inference. V2 correctness-only progress follows; source d82f9a7, native acceptance passed.

# Stu rollout mechanism screen

Development-only; these small samples do not establish strength.

| Run | Boards | IMP/board ± SE | Python CPU s/board (solver excluded) | Failures |
| --- | ---: | ---: | ---: | ---: |
| smoke-flat32 | 16 | -2.0 ± 0.9129 | 23.86 | 0 |
| smoke-recursive32 | 4 | 0.25 ± 0.25 | 46.68 | 0 |

## smoke-flat32 actor costs

| Actor | Action wall s | Worker CPU s | Solver CPU s | Child searches | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| rx2-flat32 | 141.78 | 137.23 | 4.42 | 0 | 0.0 |
| rx2-control | 248.23 | 238.07 | 10.45 | 0 | 0.0 |

## smoke-recursive32 actor costs

| Actor | Action wall s | Worker CPU s | Solver CPU s | Child searches | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| rx2-recursive32 | 127.81 | 125.72 | 2.07 | 510.0 | 0.0 |
| rx2-control | 56.86 | 56.05 | 0.78 | 0 | 0.0 |
