# Fleet status

**Last check:** 12 November 2026, 03:05 UTC. **Next check:** about 03:30 UTC.

| Machine | Running | Since | At the last check |
| --- | --- | --- | --- |
| `azure1` | E1: Gen 7 phase 1 collector, shard 0/8, 8 workers | 02:52 | 221 of 2,814 boards, about 960 an hour, no failures, feed 1 minute behind |
| `azure2` | E1, shard 1/8, 8 workers | 03:02 | 59 boards, no open failures (one startup failure diagnosed and archived, see below) |
| `azure3` | E1, shard 2/8, 8 workers | 02:59 | 104 boards, about 955 an hour, no failures |
| `azure4` | E1, shard 3/8, 8 workers; E2 step 1 (copying feeds) at the lowest priority | 02:59 | 148 boards, about 1,040 an hour, no failures |

**E1 by pair, these four machines, 03:05:** `7s-32~6-32` 178 boards, +0.26 +- 0.23 IMPs a board for
`7s-32`; `7s-32~5RZ32` 176, +1.35 +- 0.32; `7s-32~1` 178, +2.24 +- 0.35. About 4,060 boards an hour
together; 2,000 a pair at about 04:25.

**Free now:** nothing. **Free next:** all four at about 04:25, when E1's pairs reach 2,000 boards
and the collectors are stopped, as the launch steps say.

**Shards.** These machines hold shards 0 to 3 of 8 of the `arena-gen6-gen7-capture-feed` capsule at
`8833c62`. Any other collector preparing from that capsule must use `--shard K/8` with K from 4 to
7, or a source run of its own; with any other split it would play these machines' deals again.

**Not on these machines:** BEN. The two BEN pairs of phase 1 need a collector that has the BEN
servers.

**The startup failure on `azure2`.** A new run's eight workers opened a `dds-cache.sqlite` that did
not exist yet at the same moment, and one got `sqlite3.OperationalError('database is locked')` on
`PRAGMA journal_mode=WAL`. No board was played. The record is in the run's `resolved-failures/`
with its resolution, as earlier launches did, and the unchanged cohort was restarted. It can happen
to any new run; opening the cache once before the workers start would avoid it.
