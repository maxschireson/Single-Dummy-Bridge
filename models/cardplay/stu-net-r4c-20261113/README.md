# Stu's round 4 control net (14 November 2026), as Gen X Stu (round 4c) plays it in the arena

Not kept in git: `python restore.py` fetches `policy.npz` from `train-r4c/policy.npz` on
`transfer/rollout-loop-azure5-20261113` and checks its SHA-256 (`e4b689c8...`). The loop session trains it
(`training/rollout-loop-20261113` on `research/rollout-loop-20261113`, README "Round 4 as trained"): round 1's net
trained further on the loop's rows, without the human tables (the control). Same inputs as policy v4.1
(`gen7_net.PolicyNet`); the scorer is the hand-fit scorer v0. `stu4c-put` reads it both as its table net and in its
rollouts. `configs/round9-genx-stu-r4c.json` names it as the artifact `gen7_policy_stur4c`.
