# Gen 7 policy net v0 (11 November 2026)

**Status: research prototype. No arena bot uses it.** Read
[docs/gen7_prototype_2026-11-11.md](../../../docs/gen7_prototype_2026-11-11.md) first.

258,434 parameters. From one seat's view (its hand, dummy, the play so far, the auction) it gives:

- **policy**: the probability of each legal card being the one Gen 6 plays there;
- **gap**: Gen 6's estimated tricks given up by each legal card;
- **owner**: which hidden seat holds each unseen card;
- **tricks**: the deciding side's final tricks.

Only the policy head is used by `bridge_harness/gen7.py`.

The auction reaches the net as the raw calls and as what the hand-fit scorer
(`models/cardplay/hand-fit-scorer-v0-2026-11-11`, SHA-256 in `manifest.json`) says each seat's calls
show. The net must be run with that scorer; the bank of random hands used for that reading is stored
inside the weights file.

Trained 2 epochs (best of 3 by held-out log-loss, about a minute on two cores) on 519,094 Gen 6
decisions from 3,355 deals published by the three Gen 6 feeds up to about 05:45 UTC on
11 November. 398 deals were held out for validation and 406 for test, split by deal family.

Test deals (60,010 decisions):

| | |
| --- | --- |
| Log-loss on Gen 6's card | 0.920 (uniform over legal cards 1.270; 0.758 if it knew Gen 6's equal-best set and split evenly) |
| Plays Gen 6's exact card | 61.0% |
| Plays one of Gen 6's equal-best cards | 83.1% |
| Tricks given up per decision, by Gen 6's estimates | 0.080 (random legal card 0.200) |
| A Gen 6 equal-best card is in its top 2 / top 3 | 93.7% / 97.3% |

Run `python restore.py` here to rebuild `gen7_policy_v0.npz` from its parts (the repository ignores
`*.npz`). Load it with `bridge_harness.gen7_net.PolicyNet(path, FitScorer(scorer_path))`.
`metrics.json` is the training report, including the auction-use test.

Rebuild: `scripts/gen7_build_dataset.py` then `scripts/train_gen7_policy.py --kind suit --width 256 --epochs 3`.
Training needs `jax` and `optax`; inference is NumPy only.
