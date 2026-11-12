# Fleet status

**Last check:** 12 November 2026, 04:04 UTC. **Next check:** about 04:25 UTC. Who holds which box:
the allocation table in `BOARD.md` on branch `box/coordination`.

| Machine | Held by | Running | At the last check |
| --- | --- | --- | --- |
| `azure1` | Gen 8 session, since 03:50 | Gen 8 matches (`~/work/g8`, unit `g8-queue`) | The operator's phase 1 cohort `002cbafd32e1` (shard 0/8) was drained at 03:50 with 828 of 2,814 boards, no failures, feed complete |
| `azure2` | operator | E1b: `7s-32` against BEN (16), eight lanes, since 03:45 | 131 boards published, about 550 an hour, no failures, records show 16 play samples. Its non-BEN cohort `10772c07d1a7` (shard 1/8) stopped at 608 boards, feed complete |
| `azure3` | operator | E1b: `7s-32` against BEN (64), eight lanes, since 03:50 | 53 boards published, 250 to 310 an hour in the first ten minutes, no failures, records show 64 play samples. Its non-BEN cohort `d75a644daf20` (shard 2/8) stopped at 720 boards, feed complete |
| `azure4` | Gen 8 session, since 03:50 | Gen 8 matches | The operator's phase 1 cohort `869ada89eaf3` (shard 3/8) was drained at 03:50 with 829 of 2,814 boards, no failures, feed complete. `~/work/feeds` holds 13 GB of Gen 6 feed episodes |
| `azure5` (Bridgebots5) | policy 4.1 session | Training Gen 7 policy net 4.1 | Temporary; a timer on `azure1` deletes it at 05:42 |
| `azure6` (Bridgebots6) | Gen 8 session | Gen 8 experiments | Temporary; a timer on `azure1` deallocates it at 10:03 |

**Phase 1 by pair, all collectors, raw counts, 03:54:** `7s-32~6-32` 1,153 boards, +0.22 +- 0.10
IMPs a board for `7s-32`; `7s-32~5RZ32` 1,154, +1.10 +- 0.12; `7s-32~1` 1,151, +2.21 +- 0.13;
`7s-32~ben` 85; `7s-32~ben64` 29. No Azure box plays the three pairs without BEN now. The other
collectors add about 200 to 235 boards an hour to each, so 2,000 raw boards between about 07:30 and
08:15.

**Shards of capsule `8833c62`.** Shards 0 to 3 of 8 belong to `azure1` to `azure4`, played and
unplayed deals alike. The BEN lanes use sub-shards of the same deals: of 32, numbers 0, 8, 16, 24,
2, 10, 18 and 26 for BEN (16) on `azure2`, and 1, 9, 17, 25, 3, 11, 19 and 27 for BEN (64) on
`azure3`. Shard 4/8 belongs to the cloud collector. Shards 5 to 7 are unclaimed.

**BEN lanes.** One lane is one cohort with its own BEN server, collector, publisher and feed
(`arena-gen7-phase1-azure2-ben16-1-feed` to `-8-feed`, `arena-gen7-phase1-azure3-ben64-1-feed` to
`-8-feed`), because the runtime plays BEN boards with a single worker. Tooling on the box:
`~/work/lanes/lane.sh`. The BEN (16) preflight used the stock `smoke()` with its exclusion of the
pair id `ben` removed; each `preflight.json` says so.

**Earlier incident, `azure2`, 03:02.** Eight workers of a new run opened a `dds-cache.sqlite` that
did not exist yet at the same moment and one got `database is locked`. No board was played; the
record is in that run's `resolved-failures/`.
