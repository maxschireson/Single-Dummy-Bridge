# Gen 7 policy net v4 (11 November 2026)

**Status: research prototype. No arena bot uses it.** Read
[docs/gen7_prototype_2026-11-11.md](../../../docs/gen7_prototype_2026-11-11.md) first.

The same net and recipe as [v3.1](../gen7-policy-v3.1-2026-11-11/README.md) (828,098 parameters,
`--width 512`, three epochs, a fitted temperature) on more boards: 17,207 training deals
(5,826,238 examples) against 12,111. The added boards are the 1,891 that were held back as unseen
for v3.1's tree bench and 4,520 that had reached the feeds by 21:19 UTC.

- **Epoch 3** has both the lowest held-out tricks given up and the lowest held-out log-loss
  (0.0342 and 0.683 on the 700,551 validation decisions of its own split).
- **Temperature 1.201**, fitted on the validation deals of gen7_v2 (112,533 decisions; log-loss
  0.6890 to 0.6809). As in v3.1 the division is inside the file, in the policy columns of the
  decoder's last layer; the gap and owner heads are as trained.

On v0's 406 test deals (60,010 decisions):

| | v3.1 | v4 |
| --- | --- | --- |
| Tricks given up per decision, by Gen 6's estimates | 0.0374 | 0.0333 |
| Plays Gen 6's exact card | 70.5% | 72.0% |
| Log-loss on Gen 6's card | 0.713 | 0.682 |
| An equal-best card is in its top 3 | 98.5% | 98.6% |
| Cards kept until probabilities add to 0.98, and an equal-best card kept | 3.09, 99.8% | 3.02, 99.8% |
| Cards kept until probabilities add to 0.90, and an equal-best card kept | 2.31, 98.8% | 2.25, 98.8% |

v4 gives up 11.1% less than v3.1, 95% interval [5.1%, 16.5%] from 2,000 bootstrap draws of deals,
for 1.42 times the training deals: lead 9% [-10, 25], tricks 1-2 7% [-8, 19], tricks 3-6 8%
[0, 16], tricks 7-13 12% [5, 19]. The step from v2 to v3 was 11% [5, 16] for 1.52 times the deals.

With another deal's auction in place of the real one (validation deals of gen7_v2), v4 gives up
0.037 against 0.035, and its agreement with Gen 6's opening lead falls from 56.1% to 43.0%.

The training set (7,257,481 examples, 5.4 GB as stored) no longer fits the 6 GB the trainer had
here. The trainer now maps the file and holds its whole-number tables at a few bits each (3.3 GB);
the batches are the same (`Packed` in `scripts/train_gen7_policy.py`, tested in
`tests/test_gen7.py`).

Run `python restore.py` here to rebuild `gen7_policy_v4.npz`.
