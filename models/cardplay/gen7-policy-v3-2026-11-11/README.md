# Gen 7 policy net v3 (11 November 2026)

**Status: research prototype. No arena bot uses it.** Read
[docs/gen7_prototype_2026-11-11.md](../../../docs/gen7_prototype_2026-11-11.md) first.

The same design and recipe as [v2](../gen7-policy-v2-2026-11-11/README.md) (828,098 parameters,
`--width 512`), retrained after adding 5,163 boards: the 1,381 that reached the feeds between
10:05 and 10:58 UTC and two thirds of the 5,673 that arrived from then to 15:24 UTC. The other
third (1,891 boards) is in no net's training set. 12,111 training deals (v2: 7,968) and 3,696,408
decisions (v2: 2,042,221). Of the new decisions 11% are from root tables, 56% from tie-fork tables
and 33% from gap-fork tables. Best of 3 epochs by held-out log-loss (epoch 2), about thirteen
minutes on two cores. It needs the hand-fit scorer named in `manifest.json`.

On v0's 406 test deals (60,010 decisions):

| | v2 | v3 |
| --- | --- | --- |
| Log-loss on Gen 6's card | 0.779 | 0.727 |
| Plays Gen 6's exact card | 67.9% | 70.1% |
| Plays one of Gen 6's equal-best cards | 87.2% | 88.1% |
| Tricks given up per decision, by Gen 6's estimates | 0.046 | 0.041 |
| An equal-best card is in its top 2 / top 3 | 95.4% / 98.3% | 95.9% / 98.5% |
| Cards kept until probabilities add to 0.90 | 2.23 | 2.16 |
| Cards kept until probabilities add to 0.98, and an equal-best card kept | 2.98, 99.6% | 2.90, 99.7% |

The step is smaller than the one before: 52% more deals cut tricks given up by 11%, where the same
increase had cut it by 20%. Held-out log-loss was flat from epoch 2 (0.7179) to epoch 3 (0.7186)
while held-out tricks given up still fell (0.041 to 0.039), and the recipe keeps the epoch with the
best log-loss, so part of the flattening may be the recipe or the net's size and not the data.

With another deal's auction in place of the real one v3 gives up 0.044 against 0.041 on its
validation deals, and its agreement with Gen 6's opening lead falls from 53.2% to 42.6%.

Run `python restore.py` here to rebuild `gen7_policy_v3.npz`. Rebuild from data:
`scripts/train_gen7_policy.py --kind suit --width 512 --epochs 3`.
