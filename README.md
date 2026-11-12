# Families policy net v4.1 was trained on: the union of the two lists (12 November 2026)

`v41-training-families-union.json`: a JSON list of 34,092 family hashes (the canonical deal key over rotations,
`bridge_harness.bidding_env.deal_key(hands, True)`), sorted; sha256 `0b8ac2b7f41b91915f518c42f76701728097b4151acb5d0e964051c261eca0e2`.
It is the union of:

- the independent collector's list, `recovery/artifacts/validation/all-training-families.json` on
  `arena-gen71-independent-feed` at `db4480b` (32,205 families, sha256 `4818856d731bee23...`), used for the Gen 7.1
  cohorts that leave the training families out;
- the policy 4.1 session's list, `v41_training_families.txt.gz` on `transfer/gen7-policy-v4.1-families-20261112`
  at `1132bcf` (34,029 families: every deal of the training set `gen7_v41_train.npz`).

1,887 families are only in the second, 63 only in the first. For the Gen 8 cohorts (`--exclude-families`, Max,
12 November 15:50 UTC: never a board in a family the bot was trained on, in the arena). Made by the arena operator,
Claude session https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ.
