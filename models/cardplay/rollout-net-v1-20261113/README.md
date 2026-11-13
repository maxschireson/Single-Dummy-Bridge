# Rollout net v1 (13 November 2026), as used by the 8X bots

Not kept in git: `python restore.py` fetches `policy_ft.npz` (v4.1 fine-tuned on the Gen 7+ bots' searched decisions,
512 wide) and `policy_scratch.npz` (the same data from random weights) from `transfer/rollout-net-v1-20261113` and
checks their SHA-256. Trained by the plan session (`training/rollout-net-v1-20261113`); scores in that branch's
`runs/*/metrics.json`. `scripts/gen8_match.py` and `scripts/x8_match.py` run `restore.py` when a bot names a file here
that is missing. Same inputs as policy v4.1 (`gen7_net.PolicyNet`); the scorer is the hand-fit scorer v0.
