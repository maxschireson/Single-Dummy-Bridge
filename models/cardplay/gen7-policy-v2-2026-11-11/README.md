# Gen 7 policy net v2 (11 November 2026)

**Status: research prototype. No arena bot uses it.** Read
[docs/gen7_prototype_2026-11-11.md](../../../docs/gen7_prototype_2026-11-11.md) first.

The same design and recipe as [v1](../gen7-policy-v1-2026-11-11/README.md) (828,098 parameters,
`--width 512`), retrained after adding the 3,396 boards that reached the feeds by 10:05 UTC: the
three fast self-play feeds (2,237), the two v7-capture feeds (665), the chatgpt feed (386) and the
extra self-play feed (108). 7,968 training deals (v1: 5,240) and 2,042,221 decisions (v1:
1,003,622). Of the new decisions 12% are from root tables, 51% from tie-fork tables and 37% from
gap-fork tables. Best of 3 epochs by held-out log-loss (epoch 2), about eight minutes on two
cores. It needs the hand-fit scorer named in `manifest.json`, as v0 and v1 do.

On v0's 406 test deals (60,010 decisions):

| | v1 | v2 |
| --- | --- | --- |
| Log-loss on Gen 6's card | 0.830 | 0.779 |
| Plays Gen 6's exact card | 65.2% | 67.9% |
| Plays one of Gen 6's equal-best cards | 85.6% | 87.2% |
| Tricks given up per decision, by Gen 6's estimates | 0.057 | 0.046 |
| An equal-best card is in its top 2 / top 3 | 94.9% / 98.0% | 95.4% / 98.3% |
| Cards kept until probabilities add to 0.90 | 2.35 | 2.23 |
| Cards kept until probabilities add to 0.98, and an equal-best card kept | 3.14, 99.7% | 2.98, 99.6% |

On the 341 test deals of the new boards (126,864 decisions) v2 gives up 0.049 tricks per decision
and v1 0.057.

With another deal's auction in place of the real one v2 gives up 0.051 against 0.048 on its
validation deals, and its agreement with Gen 6's opening lead falls from 52.7% to 40.0%.

Not yet measured for v2: its distance from a 128-layout search (v1: 0.063 tricks a decision from
trick 3 on, where a fresh 6-32 search is at 0.0006), and its worth as the tree's reply model.

Run `python restore.py` here to rebuild `gen7_policy_v2.npz`. Rebuild from data:
`scripts/train_gen7_policy.py --kind suit --width 512 --epochs 3`.
