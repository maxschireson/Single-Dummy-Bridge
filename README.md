# The arrival run's full-path rehearsal (G9-D6), one machine, 12 November 2026

This is a transfer branch: records only, never merged into source.

**What ran.** The box run's events file (`configs/arena9/arrival-events.json`) on five 16-board epochs:
- guest-a was submitted before epoch 2;
- 7s-32 was retired by a queued command before epoch 4, and guest-b was submitted then;
- an epoch-3 floor board was replayed.

The rules are `rules-fullpath.json`: `rules-arrival.json` with epochs of 16 boards and floors of 4 (guest-a) and 3 (guest-b) boards a pair.

**Where it ran.** A fresh worktree of `feature/gen9-arena-arrival` at 4354b64. DDS was built first. The nets were restored only by the runner's and bill's on-first-use code (d4515bd, 514e046), as in a box checkout. Wall time was 19 minutes, 31 CPU-minutes, with 2 workers.

**Files.**
- `control/`: the control directory as the runner left it (epoch 6 is opened but not played).
- `report.md`: the page, regenerated with the report code of e81625b, which adds the other profiles and marks retired players.
- `replay.json`: the replay result.
- `results.jsonl`: every board row.
- `run.txt`: the runner's output.

**What the records do not have.** guest-b's package here still names the Gen 6 bidder's hash (fixed in 32dcf6f). Its bidding is the Gen 5 net in both versions. The retire event has no epoch field, because plan events got one only in e81625b. Item 1's numbers are 4 and 3 deals an epoch, so they say nothing about the effect.
