# Rollout loop: the sandbox matches of 13 November 2026

**Work in progress. Research data, not an arena cohort and not a feed. Never merge this branch.** The match rows behind
the tables in `training/rollout-loop-20261113/README.md` on `research/rollout-loop-20261113`: a rollout bot from trick 7
against a net alone, and the control that separates the net inside the rollouts from the opponent it is matched to.

- Played in a Claude session's 2-core sandbox with `scripts/x8_match.py` on the 8X engine at `1a779a9`, source capsule
  `arena-gen6-gen7-capture-feed:recovery/` (manifest sha256 `2f8f6b792ac874f1...`), seed 131, deals 0 to 299, common bidder
  `6-32`. `r3` was stopped at 63 boards.
- `smoke-bots.json` is the bots file as run. The same bots are in `configs/loop-bots.json` on the source branch (equal
  apart from labels and the list of names in `opponent_play_weight`; `make_bots.py` there was checked against it).
- Folders: `r7` (`r7-v41~n-v41`), `r3` (`r3-v41~n-v41`), `r7x_v0` and `r7x_v4` (`r7x-v0~n-v41`, `r7x-v4~n-v41`),
  `c_n41_n4` (`n-v41~n-v4`), `c_r7_n4` (`r7-v41~n-v4`), `c_r7x4_n4` (`r7x-v4~n-v4`), `c_r7_r7f4` (`r7-v41~r7f-v4`).
  One row a board in `results.jsonl`; `common` is the IMPs to the first-named bot with both tables in the same contract.
- `lev.py` and `lev2.py` print `summary.txt` from the rows (paths are the sandbox's).
