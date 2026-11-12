# Fleet status

**Last check:** 12 November 2026, 12:55 UTC. **Next check:** about 13:35 UTC. Who holds which box:
the allocation table in `BOARD.md` on branch `box/coordination`.

**Gen 7.1** (Max, 05:42: push 7.1, policy net v4.1, from 06:00 unless revoked; 7.1 plays 7.0 where
7.0 played itself, for at least 1,000 boards and until a 95% lead, then 7.1 self-play; in every other
match 7 becomes 7.1. 05:54: azure2 plays 7.1 against 7.0 on every board).

| Machine | Held by | Running | At the last check |
| --- | --- | --- | --- |
| `azure1` | operator from 11:42 (Max, 11:36 and 11:38) | `71s-32~71s-32` and `71s-32~7s-32`, one board in two each, cohort `f37d8d826522`, 1,471 deals v4.1 was not trained on, feed `arena-gen7-1-mix-azure1-feed` (registered) | 481 boards at 12:52 (241 self-play, 240 against 7.0), about 650 an hour, no failures. Eight workers since 12:35 (the Gen 8 match ended; g8 cut its azure1 queue). `gen71-recycle` active, cache on `/mnt/ddscache`. Tooling `~/work/gen71/gen71d.sh` |
| `azure2` | plan session from 08:15 (Max's authority) | Plan-level search experiments | Drained at 08:14: cohort `4b32e6ed0d6b` at 745 of 1,465 boards, all published (`67dd0ed`); units disabled, `/mnt/ddscache` empty. Nothing of the operator's is queued there; resume from its 720 unplayed deals when the box comes back |
| `azure3` | operator | `71s-32~ben64`, eight lanes on deals v4.1 was not trained on | Lanes 3 and 4 moved to their second pool at 12:42 and 12:44 (`lane-switch`); the other six follow as they finish. 2,836 boards in all at 12:52, about 480 an hour, no failures; `lane-recycle` has restarted lanes 42 times. Pool 2 feeds `arena-gen7-1-fresh2-azure3-ben64-N-feed`, registered as they appear (3 and 4 so far, gh-pages `55a5000`). The gate runs here (`/home/claude/watch/gate3.sh`) |
| `azure4` | Gen 8 session (lent; Max 11:38 and 12:21: until 15:00 at the latest), then Gen 9 | Gen 8 work | Nothing of the operator's runs or is queued there; its prepared cohort `7cefdbdb7771` (1,468 deals) waits unstarted |
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
every registered feed, none on a training family: at 12:53, 3,548 boards, mean -0.050, 95% interval
-0.133 to +0.034, not eligible. Not met at 1,000 boards (07:53: 1,124, -0.072, -0.222 to +0.078); Max told, his call. `pool4.py` prints the raw counts. When it is met,
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
