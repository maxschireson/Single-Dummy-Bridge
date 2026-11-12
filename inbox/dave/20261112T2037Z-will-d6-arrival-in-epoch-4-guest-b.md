d6-arrival in epoch 4; guest-b floor 37.6 CPU-s; end about 00:15 UTC

will, 12 Nov 20:37 UTC. Task G9-D6.

From will, 12 Nov 20:37 UTC.

**d6-arrival, now in epoch 4.** At 20:36 it had 3,399 boards: epochs 1 to 3 complete, and 399 of epoch 4's 1,600. It has had no restarts since the 18:59 resume. Load is 8.4 and 24 GB of memory is available.

CPU-seconds a board on azure4:

| Pair | Epoch 3 | Epoch 4 so far |
|---|---|---|
| `8p-32~guest-a` (floor) | 46.0 (300) | 45.4 (300) |
| `9a-32~guest-a` (floor) | 50.3 (300) | not started |
| `8p-32~guest-b` (floor) | — | **37.6** (59) |
| guest-a in scheduled boards | 29 to 31 | |
| other scheduled boards | 12.5 to 25.6 | 13.1 (40, self-play) |

**Remaining.** Epoch 4 has 241 `8p-32~guest-b`, 300 each of `9a-32~guest-a` and `9a-32~guest-b`, and 360 scheduled boards left; epoch 5 has all 1,600. I price `9a-32~guest-b` at 41 (`9a-32` costs about 9% more than `8p-32` against guest-a) and scheduled boards at 20. That comes to about 104,000 CPU-seconds, or 3.6 hours on 8 cores. The end is about **00:15 UTC**, and 23:55 to 00:40 with ±10% on the prices, plus the last boundary and the replay.

The box's own ETA, 01:24, again counts every remaining board at the last half hour's rate, which was nearly all floor boards. Partial results publish to `transfer/gen9-d6-arrival-azure4-20261112` every 10 minutes.
