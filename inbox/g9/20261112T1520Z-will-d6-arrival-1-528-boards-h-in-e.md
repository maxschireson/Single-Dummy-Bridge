d6-arrival: 1,528 boards/h in epoch 1 (18.8 CPU-s a board, 11% under your 21); finish about 20:30-21:00 with the floor mix

will, 12 Nov 15:20 UTC. Task G9-D6.

From will, 12 Nov 15:20 UTC.

**`d6-arrival` on azure4, 15 minutes in.** At 15:19 it had 396 of 6,200 boards, all in epoch 1. It started at 15:04 with startup included, and has had no restarts. The box measures 1,528 boards an hour, which is 18.8 CPU-seconds a board at 8 workers. For epoch 1, which has no floor boards, your estimate of 21 CPU-seconds gives 1,370 an hour. So the box runs about 11% faster than the estimate.

**Expected finish.** The box's own ETA of 19:07 assumes epoch 1's rate throughout. Floor boards are slower and make up half of epochs 2 and 3 and three quarters of epochs 4 and 5 (600, 600, 1,200, 1,200 of 1,200, 1,200, 1,600, 1,600). Counting floor boards at 33 CPU-seconds and the rest at 21:
- The run comes to 173,400 CPU-seconds, about 6.0 hours on 8 cores.
- Scaled by epoch 1's measured speed, it comes to 5.4 hours, with about 5.1 hours left at 15:19.

That puts the end at about **20:30 UTC**, plus the epoch boundaries (arrivals, snapshots) and the replay. My estimate is 20:30 to 21:00, which fits before 21:30. Whether floor boards keep the same 11% is not measured yet. I will check again early in epoch 2, which should start at about 15:30.

Partial results are on `transfer/gen9-d6-arrival-azure4-20261112`, updated every 10 minutes.
