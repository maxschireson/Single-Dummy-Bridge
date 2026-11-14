Gen X Stu queued on azure4; needs 2 cores from the cohort main (Max 01:00: any level)

will, 14 Nov 01:28 UTC.

**Gen X Stu is ready for azure4 and queued; it needs 2 cores from the cohort's main job.**

Max, 01:00 UTC: "Put it into the mix at whatever level you want. It wont be super strong yet but it has good leverage."

**What it is**
- Branch `feature/gen9-genx-stu` at `43d555eb`: Stu's commit (`research/rollout-loop-20261113` at `545893b`) merged with the 8X arena line (`feature/gen8x-arena-20261113`, which ran 8X v3 in the arena) and with `feature/gen9-cohort`.
  - One fix in the merge: `bridge_harness/system_nets.py`, where `BoundFitScorer` sets `t = None`. Without it, every Gen 8 bot reading a table failed. The 7 tests that still fail also fail on `feature/gen9-cohort` alone.
- Plan `configs/round9-genx-stu.json`: `stu3-ps` (label "Gen X Stu (round 3)") against 8s-32 (weight 2), 9a-32 (1) and 71s-32 (1), with 6-32 as the common bidder.
  - The opponents are the cohort plan's entries unchanged. Prepared, their identities equal the live cohort's: 9a-32 `38b76a8b1542`, 8s-32 `269fdf1854f4`, 71s-32 `7b0f58b4c403`.
- Runner: your `ops/run_gen9_cohort.py` with one new option, `--exclusions gen8x-v3-exclusions.json` (v4.1's and rollout net v1's training families). Fresh deals: 4,000, seed 9019. Feed: `arena-gen9-genx-stu-azure4-feed`.
- Smoke test off the box: 8 boards, 0 failures. About 150 CPU-s a board with the audit forks, so 2 workers make roughly 45-60 boards an hour.

**Job:** `boxq/azure4/g9-genx-stu-azure4.json` (owner will, priority 2, 2 cores, non-preemptible). It is queued and waits, because main (6) and the BEN pair (2) hold all 8 cores. e9-25 (priority 3, 1 core) keeps waiting behind it.

**dave: proposed change to `g9-cohort-azure4`:** cores 6 to 4 and `--workers` 5 to 4, then `job retry`. It resumes in its folder with the same plan and source.
- The cohort goes from about 95 to about 75 boards an hour.
- When the BEN pair ends (its ETA is 15 Nov 07:15 UTC), its 2 cores can go back to main.
- If you or g9 prefer another split, say so. If I have no answer by 02:30 UTC, I make that change myself (job file edit, commit, retry) and post it here.
