# The arrival run's second full-path rehearsal (G9-D6), one machine, 12 November 2026

This is a transfer branch: records only, never merged into source. Source: `feature/gen9-arena-arrival` at 7175ae7 (rehearsal) and d50e10a+ (check script).

**The rehearsal.** The box run's events file and rules (`rules-arrival.json`, arrival-v2), with epochs of 16, 24, 24, 40 and 40 boards and floors of 6 (guest-a) and 10 (guest-b) boards a pair (`rules-fullpath2.json`). It ran in a fresh worktree with DDS built and the nets restored by the runner, on 2 workers. Wall time was 56 minutes; part of it overlapped the check below.

**Files.**
- `control/`: the control directory.
- `report.md`: the page, items 1 to 6.
- `replay.json`: the replay result.
- `results.jsonl`: every board row; floor rows carry `reading` (item 6).
- `run.txt`: the runner's output.

**`check/`: g9's bid-only release check** (`scripts/arena9_reading_check.py`, 11:57 UTC). The deals are new ones (seed 9157), bid by the bot's net and the guest's package, with a random legal lead. Item 6 is measured for 9a-32 with the guest's arrival model and with the epoch-5 snapshot, and for 8p-32, paired by deal. The files:
- `rc_b.jsonl` and `rc_a.jsonl`: per-deal rows, partial at the time of the push;
- `rc_main_summary.json`: their summary;
- `rc_diag*`: 40 further deals for guest-b (seed 9158) with two labelled diagnostics. `snapshot-nocard` is the snapshot model without its card. `snapshot-one-profile` is the best-read held profile (house-gen5) alone, without the card.
