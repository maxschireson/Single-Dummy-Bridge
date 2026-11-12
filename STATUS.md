# Fleet status

**Last check:** 12 November 2026, 05:23 UTC. **Next check:** about 05:55 UTC. Who holds which box:
the allocation table in `BOARD.md` on branch `box/coordination`.

| Machine | Held by | Running | At the last check |
| --- | --- | --- | --- |
| `azure1` | Gen 8 session, since 03:50 | Gen 8 matches (`~/work/g8`) | The operator's phase 1 cohort `002cbafd32e1` (shard 0/8) is stopped for good at 828 of 2,814 boards; its 1,986 unplayed deals wait for a self-play cohort |
| `azure2` | operator | E1b: `7s-32` against BEN (16), eight lanes, since 03:45. E1c: self-play cohort `c50412d34108`, a nine-board trial with two workers, then stopped until the lanes finish | BEN (16): 579 boards, 490 to 550 an hour, no failures. Self-play cohort: 6 of 2,202 boards. Phase 1 cohort `10772c07d1a7` finished at 608 boards |
| `azure3` | operator | E1b: `7s-32` against BEN (64), eight lanes, since 03:50 | 290 boards, about 310 an hour, no failures. Phase 1 cohort `d75a644daf20` (shard 2/8) stopped for good at 720 boards; 2,094 unplayed deals wait |
| `azure4` | Gen 8 session, since 03:50 | Gen 8 matches | Phase 1 cohort `869ada89eaf3` (shard 3/8) stopped for good at 829 boards; 1,985 unplayed deals wait. `~/work/feeds` holds 13 GB of Gen 6 feed episodes |
| `azure5` (Bridgebots5) | policy 4.1 session | Training Gen 7 policy net 4.1 | Temporary; extended by Max at 05:25; a timer on `azure1` deletes it at 07:35 |
| `azure6` (Bridgebots6) | Gen 8 session | Gen 8 experiments | Temporary; a persistent timer on `azure1` stops it at 09:55 |

**Memory on the BEN boxes, 05:23.** A lane's collector grows by about 24 MB a board in its BEN
worker (cause not found; the BEN servers and the cohorts without BEN do not grow). `azure2` was
down to 3.2 GB free; its eight collectors were restarted the graceful way at 05:24 with no failure.
Both BEN boxes now run the unit `lane-recycle`, which restarts a lane's collector at 1.9 GB, one
lane at a time. Before stopping lanes for good, write `~/work/lanes/RECYCLE_OFF`.

**At 05:23, all collectors, raw:** `7s-32~ben` 894 boards, +0.04 +- 0.14 IMPs a board, about 580 an
hour; `7s-32~ben64` 466, +0.13 +- 0.19, about 300 an hour; `7s-32~6-32` 1,387, +0.25 +- 0.09;
self-play 135 boards. The numbers further down are from 04:52.

**Max, 04:09:** the Gen 5 and Gen 1 pairs stop; their deals go to self-play. **Max, 04:13:** the
operator registered the 16 BEN feeds on the dashboard (`gh-pages` `909b0b0`).

**Phase 1 by pair, all collectors, raw counts, 04:52:** `7s-32~6-32` 1,341 boards, +0.21 +- 0.09
IMPs a board for `7s-32`; `7s-32~ben` 620, -0.11 +- 0.17; `7s-32~ben64` 331, +0.11 +- 0.24.
Stopped: `7s-32~5RZ32` 1,319, +1.14 +- 0.11; `7s-32~1` 1,319, +2.24 +- 0.12. Self-play
(`7s-32~7s-32`, no score): 43 boards, mostly Codex.

**Self-play source.** Branch `feature/gen7-selfplay-20261112`, commit `7780e5e` or later; notice
`docs/gen7_selfplay_2026-11-12.md` there. Box tooling: `~/work/selfplay/selfplay.sh` on `azure2`
(`build`, `tests`, `prepare`, `preflight`, `records`, `units`, `trial N`, `publish`, `start W`,
`status`). A cohort is prepared from the box's drained phase 1 cohort, so it takes exactly the deals
that cohort had not played.

**No gap forks in the Azure records so far.** The launch source `fe382f9` carries the `gap_fork`
setting without acting on it. Phase 1, pre-arena test and BEN lane records have tie and tree audits
only. Cohorts prepared at `7780e5e` record gap forks and the guess-size fields.

**Shards of capsule `8833c62`.** Shards 0 to 3 of 8 belong to `azure1` to `azure4`. The BEN lanes
use sub-shards of the same deals in the BEN matchups: of 32, numbers 0, 8, 16, 24, 2, 10, 18 and 26
for BEN (16) on `azure2`, and 1, 9, 17, 25, 3, 11, 19 and 27 for BEN (64) on `azure3`. Shard 4/8
belongs to the cloud collector. Shards 5 to 7 are unclaimed.

**BEN lanes.** One lane is one cohort with its own BEN server, collector, publisher and feed
(`arena-gen7-phase1-azure2-ben16-1-feed` to `-8-feed`, `arena-gen7-phase1-azure3-ben64-1-feed` to
`-8-feed`), because the runtime plays BEN boards with a single worker. Tooling on the box:
`~/work/lanes/lane.sh`.
