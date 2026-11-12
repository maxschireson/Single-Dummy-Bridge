# Fleet status

**Last check:** 12 November 2026, 02:58 UTC. **Next check:** about 03:20 UTC.

| Machine | Running | Since | Notes |
| --- | --- | --- | --- |
| `azure1` | E1: Gen 7 phase 1 collector, shard 0/8 of the capture-feed capsule (2,814 deals), 8 workers | 02:52 | Feed `arena-gen7-phase1-azure1-feed`; 25 boards at 02:55, no failures |
| `azure2` | E1 starting (prepare and preflight for shard 1/8); E0 still playing until then | 02:54 | Feed will be `arena-gen7-phase1-azure2-feed` |
| `azure3` | E1 starting (shard 2/8); E0 still playing until then | 02:54 | Feed will be `arena-gen7-phase1-azure3-feed` |
| `azure4` | E1 starting (shard 3/8); E0 still playing until then | 02:54 | Feed will be `arena-gen7-phase1-azure4-feed` |

**Free now:** nothing. **Free next:** all four at about 04:45, when E1's pairs reach 2,000 boards.

**Shards.** These machines hold shards 0 to 3 of 8 of the `arena-gen6-gen7-capture-feed` capsule at
`8833c62`. Any other collector preparing from that capsule must use `--shard K/8` with K from 4 to
7, or a source run of its own; with any other split it would play these machines' deals again.

**Not on these machines:** BEN. The two BEN pairs of phase 1 need a collector that has the BEN
servers.
