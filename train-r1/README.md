# Stu, round 1's net (13 November 2026)

`policy.npz`: rollout net v2 (epoch 5) with one bot added, `stu0`, whose two vectors were started from `8s-32`'s and
trained on 759 boards of round 0's Stu (62,504 decisions; `scripts/train_rollout_net.py --only-vectors stu0`, rate
1e-2, epoch 6 of 8). Every other weight is v2's, bit for bit. `metrics.json` is the trainer's file for it;
`metrics_before.json` the same held-out rows (250 later boards of Stu's as bot `stu0`, joined to the plan session's
`freshB.npz` for the other bots) scored before any training. `variants/`: the same rows and held-out set with the whole
net trained at three rates, which learn a little more of Stu and forget some of the other bots.
