d6-arrival slower: floor boards 46.6 CPU-s (est. 33); end about 22:30-23:40 UTC, not 21:00

will, 12 Nov 16:13 UTC. Task G9-D6.

From will, 12 Nov 16:13 UTC.

**`d6-arrival` is slower than my 15:20 estimate.** At 16:12 it had played 1,188 boards: epoch 1's 600 and 588 of epoch 2's 1,200. It has had no restarts. The load is 8.0 on 8 CPUs, and 26 GB of memory is available.

CPU-seconds a board, from the rows' `cpu` field on azure4:

| Epoch | Boards | CPU-seconds a board |
|---|---|---|
| 1 | 600 | 12.9 (`8p-32` self-play) to 24.5 (`9a-32~8p-32`); about 18.8 on average |
| 2, scheduled boards so far | 288 | 11.6 to 27.7 |
| 2, floor `8p-32~guest-a` | 300 | **46.6** |

The floor figure compares with your 33. `9a-32~guest-a`'s 300 floor boards have not started; `9a-32` costs 10 to 18% more than `8p-32` on the same opponents. The box's rate over the last 30 minutes is 585 boards an hour, mostly floor boards.

**New estimate.** Floor boards are 2,700 of the 3,312 boards left: 300 remaining in epoch 2, 600 in epoch 3, and 1,200 in each of epochs 4 and 5. Counting them at 45 to 55 CPU-seconds and the rest at 18.8, there are 6.3 to 7.4 hours left from 16:12. So the run ends at about **22:30 to 23:40 UTC**, not 20:30 to 21:00. That is still well before the 02:00 latest start, and a rerun of the same length would end Friday morning, inside the freeze. E9-0 and the rest of the queue would start about 1.5 to 2 hours later than planned.

guest-b's floor boards (epochs 4 and 5) are not measured. I will report again when `9a-32~guest-a`'s first floor boards are in, at about 16:45.
