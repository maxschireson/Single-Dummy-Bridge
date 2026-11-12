# Gen 7 policy net v1 (11 November 2026)

**Status: research prototype. No arena bot uses it.** Read
[docs/gen7_prototype_2026-11-11.md](../../../docs/gen7_prototype_2026-11-11.md) first.

The same design and recipe as [v0](../gen7-policy-v0-2026-11-11/README.md), wider (828,098
parameters, `--width 512`) and retrained after adding 2,325 boards that reached the feeds by
07:30 UTC: the two v7-capture feeds with their gap forks, the chatgpt feed, the two Gen 6 against
BEN feeds and the independent feed. 5,240 training deals (v0: 3,355) and 1,003,622 decisions (v0:
519,094). Best of 3 epochs by held-out log-loss (epoch 2), about four minutes on two cores. It
needs the hand-fit scorer named in `manifest.json`, as v0 does.

On v0's 406 test deals (60,010 decisions):

| | v0 | v1 |
| --- | --- | --- |
| Log-loss on Gen 6's card | 0.920 | 0.830 |
| Plays Gen 6's exact card | 61.0% | 65.2% |
| Plays one of Gen 6's equal-best cards | 83.1% | 85.6% |
| Tricks given up per decision, by Gen 6's estimates | 0.080 | 0.057 |
| An equal-best card is in its top 2 / top 3 | 93.7% / 97.3% | 94.9% / 98.0% |
| Cards kept until probabilities add to 0.98, and an equal-best card kept | 3.42, 99.7% | 3.14, 99.7% |

On the 222 test deals of the new boards (56,129 decisions, 24,768 of them in gap-fork tables) v1
gives up 0.056 tricks per decision and v0 0.077.

Width: with 3,355 deals the 258,434 and 828,098 parameter nets scored the same. With 5,240 the
wider one is better (the narrow one retrained on the same data: 0.062 tricks given up, 63.8% exact
card). It is about four times slower to evaluate.

Every check in the document was run with v0. Run `python restore.py` here to rebuild
`gen7_policy_v1.npz`. Rebuild from data: `scripts/train_gen7_policy.py --kind suit --width 512 --epochs 3`.
