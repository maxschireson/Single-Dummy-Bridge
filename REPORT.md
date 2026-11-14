# Rollout review correction

Old recursive/selective results are invalid for inference. V2 correctness-only progress follows; source d82f9a7, native acceptance passed.

# Stu rollout mechanism screen

Development-only; these small samples do not establish strength.

| Run | Boards | IMP/board ± SE | Python CPU s/board (solver excluded) | Failures |
| --- | ---: | ---: | ---: | ---: |
| smoke-flat32 | 8 | -1.5 ± 1.4142 | 23.88 | 0 |

## smoke-flat32 actor costs

| Actor | Action wall s | Worker CPU s | Solver CPU s | Child searches | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| rx2-flat32 | 69.23 | 67.32 | 1.83 | 0 | 0.0 |
| rx2-control | 122.39 | 118.27 | 4.27 | 0 | 0.0 |
