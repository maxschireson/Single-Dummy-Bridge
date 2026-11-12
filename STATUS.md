# Fleet status

**Last check:** 12 November 2026, 15:35 UTC. **Next check:** about 16:10 UTC. Who holds which box:
the allocation table in `BOARD.md` on branch `box/coordination`.

**Gen 7.1** (Max, 05:42: push 7.1, policy net v4.1, from 06:00 unless revoked; 7.1 plays 7.0 where
7.0 played itself, for at least 1,000 boards and until a 95% lead, then 7.1 self-play; in every other
match 7 becomes 7.1. 05:54: azure2 plays 7.1 against 7.0 on every board).

| Machine | Held by | Running | At the last check |
| --- | --- | --- | --- |
| `azure1` | operator (Max, 13:52 and 13:56: settings test) | Fork-free settings matches with `gen8_match.py` at `48982f7` (units `match-m1`, `match-m3`, four workers each; seed 7111, 3,000 deals, the same in both): `m1` 7.1 at layout-weight exponent 1.0 against 7.0 as deployed; `m3` 7.1 at 1.0 against 7.0 at 1.0. Results to `transfer/gen71-settings-azure1-20261112` every ten minutes | 775 boards each at 15:17: `m1` +0.178 +- 0.090, `m3` +0.156 +- 0.091 (the bench predicts about +0.03 and 0.00). Running to 3,000 (about 17:40), then back to the 7.1 mix (`gen71-mix2-azure1`, capsule shard 5/8, prepared). The mix cohort `f37d8d826522` is paused at 1,256 of 1,471 |
| `azure2` | plan session from 08:15 (Max's authority) | Plan-level search experiments | Drained at 08:14: cohort `4b32e6ed0d6b` at 745 of 1,465 boards, all published (`67dd0ed`); units disabled, `/mnt/ddscache` empty. Nothing of the operator's is queued there; resume from its 720 unplayed deals when the box comes back |
| `azure3` | operator | `71s-32~ben64`, eight lanes on deals v4.1 was not trained on | Second pool (`gen71fresh2-*`) ends between 15:40 and 16:45; **third pool armed at 15:31**: capsule shard 6/8 (claimed on the board 15:24) through the never-played `gen71-claim6-azure3`, an eighth a lane (`gen71fresh3-azure3-ben64-N`, 1,470 deals, preflights passed), feeds `arena-gen7-1-fresh3-azure3-ben64-N-feed` (register with `/tmp/dashcheck/register_pool3.py`). About 470 an hour, no failures; `lane-recycle` has restarted lanes 61 times. The gate runs here |
| `azure4` | Gen 9 (from 14:58; g8 released it) | Gen 9 job queue | Nothing of the operator's runs or is queued there; its prepared cohort `7cefdbdb7771` (1,468 deals) waits unstarted |
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
