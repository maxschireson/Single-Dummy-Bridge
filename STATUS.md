# Fleet status

**Last check:** 12 November 2026, 06:12 UTC. **Next check:** about 06:40 UTC. Who holds which box:
the allocation table in `BOARD.md` on branch `box/coordination`.

**Gen 7.1 since 06:06 UTC** (Max, 05:42: push 7.1, policy net v4.1, from 06:00 unless revoked; 7.1
plays 7.0 where 7.0 played itself, for at least 1,000 boards and until a 95% lead, then 7.1
self-play; in every other match 7 becomes 7.1. 05:54: azure2 plays 7.1 against 7.0 on every board).
Source `feature/gen7-selfplay-20261112` at `9f5ec19`; notice `docs/gen71_2026-11-12.md` there.

| Machine | Held by | Running | At the last check |
| --- | --- | --- | --- |
| `azure1` | Gen 8 session | Gen 8 matches | The operator's phase 1 cohort is stopped for good at 828 boards; 1,986 unplayed deals wait |
| `azure2` | operator | `71s-32~7s-32` on every board, eight workers, cohort `7207e693b740`, feed `arena-gen7-1-vs70-azure2-feed` | 29 boards in its first five minutes, no failures, 25 GB of memory free. Tooling `~/work/gen71/gen71b.sh` |
| `azure3` | operator | `71s-32~ben64`, eight lanes, feeds `arena-gen7-1-azure3-ben64-1-feed` to `-8-feed` | 28 boards in the first four minutes, no failures; `lane-recycle` active. Tooling `~/work/lanes/lane71.sh` |
| `azure4` | Gen 8 session | Gen 8 matches | Phase 1 cohort stopped for good at 829 boards; 1,985 unplayed deals wait |
| `azure5` (Bridgebots5) | policy 4.1 session, then Gen 8 | Training | No longer temporary (Max, 05:59); its deletion timer is cancelled |
| `azure6` (Bridgebots6) | Gen 8 session | Gen 8 experiments | Temporary; a timer on `azure1` stops it at 09:55 |

**Finished on Azure, all published, nothing deleted.** Gen 7.0 against BEN (16): 1,195 boards (eight
lanes on `azure2`). Against BEN (64): 606 boards (eight lanes on `azure3`). Phase 1 without BEN: 2,985
boards. 7.0 self-play trial cohorts on `azure2`: 4 and 11 boards. First 7.1 cohort on `azure2` (1:2
mix): 8 boards.

**Gen 7.0, all collectors, final or closing, raw:** `7s-32~ben` 1,274 boards, +0.09 +- 0.12 IMPs a
board; `7s-32~ben64` 684, +0.07 +- 0.15; `7s-32~6-32` 1,572, +0.28 +- 0.08; `7s-32~5RZ32` 1,319,
+1.14 +- 0.11; `7s-32~1` 1,319, +2.24 +- 0.12.

**The rule for `71s-32~7s-32`:** at least 1,000 boards over all collectors and the lower end of a
95% interval for 7.1 above zero; then `configs/round71-selfplay.json` is opened. `pool4.py` prints
it at every check. The Gen 8 session's own match of the two bots stood at +0.001 +- 0.077 after
1,150 boards at 06:07.

**Memory.** A BEN lane's collector grows by about 24 MB a board; `lane-recycle` on `azure3`
restarts a lane gracefully at 1.9 GB. Before stopping lanes for good, write
`~/work/lanes/RECYCLE_OFF`. Whether the eight workers on `azure2` grow is not known yet (0.8 to
0.9 GB each after five minutes).

**Dashboard.** `gh-pages` knows `71s-32` (`03d02fc`), accepts feed branches named `arena-gen71-...`
(`f770be6`), and lists the ten Azure 7.1 feeds (`f2b9e49`).
