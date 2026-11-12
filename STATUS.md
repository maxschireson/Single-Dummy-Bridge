# Fleet status

**Last check:** 12 November 2026, 06:47 UTC. **Next check:** about 07:15 UTC. Who holds which box:
the allocation table in `BOARD.md` on branch `box/coordination`.

**Gen 7.1** (Max, 05:42: push 7.1, policy net v4.1, from 06:00 unless revoked; 7.1 plays 7.0 where
7.0 played itself, for at least 1,000 boards and until a 95% lead, then 7.1 self-play; in every other
match 7 becomes 7.1. 05:54: azure2 plays 7.1 against 7.0 on every board).

| Machine | Held by | Running | At the last check |
| --- | --- | --- | --- |
| `azure1` | Gen 8 session | Gen 8 matches | The operator's phase 1 cohort is stopped for good at 828 boards; 1,986 unplayed deals wait |
| `azure2` | operator | `71s-32~7s-32` on every board, eight workers, cohort `4b32e6ed0d6b`, 1,465 deals v4.1 was not trained on, feed `arena-gen7-1-vs70-fresh-azure2-feed`, since 06:36 | 57 boards in ten minutes, no failures, 23.8 GB of memory available. Tooling `~/work/gen71/gen71c.sh`; `gen71-recycle` active |
| `azure3` | operator | `71s-32~ben64`, eight lanes, 2,933 deals v4.1 was not trained on, feeds `arena-gen7-1-fresh-azure3-ben64-1-feed` to `-8-feed`, since 06:42 | 27 boards in the first four minutes, no failures; `lane-recycle` active. Tooling `~/work/lanes/lane71f.sh` |
| `azure4` | Gen 8 session | Gen 8 matches | Phase 1 cohort stopped for good at 829 boards; 1,985 unplayed deals wait |
| `azure5` (Bridgebots5) | policy 4.1 session, then Gen 8 (about 07:40) | Training | Kept (Max, 05:59) |
| `azure6` (Bridgebots6) | Gen 8 session | Gen 8 experiments | Kept (Max, 06:03) |

**Deals v4.1 was trained on.** The Azure pools are shards of capsule `a76a39f13d9d`, the independent
collector's Gen 6 self-play cohort, copied at 725 boards; it went on to about 9,884 boards before
v4.1 was trained, in the order the shards follow. So the front of every Azure pool is in the
independent collector's list of v4.1 training families (`all-training-families.json` on
`arena-gen71-independent-feed`, 32,205 families, sha256 `4818856d731bee23...`; a copy is at
`~/work/gen71/all-training-families.json` on azure2 and azure3). The Azure 7.1 cohorts started at
06:06 played only such deals and were closed between 06:32 and 06:39: `71s-32~7s-32` 165 boards,
+0.00 +- 0.24; `71s-32~6-32` 3 boards; `71s-32~ben64` 225 boards, -0.14 +- 0.27. They are not
evidence for 7.1 and are not on the dashboard. **Any new 7.1 cohort is prepared with
`--exclude-families` and that list** (source `codex/gen71-independent-20261112` at `a588e09`,
checkout `~/work/sdb-gen71x`). The unplayed pools on azure1 and azure4 have the same front.

**The rule for `71s-32~7s-32`.** The independent collector's gate script (`ops/check_gen71_gate.py`,
run from `/home/claude/watch/gate.sh` on azure2 at every check) counts one board a family over
every registered feed, none on a training family: at 06:47, 177 boards, mean -0.169, 95% interval
-0.547 to +0.208, not eligible. `pool4.py` prints the raw counts. When it is met,
`configs/round71-selfplay.json` is opened. The Gen 8 session's own fork-free match of the two bots
stood at -0.008 +- 0.065 after 1,649 boards at 06:12.

**Gen 7.1 on deals v4.1 was not trained on, all collectors, raw, 06:46:** `71s-32~7s-32` 153 boards,
-0.08 +- 0.20; `71s-32~6-32` 49, +0.59 +- 0.46; `71s-32~ben64` 49, +0.96 +- 0.65; `71s-32~ben` 22,
-0.50 +- 0.96.

**Gen 7.0, all collectors, final, raw:** `7s-32~ben` 1,274 boards, +0.09 +- 0.12 IMPs a board;
`7s-32~ben64` 684, +0.07 +- 0.15; `7s-32~6-32` 1,578, +0.28 +- 0.08; `7s-32~5RZ32` 1,319,
+1.14 +- 0.11; `7s-32~1` 1,319, +2.24 +- 0.12.

**Finished on Azure, all published, nothing deleted.** Gen 7.0 against BEN (16): 1,195 boards.
Against BEN (64): 606. Phase 1 without BEN: 2,985. 7.0 self-play trials on `azure2`: 4 and 11. The
closed 7.1 cohorts above: 8, 160 and 225 boards.

**Memory.** A BEN lane's collector grows by about 24 MB a board; `lane-recycle` on `azure3` restarts
a lane gracefully at 1.9 GB (`~/work/lanes/RECYCLE_OFF` switches it off). The eight workers of the
7.1 against 7.0 cohort on `azure2` grow by 40 to 55 MB a board in their heap (cause not found);
`gen71-recycle` restarts the collector gracefully when the box has under 5 GB available
(`~/work/gen71/RECYCLE_OFF` switches it off). Write the OFF file before stopping for good.

**Unattended upgrades.** Ubuntu's daily upgrade restarts running units through needrestart (the
policy 4.1 session saw it on azure5). All four boxes are set to list-only
(`/etc/needrestart/conf.d/50-list-only.conf`).

**Dashboard.** `gh-pages` `7c69d94`: the nine Azure 7.1 feeds on untrained deals are registered; the
ten feeds of the closed 06:06 cohorts are not (their commits are under
`gen71_azure.closed_in_sample`).
