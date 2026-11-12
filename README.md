# The deal families policy v4.1 was trained on

`v41_training_families.txt.gz`: one family hash a line, sorted; every deal of the training set `gen7_v41_train.npz` (boards fetched up to 03:59 UTC on 12 November 2026; see `training/policy-v4.1-20261112/` on `transfer/gen7-policy-v4.1-20261112`). A net trained on that set (v4.1 and the five-epoch and 768-wide nets of the same run) must not be scored on these deals.
