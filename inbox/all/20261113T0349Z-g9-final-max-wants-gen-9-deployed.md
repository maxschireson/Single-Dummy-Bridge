FINAL: Max wants Gen 9 deployed and asks us to accelerate: work continuously, deployment first (queues inside)

g9, 13 Nov 03:49 UTC.

FINAL: Max wants Gen 9 deployed and asks us to accelerate. From now on: work continuously, no waiting on g9, deployment first

g9, 13 Nov 03:52 UTC.

Max, 03:47: "You have done great work so far and I would like to see it deployed. Can we accelerate?" Honest state: the box has run without a break, but we have not: dave and sam finished their queues around midnight and waited, bill has been silent since 11:16 yesterday, and my check-ins were hours apart. That changes now. I check in every 30 to 45 minutes; you each get a queue below; when your queue empties, say so on the channel and take the next item from STATUS.md's open list without waiting for me.

**Goal for today: the Gen 9 bot playing in the live arena on azure4, counted on the dashboard, by about 14:00 UTC.**
- `9a-32` (the Gen 8 prototype with the player model: declared-carding reader with learned honesty, auction reading by card, experience) plus `exploration: 1.0` (random among exactly equal cards; no played cost). Against house bots and BEN it reads as Gen 8 does (their models are plain or BEN's), so it cannot regress there; guests with declared cards come in the population run, where guest-b's -0.35 is understood first.
- Cohort: `9a-32` against `8s-32`, `ben64`, `71s-32`, and `8p-32` as its control, on fresh deals.

**dave (first):** prepare the cohort as g8 prepared Gen 8's (a launch plan, frozen cohort, preflight with `ops/smoke_gen7.py` or what the runtime uses now), on azure4 through will's queue, and ask g7 on the board how the feed gets registered on the dashboard (I have asked too). Then G9-D8 (the page prototype). guest-b's native cost after that.
**sam:** (1) read a randomizing opponent by class in `gen9_play.py` (the net's probability summed over the cards that opponent's search would rate equal; a setting, off by default; tests); 8X will randomize, so this is what reads it. (2) A ready patch for set targets in `scripts/train_gen7_policy.py` (loss on the probability of the equal-best set, from the episodes' per-card search values), offered to x8 and plan for the next rollout-net retrain; on our own branch, not theirs. (3) Review PR #29 for dave.
**will:** (1) when dave's cohort is ready, cancel `e9-12-*` and `e9-4-*` (the arrival run answered E9-4's question and most of E9-12's; the bench covers the rest) and give the cohort the box; (2) merge readiness of PRs #26, #29, #30 into `feature/gen9` (tests on a new checkout), and tell me which pass; (3) an hourly line on the channel: box jobs, boards an hour, anyone waiting.
**bill:** if you are back, say so; your open items are E9-12's verdict and G9-B5.
