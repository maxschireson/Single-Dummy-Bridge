Gen X Stu now round 4c (stu4c-put) on azure4 since 16:22; round 3 ended at 719 and is archived

will, 14 Nov 16:26 UTC.

**Gen X Stu is now round 4c (`stu4c-put`), from 16:22 UTC, on the 2 cores round 3 had.**

**Why:** Max, 08:08: "I will have an iteration before long". To the play server's session he said "use r4c until further notice". At 08:08 I said a new iteration takes Gen X Stu's cores by default, round 3 stopping.

**The bot:** the loop's `stu4c-put` at `4488e91d`, gen7 and x8 blocks unchanged.
- It plays round 4's control net (no human tables), both at the table and in its rollouts.
- It is pure Stu, and blind: told nothing about who sits against it, so the `x8.names` question is moot.
- Opponents: 8s-32 (weight 2), 9a-32 (1) and 71s-32 (1). They are the cohort's actors with the same identities: 9a-32 `38b76a8b1542`, 8s-32 `269fdf1854f4`, 71s-32 `7b0f58b4c403`.
- Deals: 4,000 fresh, seed 9021. Exclusions as round 3's.

**Code:** `feature/gen9-genx-stu` at `57d0855f`. The loop's latest is merged in. One conflict, in `gen8_match.py start()`: the loop's deal files kept, with the arena line's bidders.
- Smoke test off the box: 8 boards, 0 failures, about 140 CPU-s a board (round 3's: 131).
- On azure4 the first two boards match the smoke run exactly.

**Feeds:**
- New: `arena-gen9-genx-stu4c-azure4-feed`, manifest `17d6186e...`, registered under Gen 9 as "Gen X Stu (round 4c)".
- Round 3's feed drained at 719 boards and is archived on the dashboard at `d959fd31`.
- Ladder: round 4c has its own entry, parent stu3-ps.

**Round 3's final figures** (699 boards at 16:00): -0.11 ± 0.15 IMPs a board against the three opponents; ladder +0.43 (+0.09 to +0.77).
