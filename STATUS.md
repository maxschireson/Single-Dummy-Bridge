# Fleet status

**Last check:** 12 November 2026, 21:47 UTC. Who holds which box: the allocation table in `BOARD.md` on branch
`box/coordination`. Fleet check: `/home/claude/watch/pool8.py` (per-box `box8.sh`).

**Gen 8 arena** (Max, 15:32 "Go ahead", 15:33, 15:50: never a board in a family the bot was trained on; 16:11 to the
operator: switch the arena to Gen 8, 7.1 stays as the representative of the 7 family). Source
`feature/gen8-prototype-20261112` at `792c4cb`; notice `docs/gen8_candidate_2026-11-12.md` there. Every cohort is
prepared with `--exclude-families` and the union of the two lists of v4.1 training families (34,092 families,
sha256 `0b8ac2b7f41b9191...`, branch `transfer/v41-training-families-union-20261112`).

| Machine | Held by | Running | At the last check |
| --- | --- | --- | --- |
| `azure1` | operator | `configs/round8-candidate.json`, eight workers. `gen8-azure1` (`b9900c30105c`) finished at 1,097 of 1,097 at 20:26; since then `gen8-s3-azure1` (`05729bda9553`, 1,468 deals: azure4's phase 1 cohort's remaining deals), feed `arena-gen8-s3-azure1-feed`. Armed next (`next8`): `gen8-s7-azure1` (`22b58cd811cc`, 1,074 deals: azure6's drained Gen 8 cohort's remaining deals, preflight passed 20:56), feed `arena-gen8-s7-azure1-feed` | 400 of 1,468 at 21:47, about 300 boards an hour: `s7` from about 01:20, to about 05:00. Still to prepare after it: azure2's `4b32e6ed0d6b` (720) and `gen71-mix-azure1` (215), to about 08:10 |
| `azure2` | plan session (Max's authority) | Plan-level search experiments | Nothing of the operator's runs there |
| `azure3` | operator | `8s-32~ben64`, eight lanes. Second pool (`gen8-p2-azure3-ben64-N`, 2,946 deals: azure2's phase 1 BEN (16) lanes' remaining deals), feeds `arena-gen8-p2-azure3-ben64-N-feed`; `lane-switch` moved lanes 3, 4, 5, 2, 7 and 1 between 20:55 and 21:46 | Lanes 6 and 8 at 178 and 180 of their first pools (184, 183); second pools about 34 boards an hour a lane, to about 08:30 |
| `azure4` | Gen 9 | Gen 9 job queue | The phase 1 publisher of `arena-gen7-phase1-azure4-feed` still pushes there (g8's, to g9) |
| `azure5` | plan session | | |
| `azure6` | the single-dummy lookup-table session (Max, 18:07) | | Freed by the operator at 18:12: `gen8-azure6` drained at 410 of 1,484, all published; its remaining deals go to azure1 as `s7` |

**Finished at the switch (all published, nothing deleted).** azure1 `gen71-mix2-azure1` (`71s-32~71s-32` and
`71s-32~7s-32`) at 381 boards (16:22). azure3's 7.1 BEN (64) lanes at 16:30: third pool lanes 1 to 5 and 7 at 9, 11,
40, 37, 7 and 1 boards; lanes 6 and 8 (second pool) at 172 and 167.

**BEN (16):** no Azure box runs its servers; `8s-32~ben` was asked of the independent collector (board, 16:24).

## Gen 7.1 (to 16:30 UTC)

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
every registered feed, none on a training family: at 15:18, 4,888 boards, mean -0.070, 95% interval
-0.143 to +0.004, not eligible (below zero once, at 14:29; Max told). Not met at 1,000 boards (07:53: 1,124, -0.072, -0.222 to +0.078); Max told, his call. `pool4.py` prints the raw counts. When it is met,
`configs/round71-selfplay.json` is opened. The Gen 8 session's own fork-free match of the two bots
stood at -0.010 +- 0.047 after 3,075 boards (plan session's 07:15 entry).

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

**Throughput (07:13 to 07:25).** A `71s-32~7s-32` board costs 48 cpu-s: base 18, tie audits 9, gap forks 21. Phase 1
boards cost 20 to 25 (no gap forks then) and ran about 960 an hour on azure2. Before 07:20 the shared solver cache
(`dds_cache.py`: WAL, `synchronous=FULL`, one write lock for eight processes) kept a third of azure2's CPU idle; the
cache now sits on `/mnt/ddscache` (tmpfs, in fstab) through a symlink at the run's `dds-cache.sqlite`, and
`gen71-recycle` empties it at each restart. Asked of Max: keep gap forks on the comparison cohort or drop them
(about 1.8 times the boards).
