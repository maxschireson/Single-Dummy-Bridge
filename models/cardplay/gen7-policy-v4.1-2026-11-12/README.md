# Gen 7 policy net v4.1 (12 November 2026)

**Status: research prototype. No arena bot uses it.** How it was made, and the scripts:
[training/policy-v4.1-20261112](../../../training/policy-v4.1-20261112/README.md). Background:
[docs/gen7_prototype_2026-11-11.md](../../../docs/gen7_prototype_2026-11-11.md).

The same net and recipe as [v4](../gen7-policy-v4-2026-11-11/README.md) (828,098 parameters,
`--width 512`, three epochs, a fitted temperature) on every board that was on the feeds at 03:59 UTC
on 12 November: 38,128 boards with searched decisions (34,029 distinct deals), 13,239,367 examples,
against v4's 17,207 training deals and 5,826,238 examples.

**No deal is held back** (Max, 12 November, 03:54 UTC: new boards arrive fast enough to test on).
The deals that the family hash marks as validation and test are trained on like the rest, so
**v4.1 must not be scored on any set's split 1 or 2 built from boards fetched before 03:59 UTC**.
Its held-out figures come from boards that reached the feeds afterwards, with every deal the
training set has removed:

| Set | Boards arrived (UTC) | Boards | Decisions | Used for |
| --- | --- | --- | --- | --- |
| B | about 03:59 to 04:28 | 631 | 218,537 | Epoch scores, the temperature |
| C | about 04:28 to 05:00 | 450 | 180,315 | The comparison below; no choice was made on it |

On B 72% of the decisions are 6-32's and 28% are `7s-32`'s (Gen 7 standard, which plays with v4
inside it); on C 84% and 16%.

What went in: 32,920 boards from the `arena-gen6-*` feeds, 3,650 from the Gen 7 phase 1 feeds and
1,637 from the pre-7 test (38,207 episodes; 79 had no searched decision). Gen 7's decisions are
included as played (Max, 03:32 UTC): there the policy target is Gen 7's card and the gap target the
search's estimates.

- **Epoch 3** has the lowest held-out tricks given up and the lowest held-out log-loss (0.0245 and
  0.6062 on B).
- **Temperature 1.074**, fitted on B (log-loss 0.6062 to 0.6051). As in v3.1 and v4 the division is
  inside the file, in the policy columns of the decoder's last layer. v4 needed 1.201.

## Against v4 and v3.1, on set C

| | v3.1 | v4 | v4.1 |
| --- | --- | --- | --- |
| Tricks given up per decision, by Gen 6's estimates | 0.0388 | 0.0340 | 0.0256 |
| Plays the exact card that was played | 71.6% | 74.7% | 75.0% |
| Log-loss on that card | 0.690 | 0.650 | 0.608 |
| An equal-best card is in its top 3 | 98.7% | 98.9% | 99.0% |
| Cards kept until probabilities add to 0.98 | 3.01 | 2.95 | 2.74 |
| Cards kept until probabilities add to 0.90 | 2.27 | 2.21 | 2.04 |

v4.1 gives up 24.8% less than v4, 95% interval [21.3%, 28.1%] from 2,000 bootstrap draws of deals,
for 2.2 times the training deals: lead 5% [-13, 22], tricks 1-2 16% [6, 26], tricks 3-6 18%
[13, 23], tricks 7-13 28% [23, 32]. On the same boards v4 gives up 12.4% [8.7, 16.0] less than v3.1.
As an exponent on training deals this step is -0.36 [-0.41, -0.30] and that one -0.38
[-0.50, -0.26]: no sign of the curve flattening. On set B the step is 25.4% [22.3, 28.2].

On the three fresh sets fetched after C as well (C, D and E together: 1,243 boards, 525,562
decisions, none in the training set) v4.1 gives up 0.0247 against v4's 0.0334: 25.9% less
[23.7%, 28.0%].

By who decided, on set C (v4, then v4.1):

| Decisions | Tricks given up | Exact card | Log-loss |
| --- | --- | --- | --- |
| 6-32's (151,309) | 0.0344, 0.0256 | 72.1%, 74.4% | 0.675, 0.620 |
| `7s-32`'s (29,006) | 0.0320, 0.0254 | 88.1%, 78.5% | 0.519, 0.549 |

Gen 7 chose its cards with v4 (tie-breaks, play weights, the tree's replies), so v4 predicts
Gen 7's card better than any other net can; tricks given up does not have that bias.

Heads, on set C (`scripts/gen7_head_eval.py`):

| Card chosen by | v4 gives up | v4.1 gives up |
| --- | --- | --- |
| Policy head | 0.0340 | 0.0256 |
| Gap head | 0.0265 | 0.0216 |
| Policy - 10 x gap | 0.0270 | 0.0213 |

With the tree's reply rule (cards until probabilities add to 0.9, at most two) v4.1 keeps 1.66
cards, an equal-best card among them at 96.9% of decisions and the card played at 92.0% (v4: 1.73,
96.4%, 91.5%).

## Epochs

Held-out figures on set B; v4's own run for comparison was scored on its validation deals, so only
the last row compares like with like.

| Epoch | Seconds | Training loss (card) | Tricks given up | Exact card | Log-loss | Gap head's card gives up |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 570 | 0.719 | 0.0303 | 73.0% | 0.660 | 0.0263 |
| 2 | 1,170 | 0.618 | 0.0272 | 74.8% | 0.620 | 0.0223 |
| 3 | 1,773 | 0.572 | 0.0245 | 75.5% | 0.606 | 0.0203 |
| v4 (finished) on B | | | 0.0328 | 76.5% | 0.635 | 0.0260 |

The third epoch still cut tricks given up by a tenth (9.9% [7.6, 12.2] on B, 9.0% [6.6, 11.4] on C).

## The auction

With another deal's auction in place of the real one (set B), v4.1 gives up 0.0288 against 0.0245,
and its agreement with the opening lead played falls from 55.3% to 45.3%. With the auction inputs
blanked it gives up 0.0510.

## At the table (added 12 November, 07:45 UTC)

Measured by the Gen 8 session in fork-free matches on fresh deals (box/coordination, 06:48 UTC):
played alone, v4.1 beats v4 by 0.762 +- 0.074 IMPs a board (4,000 boards); inside `7s-32` the same
swap is worth -0.010 +- 0.047 (3,075 boards). The net is in the arena as Gen 7.1 (`71s-32`) since
06:06 UTC. The training folder's README has the offline side: the tree bench, the layout weights,
the choice among near-tied cards.

## Not done

- Sets B and C are small next to the earlier validation sets (700,551 decisions for v4), and their
  boards are the arena's mix at the time: Gen 6 self-play and Gen 7 phase 1.

Run `python restore.py` here to rebuild `gen7_policy_v4.1.npz`.
