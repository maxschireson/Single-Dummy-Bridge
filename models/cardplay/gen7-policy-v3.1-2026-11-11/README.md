# Gen 7 policy net v3.1 (11 November 2026)

**Status: research prototype. No arena bot uses it.** Read
[docs/gen7_prototype_2026-11-11.md](../../../docs/gen7_prototype_2026-11-11.md) first.

The same net, data and recipe as [v3](../gen7-policy-v3-2026-11-11/README.md) (828,098
parameters, `--width 512`, 12,111 training deals), with two changes:

- **Epoch 3, not epoch 2.** The recipe keeps the epoch with the best held-out log-loss, which was
  epoch 2 (v3). Held-out tricks given up still fell at epoch 3 (0.0408 to 0.0387 on 433,774
  validation decisions), so this release takes epoch 3 (`--save-epochs`).
- **A fitted temperature.** Epoch 3 is overconfident. Its policy logits are divided by 1.246,
  the value that minimises log-loss on held-out validation deals (112,533 decisions; 0.7215 to
  0.7085). The division is inside the file, in the policy columns of the decoder's last layer, so
  the most probable card is unchanged. The gap and owner heads are as trained.
  (`scripts/gen7_fit_temperature.py`.)

On v0's 406 test deals (60,010 decisions):

| | v3 | v3.1 |
| --- | --- | --- |
| Tricks given up per decision, by Gen 6's estimates | 0.0406 | 0.0374 |
| Plays Gen 6's exact card | 70.1% | 70.5% |
| Log-loss on Gen 6's card | 0.727 | 0.713 |
| An equal-best card is in its top 3 | 98.5% | 98.5% |
| Cards kept until probabilities add to 0.98, and an equal-best card kept | 2.90, 99.7% | 3.09, 99.8% |
| Cards kept until probabilities add to 0.90, and an equal-best card kept | 2.16, 98.4% | 2.31, 98.8% |

v3.1 gives up 7.8% less than v3, 95% interval [4.6%, 11.0%] from 2,000 bootstrap draws of deals:
lead 14% [3, 24], tricks 1-2 13% [3, 23], tricks 3-6 3% [-2, 9], tricks 7-13 9% [5, 12]. Its
cards-kept figures are larger than v3's because v3 is overconfident too (its own fitted temperature
is 1.17; calibrated it keeps 3.12 and 2.34 cards).

A 768-wide net on the same data, also at epoch 3 with its own temperature, is level with v3.1
(-0.2%, [-6.3%, 5.6%]).

With another deal's auction in place of the real one (validation deals of gen7_v2), v3.1 gives up
0.043 against 0.038, and its agreement with Gen 6's opening lead falls from 53.9% to 43.1%.

Run `python restore.py` here to rebuild `gen7_policy_v3.1.npz`.
