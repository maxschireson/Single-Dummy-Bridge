# Frozen validation sets (Max, 21:35 UTC on 14 November: "A stable validation set would be better")

**V1** (`V1/manifest.json`, approved by loop at 21:55 UTC) has two parts:

- **Arena part.** 2,248 arena records (2,237 deals, 2,183 families with rows) from round 4's feeds. None is in rollout
  net v2's set or round 4's arena sample, and none shares a family with either. All are in the test split of the
  family hash. 1,647,975 rows (`V1/manifest.json` has the record list, the builder's commit and arguments, and the
  rows' sha256). Rebuild with `scripts/gen7_build_dataset.py` on the listed records (about 12 minutes on 2 cores).
  Selected by `select_v1.py`.
- **Stu part.** Round 4's test set (`train-r4c/stu_test.npz`, 300 deals, 12,419 rows), Stu's own play.

`V1/v1_families.txt` holds the 2,483 reserved families. From round 5, `check_families.py` fails any training set
that contains one. **freshB** (144 deals) is kept as its own set, V(width).

`training/perf-20261114/p10/eval_nets.py` scores each net on a set with the trainer's own `evaluate`. It reproduces
the width run's logged epoch scores on freshB exactly. `lifecycle.py` lays the reports side by side
(`V1/lifecycle-*.md`).
