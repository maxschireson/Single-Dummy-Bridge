# Stu's round 3 rollout net (14 November 2026), as Gen X Stu plays it in the arena

Not kept in git: `python restore.py` fetches `policy.npz` from `train-r3/policy.npz` on
`transfer/rollout-loop-azure5-20261113` and checks its SHA-256 (`a8cf8a94...`). The loop session trains it
(`training/rollout-loop-20261113` on `research/rollout-loop-20261113`): rollout net v2 trained further on the loop's
self-play games. Same inputs as policy v4.1 (`gen7_net.PolicyNet`); the scorer is the hand-fit scorer v0.
`configs/round9-genx-stu.json` names it as the artifact `gen7_policy_stur3`.
