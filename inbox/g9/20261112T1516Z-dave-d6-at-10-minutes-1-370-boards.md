D6 at 10 minutes: 1,370 boards an hour in epoch 1, on the estimate; projected end about 21:00 UTC

dave, 12 Nov 15:16 UTC. Task G9-D6.

From dave, 12 Nov 15:18 UTC. Task G9-D6.

- **Progress.** d6-arrival started on azure4 at 15:04. By 15:14 it had 258 of 6,200 boards, all in epoch 1 (house pairs, no floors), and no item-6 errors.
- **Rate against the estimate.** The queue shows 1,369 boards an hour. The estimate for boards without floors (21 CPU-s each on 8 cores) is 1,371. A board here costs 18.4 CPU-s, against 20.9 for the same kind in rehearsal 2.
- **Projected end.** Floors start in epoch 2 and cost about 38 CPU-s a board with item 6. If azure4 stays 0.88 of this machine's cost, the run takes about 5.8 hours and ends near 21:00 UTC. The queue's 19:35 assumes epoch 1's rate throughout, so it is early. Not known: the cost of floor boards on azure4 until epoch 2 has run.
- **Boards come in runs by pair.** The runner plays one pair's boards at a time, so the results branch fills that way. Epoch 1's schedule is in its manifest: 9 pairs, 10 or 11 units each, the gain pool split evenly because nothing is rated yet.
- **Next.** I check again at epoch 2's floors and report their rate.
