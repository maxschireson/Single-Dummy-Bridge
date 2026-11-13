# Gen 7 prototype (11 November 2026)

> On `feature/gen7-alpha-20261111` and `feature/gen7-candidate-20261111` the player consults the tree and
> the runtime knows the `gen7` engine: see [Gen 7 alpha](gen7_alpha_2026-11-11.md) and
> [the candidate notice](gen7_candidate_2026-11-11.md). The lines below saying that nothing was run
> through the collectors, and that the ops files need teaching the engine, describe the prototype
> branch this write-up came from. This copy is the write-up as of `transfer/gen7-prototype-20261111`
> at `3482198`; the analysis scripts its later sections name (`gen7_sweep.py`, `gen7_match_forks.py`,
> `gen7_board_cost.py`, `gen7_head_eval.py`, `gen7_stake_breadth.py`) and the trainer changes are on
> that branch, not this one.

**Status: prototype. Not an arena bot, and not recommended as one yet.** Branch
`transfer/gen7-prototype-20261111`, cut from `transfer/gen7-capture-forks-20261111`. Nothing here
changes Gen 6 or the collectors.

What this is: a policy net trained to predict Gen 6's card from one seat's view, a player that is
the Gen 6 search reading that net, and the measurements that say what the net is and is not good
for today. The measurements point at the next build (a short tree search over the net's top few
cards), which is not in this branch.

## What was built

| File | What it is |
| --- | --- |
| `bridge_harness/gen7_net.py` | One seat's view as arrays (`encode`), what the calls show (`Shown`), the net's forward pass and NumPy inference (`PolicyNet`) |
| `bridge_harness/gen7.py` | `Gen7Player`: the Gen 6 player with three switches that read the net |
| `scripts/gen7_build_dataset.py` | Published Gen 6 episodes to a training set |
| `scripts/train_gen7_policy.py` | Trains the net (JAX, CPU); writes the weights and a report that includes the auction-use test |
| `scripts/gen7_check.py` | Five checks against recorded Gen 6 tables: `fidelity`, `inference`, `match`, `speed`, `auction` |
| `scripts/gen7_lookahead.py` | From gap forks and root tables: tricks lost at each trick, Gen 6's estimates against real play, and what one to three tricks of lookahead could recover |
| `tests/test_gen7.py` | 23 tests |
| `models/cardplay/gen7-policy-v0-2026-11-11/` | The trained net (258,434 parameters), in parts, with its training report. Every check below used it |
| `models/cardplay/gen7-policy-v1-2026-11-11/` | A wider net (828,098 parameters) trained on 5,240 deals (see "More boards") |
| `models/cardplay/gen7-policy-v2-2026-11-11/` | The same net trained on 7,968 deals (see "More boards again") |
| `models/cardplay/gen7-policy-v3-2026-11-11/` | The same net trained on 12,111 deals (see "And again") |
| `models/cardplay/gen7-policy-v3.1-2026-11-11/` | v3's run taken at epoch 3, with a fitted temperature (see "Width, epochs and calibration") |
| `bridge_harness/gen7_tree.py`, `scripts/gen7_bench.py` | A few tricks of play from each seat's own view before solving, and the fork-pair bench that scores it |
| `scripts/gen7_noise.py` | What sampling noise costs a Gen 6 decision, and where the net stands against it |

## The net

**Target.** The card Gen 6 played (policy head) and Gen 6's estimated cost of every legal card (gap
head), at every searched decision of a Gen 6 seat. Earlier policy nets learned to rank near-ties
from how hands finished and were never shown that a bad card is bad; this one is.

**Data.** 4,169 episodes from the three Gen 6 feeds as of about 05:45 UTC: 4,159 deals, 638,986
decisions (221,614 from root tables, 417,372 from tie-fork tables). Split by deal family: 3,355
deals train, 398 validation, 406 test.

**Inputs.** Each card's state (in hand, in dummy, played by whom and when, on the table), the
contract, vulnerability, who is deciding, the raw calls, and what the hand-fit scorer says each
seat's calls show (below).

**Scores on test deals** (60,010 decisions; "equal-best" means Gen 6's search rates the card level
with its best):

| | Net | Reference |
| --- | --- | --- |
| Log-loss on Gen 6's card | 0.920 | 1.270 uniform over legal cards; 0.758 knowing the equal-best set |
| Plays Gen 6's exact card | 61.0% | |
| Plays an equal-best card | 83.1% | |
| Tricks given up per decision, by Gen 6's estimates | 0.080 | 0.200 random legal card |

By phase (validation): tricks given up 0.075 at the opening lead, 0.064 at tricks 1-4, 0.099 at
tricks 5-8, 0.080 at tricks 9-13. Exact-card agreement 46% at the lead.

**It should not pick cards.** At 0.08 tricks per decision it would lose heavily to Gen 6.

**It is good at keeping the right card among a few.** Same test decisions, cards ranked by policy
probability:

| Kept | Cards kept (mean) | An equal-best card is kept | Tricks given up by the best kept card | The card actually played is kept |
| --- | --- | --- | --- | --- |
| Top 1 | 1 | 83.1% | 0.080 | 61.0% |
| Top 2 | 2 | 93.7% | 0.021 | 85.6% |
| Top 3 | 3 | 97.3% | 0.0066 | 93.9% |
| Until probabilities add to 0.80 | 2.1 | 95.8% | 0.016 | 88.4% |
| Until they add to 0.90 | 2.6 | 98.0% | 0.0064 | 94.6% |
| Until they add to 0.95 | 3.0 | 99.2% | 0.0025 | 97.7% |

Variable breadth beats fixed breadth at the same average. The opening lead needs more: top 3 keeps
an equal-best lead 82% of the time, and the 0.95 rule keeps 6.9 of 13 cards for 98.2%. "Best" is
Gen 6's own estimate, so this says the net rarely prunes what Gen 6 would choose, not that the kept
set holds the truly best card.

**More deals help, steeply.** Same recipe on part of the training deals (validation; this run had
the scorer inputs fed to the whole net only, before the per-suit change below):

| Training deals | Tricks given up | Exact card |
| --- | --- | --- |
| 419 | 0.139 | 51.0% |
| 839 | 0.133 | 54.2% |
| 1,678 | 0.115 | 56.9% |
| 3,355 | 0.084 | 61.8% |

Tricks 9-13 improve at the same rate as the rest (0.113 to 0.079 over the last doubling). The net
overfits within three epochs at every size; it is short of deals, not of capacity.

### The auction

The first net ignored the auction. Blanking it, or swapping in another deal's auction, changed
nothing after the lead. A few thousand deals cannot teach what calls mean from the raw calls (the
hand-fit scorer had 230,010 deals).

What is fed now, per seat, is the scorer's reading of that seat's calls: expected length, chance of
five or more, chance of two or fewer and expected high-card points in each suit, and total points
with their spread. It is the scorer's posterior over a fixed bank of 4,096 random hands, given the
auction alone. The bank is 80% plain random hands, 10% drawn from 16+ point hands and 10% from
six-card-suit hands, reweighted exactly (ordinary hands are 0.8 times as common as dealt, strong
1.8, long 1.3, both 2.3). Examples: 1NT-3NT gives opener 15.8 points and responder 11 points with
no five-card major; 3S-4S gives opener 7.0 spades and 8 points.

Feeding that to the whole net was not enough. Routing each suit's part into that suit's encoder was.
The test is the same held-out positions with another deal's auction in place of the real one
(validation):

| Net | Tricks given up: real auction | Another deal's auction | Lead agreement: real | Another deal's |
| --- | --- | --- | --- | --- |
| Raw calls only | 0.087 | 0.089 | 41.9% | 38.3% |
| Scorer reading, whole net | 0.084 | 0.085 | 45.2% | 45.0% |
| Scorer reading, per suit (this net) | 0.083 | 0.088 | 46.0% | 37.3% |

How much is there to read? `gen7_check.py auction` decides 237 recorded positions again with the
local Gen 6, four ways, and costs each choice with a 256-layout Gen 6 that has the real auction
(tricks given up per decision):

| | All | Trick 1 | Trick 2 | Tricks 3-4 | Tricks 5-6 | Tricks 7-9 | Tricks 10-12 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Gen 6 as live (32 layouts) | 0.004 | 0.007 | 0.013 | 0.006 | 0.002 | 0.000 | 0.000 |
| Gen 6, another deal's auction | 0.019 | 0.007 | 0.026 | 0.035 | 0.031 | 0.008 | 0.002 |
| Gen 6, no auction knowledge | 0.023 | 0.001 | 0.013 | 0.033 | 0.041 | 0.017 | 0.017 |

So the auction is worth about 0.015 tricks per decision to Gen 6's own card, mostly at tricks 2-6,
and the net now captures about a third of that (0.005). Not reading the auction was about a quarter
of the net's shortfall; the rest is card play in general. Small sample (15 to 48 positions per
column). The same run shows that two runs of Gen 6-32 on one position choose a different
equal-best set 27% of the time at trick 1 and 40% at trick 2, at almost no cost, so exact-card
agreement has a ceiling well under 100% early in the hand.

Suit-swap augmentation was tried and dropped. It improved card-choice scores, but relabelling an
auction's suits breaks what the calls mean.

## The player

`Gen7Player` is `Gen6Player` plus switches in `spec['gen7']`. Layouts still come from the lead net,
the hand-fit scorer and the deal list, and DDS still ranks the cards.

| Switch | Default | Meaning |
| --- | --- | --- |
| `play_weight` | 0.5 | From the deal list on, each layout's weight is multiplied by the net's probability of every card the hidden seats have played, given what that seat saw in that layout, raised to this power. 0 = Gen 6's weights |
| `play_floor` | 0.05 | Each such probability is mixed with this share of uniform over the legal cards |
| `play_max_layouts` | 1024 | A longer list is first cut to this many by scorer weight |
| `play_lead` | true | The opening lead counts as a play |
| `tie_break` | `net` | Exact ties go to the net's most probable card; `gen5` = the Gen 5 policy net, as Gen 6 |
| `search_from_trick` | 1 | Earlier tricks are played from the net with no search (for fast data tables). 1 = always search |
| `net_sample` | false | Unsearched cards are drawn from the policy instead of taking its top card |

With `play_weight` 0, `tie_break` `gen5` and `search_from_trick` 1 it plays Gen 6's game card for
card (tested).

A hidden seat's view is rebuilt from the decider's Observation and the layout alone
(`gen7.past_view`). A defender's hidden choosers are partner and declarer, and declarer's choice of
dummy's cards counts; declarer's are both defenders. The tests check the rebuilt view against the
Observation the game really gave that seat, for every kind of play. The same function is what a
forward tree search needs.

## Checks

All on deals the net did not train on. `scripts/gen7_check.py`.

**Fidelity.** The Gen 6 built here from the repository's model files is the live bot: at 156
recorded deal-list decisions the largest estimate difference is 1.4e-7, and the tie-break card
matches 119 times of 119. (It never loads the lead net, which needs TensorFlow, so opening leads
are taken from the record.)

**Does the net's reading of the play find the true layout?** Yes. 1,881 recorded deal-list
decisions on 74 test deals, settings fixed beforehand (`play_weight` 0.5, floor 0.05). Mean
log-probability of the true layout:

| Weighting | All | Hidden seats played by Gen 6 | A hidden seat played by another bot |
| --- | --- | --- | --- |
| Uniform over the list | -3.75 | -4.10 | -3.64 |
| Gen 6 (scorer) | -2.77 | -3.12 | -2.65 |
| Scorer and play | -2.47 | -2.68 | -2.40 |
| Gain | 0.30 ± 0.04 | 0.44 ± 0.07 | 0.25 ± 0.04 |

The true layout became more likely at 70% of decisions. The opening lead supplies 0.04 of the
0.30. On validation deals (with the previous version of the net) the gain was 0.28 ± 0.03. On both,
any `play_weight` from 0.5 to 0.75 with a floor from 0.02 to 0.15 scored within 0.04 of the best.

**Does that pick better cards?** Not measurably, at these tricks. The card changes at 1.6% of those
decisions. True-deal double-dummy cost per decision: 0.0064 with Gen 6's weights, 0.0048 with play
weights, difference 0.0016 ± 0.0014 (test); on validation, with the previous version of the net,
-0.0014 ± 0.0018. From
trick 7 there is little left to decide. If the play reading is worth tricks it is earlier in the
hand, where it cannot be applied to an exact list and needs sampling.

**Match.** 40 test boards against the local Gen 6: the recorded contract and opening lead, both
rooms, sides swapped, the same random stream for the same position, so a board is flat unless Gen 7
chooses differently. Gen 7 (`play_weight` 0.5, net tie-break) scored +0.30 IMPs per board ± 0.21;
8 boards were not flat (5 won, 3 lost). That is no evidence of a difference. It shows the player
plays whole tables and is not broken.

**Cost.** In that match a table with Gen 7 at two seats took 6.7 cpu-seconds after the lead; Gen 6
at all four took 5.5 on other boards. The extra is the play likelihood: each seat's first deal-list
decision scores up to 1,024 layouts for every earlier hidden play, and later ones reuse a cache and
score only the new plays.

**Fast data tables.** Gen 6 spends 27% of its search time on the opening lead, 43% at trick 1 and
20% at trick 2 (889 recorded root tables). Measured here on 8 boards: a full Gen 6 table after the
lead 5.5 cpu-seconds (about 7.6 with the lead search, by that share); the net playing the lead and
tricks 1-2 with Gen 6's search from trick 3, 1.95; search from trick 4, 1.1. So about 4 times and 7
times faster on table time, not 10 and 20: the scorer's one-off hand-type scoring for the auction
moves to the first searched trick. Tie forks (about 1.2 cpu-seconds per root table) and the
per-board work do not shrink.

## More boards (07:30 UTC)

2,325 boards had reached the feeds beyond the 4,169 used above: 1,194 on the two v7-capture feeds
(with gap forks), 571 on the chatgpt feed, 479 on the two Gen 6 against BEN feeds, 81 on the
independent feed. Adding them takes training deals from 3,355 to 5,240 and decisions from 519,094
to 1,003,622 (gap forks add many decisions per board). Same recipe, same test deals as above:

| | v0 (3,355 deals) | Same net, 5,240 deals | v1: wider net, 5,240 deals |
| --- | --- | --- | --- |
| Parameters | 258,434 | 258,434 | 828,098 |
| Tricks given up per decision | 0.080 | 0.062 | 0.057 |
| Plays Gen 6's exact card | 61.0% | 63.8% | 65.2% |
| An equal-best card in its top 3 | 97.3% | 97.9% | 98.0% |
| Cards kept until probabilities add to 0.98 | 3.42 | 3.25 | 3.14 |

The learning curve predicted about 0.065 for the same net. Breadth for the same coverage is already
falling. With 3,355 deals the two widths scored the same; with 5,240 the wider one is better, so it
is the one released as v1. It is about four times slower to evaluate.

## More boards again (11:08 UTC): v2

3,396 more boards by 10:05 UTC, mostly the fast self-play feeds (2,237), with their tie and gap
forks: 7,968 training deals and 2,042,221 decisions. Same net and recipe as v1, same test deals:

| | v1 (5,240 deals) | v2 (7,968 deals) |
| --- | --- | --- |
| Tricks given up per decision | 0.057 | 0.046 |
| Plays Gen 6's exact card | 65.2% | 67.9% |
| An equal-best card in its top 3 | 98.0% | 98.3% |
| Cards kept until probabilities add to 0.90 | 2.35 | 2.23 |
| Cards kept until probabilities add to 0.98 | 3.14 | 2.98 |

Tricks given up fell by 20% for 52% more deals, as it did for the step before (22% for 56%, at the
narrower width). On that slope (given up proportional to deals to the power -0.54) halving it again
takes 3.6 times the deals. Two steps of one curve; the new deals also carry twice the decisions
per deal, most of them in fork tables. The feeds were adding about 1,560 boards an hour at 11:00.

## And again (15:57 UTC): v3

5,163 more boards: the 1,381 held back for the bench above and two thirds of the 5,673 that reached
the feeds between 10:58 and 15:24 UTC (about 1,275 an hour). 12,111 training deals and 3,696,408
decisions. The other third of the newest boards (1,891) is in no net's training set.

All four nets on v0's 406 test deals (60,010 decisions), from `scripts/gen7_compare_nets.py`:

| | v0 | v1 | v2 | v3 |
| --- | --- | --- | --- | --- |
| Training deals | 3,355 | 5,240 | 7,968 | 12,111 |
| Width (parameters) | 256 (258k) | 512 (828k) | 512 | 512 |
| Tricks given up per decision | 0.080 | 0.057 | 0.046 | 0.041 |
| Plays Gen 6's exact card | 61.0% | 65.2% | 67.9% | 70.1% |
| An equal-best card in its top 3 | 97.3% | 98.0% | 98.3% | 98.5% |
| Cards kept until probabilities add to 0.98 | 3.42 | 3.14 | 2.98 | 2.90 |
| Cards kept until probabilities add to 0.90 | 2.61 | 2.35 | 2.23 | 2.16 |

Each step's cut in tricks given up, with 95% intervals from 2,000 bootstrap draws of deals, and as an
exponent of training deals:

| | All | Lead | Tricks 1-2 | Tricks 3-6 | Tricks 7-13 |
| --- | --- | --- | --- | --- | --- |
| v0 to v1 (width doubled too) | 28% [25, 32] | 24% [7, 36] | 27% [16, 36] | 26% [20, 31] | 29% [25, 34] |
| v1 to v2 | 20% [15, 25], -0.54 | 8% [-7, 21] | 18% [6, 28] | 17% [10, 24] | 22% [15, 28] |
| v2 to v3 | 11% [5, 16], -0.28 | -12% [-32, 5] | 8% [-5, 20] | 22% [14, 28] | 8% [0, 15] |
| Share of what v3 still gives up | | 1.3% | 3.8% | 21.2% | 73.7% |

The last step is flatter: the exponent's change is +0.25 [+0.02, +0.48]. The flattening is at
tricks 7-13, which are 70% of the decisions and 74% of what v3 still gives up; tricks 3-6, where
the tree asks for its replies, kept the earlier pace. Held-out log-loss was flat from epoch 2 to
epoch 3 while held-out tricks given up still fell (0.041 to 0.039), and the recipe keeps the epoch
with the best log-loss.

## Width, epochs and calibration (17:15 UTC): v3.1

A 768-wide net (1,709,058 parameters) on v3's data and recipe. Tricks given up on 433,774
validation decisions, by epoch:

| Epoch | 512 wide | 768 wide |
| --- | --- | --- |
| 1 | 0.0438 | 0.0433 |
| 2 | 0.0408 | 0.0402 |
| 3 | 0.0387 | 0.0387 |

The wider net fits the training deals better (training loss 0.54 against 0.59) and does worse on
held-out log-loss (0.733 against 0.719). Width is not what limits the net; the number of deals is.

Epoch 3 is better than epoch 2 at both widths, but overconfident. Every net here is: the
temperatures that minimise held-out log-loss are 1.21 (v0), 1.25 (v1), 1.24 (v2), 1.17 (v3), 1.25
(512 wide, epoch 3) and 1.36 (768 wide, epoch 3). So the cards-kept figures in the tables above
are 0.2 to 0.3 cards low. Calibrated, cards kept until probabilities add to 0.98 are 3.63, 3.42,
3.27 and 3.12 for v0 to v3, and to 0.90 2.84, 2.61, 2.47 and 2.34. Coverage at a fixed number of
cards (top 2, top 3) does not depend on calibration.

v3.1 is the 512-wide run at epoch 3 with its temperature (1.246) built in. On v0's test deals it
gives up 0.0374 against v3's 0.0406, 7.8% [4.6%, 11.0%] less: lead 14% [3, 24], tricks 1-2 13%
[3, 23], tricks 3-6 3% [-2, 9], tricks 7-13 9% [5, 12]. The 768-wide net at epoch 3 with its own
temperature is level with it (-0.2%, [-6.3%, 5.6%]).

## More boards a fourth time (22:10 UTC): v4

6,411 more boards: the 1,891 held back for v3.1's tree bench and the 4,520 that reached the feeds
between 15:24 and 21:19 UTC. 17,207 training deals and 5,826,238 decisions, 1.42 times v3.1's.
v3.1's recipe: 512 wide, epoch 3 (now the best epoch by held-out log-loss too), temperature 1.201
fitted on gen7_v2's validation deals and built in.

All six nets on v0's 406 test deals (60,010 decisions):

| | v0 | v1 | v2 | v3 | v3.1 | v4 |
| --- | --- | --- | --- | --- | --- | --- |
| Training deals | 3,355 | 5,240 | 7,968 | 12,111 | 12,111 | 17,207 |
| Tricks given up per decision | 0.080 | 0.057 | 0.046 | 0.041 | 0.0374 | 0.0333 |
| Plays Gen 6's exact card | 61.0% | 65.2% | 67.9% | 70.1% | 70.5% | 72.0% |
| An equal-best card in its top 2 | | | | | 96.0% | 96.3% |
| An equal-best card in its top 3 | 97.3% | 98.0% | 98.3% | 98.5% | 98.5% | 98.6% |
| Cards kept until probabilities add to 0.98, calibrated | 3.63 | 3.42 | 3.27 | 3.12 | 3.09 | 3.02 |
| Cards kept until probabilities add to 0.90, calibrated | 2.84 | 2.61 | 2.47 | 2.34 | 2.31 | 2.25 |

v3.1 to v4: 11.1% less given up, 95% interval [5.1%, 16.5%], exponent of training deals -0.34
[-0.51, -0.15]. By stage: lead 9% [-10, 25], tricks 1-2 7% [-8, 19], tricks 3-6 8% [0, 16], tricks
7-13 12% [5, 19]. The step from v2 to v3 was 11% for 1.52 times the deals (exponent -0.28), so the
curve has not flattened further. What v4 still gives up is 1.2% at the lead, 3.8% at tricks 1-2,
23.0% at tricks 3-6 and 72.0% at tricks 7-13. With another deal's auction v4 gives up 0.037
against 0.035 and its agreement with Gen 6's lead falls from 56.1% to 43.0%.

The set (7,257,481 examples, 5.4 GB as stored) did not fit the 6 GB the trainer had: the first run
was killed. `train_gen7_policy.py` now maps the file and holds the whole-number tables (state,
order, legal, auction, owner) at 4, 6, 1, 1 and 2 bits a number: 3.3 GB, the same batches. On two
cores an epoch of 5.8M examples takes 6 minutes.

### Which head chooses the card

Every figure above ranks the cards by the policy head. The same nets ranked by their gap head (the
predicted loss of each card against the best), and by policy log-probability minus ten times the
predicted gap, on the same 60,010 test decisions:

| | Tricks given up | Best card first | In top 2 | In top 3 |
| --- | --- | --- | --- | --- |
| v3.1, policy head | 0.0374 | 88.4% | 96.0% | 98.5% |
| v3.1, gap head | 0.0302 | 89.3% | 94.5% | 97.0% |
| v3.1, policy - 10 x gap | 0.0297 | 89.5% | 95.9% | 98.2% |
| v4, policy head | 0.0333 | 89.2% | 96.3% | 98.6% |
| v4, gap head | 0.0259 | 89.9% | 94.6% | 97.0% |
| v4, policy - 10 x gap | 0.0260 | 90.1% | 96.1% | 98.3% |

The gap head gives up 22% less than the policy head with v4 (95% interval [16%, 28%]) and 19%
[14%, 24%] with v3.1, about what two of the data steps above bought. It finds a best card barely
more often; it misses by less. The gain is at tricks 7-13 (0.024 against 0.034 with v4); at the
lead and tricks 1-2 the policy head is slightly ahead (0.047 against 0.050, 0.020 against 0.023).
The gap head's top-2 and top-3 coverage is worse; the blend keeps the policy head's coverage and
the gap head's first choice. It applies wherever the net's own first choice is played. Play
weights need the probability of the card Gen 6 would play, which is the policy head's job. Whether
blended replies help the tree has not been benched. (`scripts/gen7_head_eval.py`.)

With the tree's reply rule (cards until probabilities add to 0.9, at most two) v4 keeps 1.73
cards, an equal-best card among them at 96.1% of decisions and Gen 6's own card at 90.6% (v3.1:
1.75, 95.8%, 89.9%).

## What lookahead could be worth

`scripts/gen7_lookahead.py` on 700 capture-feed episodes: 500 root tables and 8,809 gap-fork pairs.
In a pair, A is the card Gen 6 played and B a card it rated worse, which the collector forced and
played out from the same position.

**Tricks lost at each trick.** Double-dummy cost, on the real deal, of the card a Gen 6 seat played,
per searched decision:

| Lead | Trick 1 | Trick 2 | Tricks 3-4 | Tricks 5-6 | Tricks 7-9 | Tricks 10-13 |
| --- | --- | --- | --- | --- | --- | --- |
| 0.26 | 0.013 | 0.042 | 0.027 | 0.023 | 0.014 | 0.005 |

This is a ceiling: it includes what cannot be avoided without seeing the cards. The opening lead is
one decision in forty and 27% of Gen 6's search time, and also 27% of the tricks its seats lose this
way.

**Gen 6's estimates against real play.** Over all pairs Gen 6 estimated that B would cost 0.47
tricks and it cost 0.39. B did better than A in 8.2% of pairs, worse in 38.7%, the same in the rest.
B did better most often early: 18% at the lead, 11.5% at tricks 1 and 2, 10% at tricks 3-4, 7% at
tricks 5-6, 4% at tricks 7-9, 1% later.

**What a trick of lookahead recovers.** Both lines of a pair are valued double dummy on the real
deal straight after the card and after 4, 8 and 12 plies of the play that actually followed, and
that value is used to choose between A and B. Tricks lost per pair by that choice, against choosing
with hindsight:

| Decision at | Pairs | Always A (Gen 6) | Now | +1 trick | +2 tricks | +3 tricks |
| --- | --- | --- | --- | --- | --- | --- |
| Lead | 715 | 0.231 | 0.150 | 0.126 | 0.117 | 0.101 |
| Trick 1 | 494 | 0.146 | 0.140 | 0.136 | 0.130 | 0.119 |
| Trick 2 | 1,048 | 0.146 | 0.132 | 0.112 | 0.101 | 0.083 |
| Tricks 3-4 | 2,012 | 0.123 | 0.100 | 0.087 | 0.071 | 0.055 |
| Tricks 5-6 | 1,793 | 0.086 | 0.069 | 0.047 | 0.032 | 0.021 |
| Tricks 7-9 | 2,032 | 0.045 | 0.031 | 0.019 | 0.008 | 0.004 |
| Tricks 10-13 | 715 | 0.011 | 0.001 | 0.000 | 0.000 | 0.000 |

"Now" is the double-dummy assumption with the layout known. Two tricks of real play before it
removes 22% of its error at the lead, 7% at trick 1, 23% at trick 2, 29% at tricks 3-4, 54% at
tricks 5-6 and 75% at tricks 7-9. So depth alone has a modest ceiling early in the hand, where a
decision pays off over many tricks; a leaf value learned from how hands finish matters more there
than going from eight plies to twelve.

Limits, and they matter. These are upper bounds, not estimates of what a search would gain. The
real deal is used at the leaf, and a search must guess the layout. Part of every figure is chance in
how two lines happen to finish; the deeper columns have already seen some of that chance play out,
which a search at the table cannot. Pairs are sampled by band (estimated gap up to 0.125, up to
0.5, above), a third each, so the figures are per sampled pair, and they cannot be added up into
tricks per table: one changed card changes every later decision.

The same pairs are the way to measure a real search before any match is played: run it on the
position, see whether it prefers A or B, and average the realized cost of B over the pairs where it
prefers B. Gen 6 scores zero by construction. With 8,809 pairs the standard error is a few
thousandths of a trick per pair, and the feeds add about six pairs per board.

**Fork tables as training data.** The same net trained on the same 5,240 deals, scored on root-table
(real play) test positions: root tables only 0.068 tricks given up, with tie-fork tables 0.064, with
gap-fork tables 0.065, with both 0.063. On the self-play feed tie forks take 20% of a board's CPU
and gap forks 28%.

## The tree on the bench (to 10:50 UTC)

`bridge_harness/gen7_tree.py` plays the next few tricks from each seat's own view before solving.
All layouts are walked together, each carrying the probability of the play so far in that layout.
Another seat's card comes from the net on what that seat sees there (`reply='net'`), from a small
search from that seat's view (`'search'`), or double dummy as in PIMC (`'dd'`). The decider's own
later card is one choice for every layout that still looks the same to it (`own='best'`), or is
treated like any other seat (`'net'`, `'search'`). With `tricks=0` the values are PIMC's exactly.

`scripts/gen7_bench.py` scores an evaluator on fork pairs. In a pair, A is the card Gen 6 played
and B a card the collector forced at the same decision and played out with the same bots, so both
have a real result. An evaluator that prefers B is charged B's result minus A's. Figures are tricks
per sampled pair against plain search on the same layouts. Pairs are a third each from estimated
gaps up to 0.125, up to 0.5, and above; tricks 3-13; opponents 45% Gen 5, 18% 6-256, the rest bots
1-3. Net v1, 8 layouts, two cards a seat kept to probability 0.90, unless stated.

The **correction** is the tree's gap between A and B minus plain search's gap on the same layouts.
Its **share** is the coefficient c in: realized cost of B = a + b x plain gap + c x correction. At 1
the results move as far as the tree moved its estimate; at 0 the movement is noise.

| Tree | Pairs | Tricks a pair | Correction share | Seconds a pair |
| --- | --- | --- | --- | --- |
| One trick | 5,950 | -0.005 +- 0.003 | 0.13 +- 0.06 | 0.08 |
| Two tricks | 5,950 | -0.011 +- 0.004 | 0.13 +- 0.04 | 0.42 |
| Two tricks, one card a seat | 3,727 | -0.010 +- 0.004 | 0.07 +- 0.04 | 0.03 |
| Two tricks, replies sharpened (`reply_power=3`) | 3,727 | -0.001 +- 0.004 | 0.12 +- 0.05 | 0.14 |
| Two tricks, net-rated mistakes dropped (`reply_gap=0.15`) | 3,727 | -0.002 +- 0.004 | 0.15 +- 0.07 | 0.24 |
| Three tricks | 351 | -0.009 +- 0.021 | 0.40 +- 0.16 | 3.2 |
| Two tricks, three cards a seat | 351 | -0.023 +- 0.020 | 0.32 +- 0.19 | 1.2 |
| Two tricks, every legal card at the decider's later turn | 351 | -0.003 +- 0.010 | 0.35 +- 0.14 | 3.2 |
| Two tricks, decider's later card from the net | 1,178 | -0.040 +- 0.011 | 0.12 +- 0.08 | 0.43 |
| Two tricks, every later card by a search from that seat's view | 1,178 | -0.015 +- 0.010 | 0.34 +- 0.12 | 1.6 |

The 3,727-pair rows include 2,355 tie-audit pairs (two cards Gen 6 rated level); on those the
two-trick tree is +0.006 +- 0.004. On the 1,178 pairs of the last two rows the plain two-trick tree
is -0.015 +- 0.010, so the decider's later card from the net is worse by 0.025 +- 0.007 pair by pair
and search replies score the same.

Four in five of the 5,950 pairs are on deals the net was trained on: the boards were split by deal
for the net, and the bench read every deal. On the 1,081 pairs from held-out deals the two-trick
tree is -0.023 +- 0.010 with a share of 0.07 +- 0.08; on training deals it is -0.009 +- 0.004 and
0.14 +- 0.04. So the table flatters the tree somewhat, and the same holds for the weighting to
tables below. `--splits 1,2` keeps the bench to held-out deals and should always be given.

What the rows say:

- No tree beats plain search from trick 3 on. By estimated gap the two-trick tree is +0.016 +-
  0.008 up to 0.125, -0.029 +- 0.007 up to 0.5, and -0.020 +- 0.005 above. It prefers B in 16% of
  pairs where plain search on the same layouts does in 2%.
- With double-dummy replies and only the decider's later cards made honest, the tree equals plain
  search in 90% of pairs and never prefers a different card. With 8 layouts the other seats' cards
  split the sample, and at the decider's next turn 1.4 layouts still look alike (2.6 of 32), so
  "one choice for layouts that look alike" barely binds.
- Treating the decider's later self like the other seats did not fix it.
- The correction share follows how faithfully the reply model plays what the seats really play.
  The stand-in searcher (8 layouts from 64 random hands fitted to the auction) is crude early and
  close to the real seats late: its share is 0.10 +- 0.15 at tricks 3-6 and 0.85 +- 0.17 at tricks
  7-13. With net replies the share at tricks 7-13 is 0.15 +- 0.09. The share is a gauge to put on
  each new net.

**Weighted back to tables.** Every gap fork records the probability with which it was drawn, so the
pairs can be weighted to the total over every (decision, other card) of one side at one table
(1,372 tables, the candidate's decisions; about 36 such pairs a side). Two-trick tree, B among the
net's top three cards (kept to probability 0.98):

| | Overrules of Gen 6 a side | Tricks a side | IMPs a side |
| --- | --- | --- | --- |
| Tricks 3-13 | 3.8 | -0.16 +- 0.16 | -0.31 +- 0.75 |
| Tricks 3-6 | 2.3 | +0.11 +- 0.13 | +0.34 +- 0.63 |
| Tricks 7-13 | 1.5 | -0.27 +- 0.10 | -0.65 +- 0.35 |
| Estimated gap up to 0.125 | 2.0 | +0.18 +- 0.08 | +0.38 +- 0.47 |
| Up to 0.5 | 1.3 | -0.14 +- 0.11 | +0.23 +- 0.46 |
| Above 0.5 | 0.5 | -0.20 +- 0.08 | -0.92 +- 0.35 |

With any card allowed it is 5.2 overrules and -0.46 +- 0.22 tricks a side. Counting the 6-256
seats as well, the first row is -0.06 +- 0.16. A bot plays both sides of a board in a match, so a
board is about twice a side: -0.33 +- 0.31 tricks, -0.6 +- 1.5 IMPs. On the boards on hand 6-32
beats 5RZ32 by 0.73 +- 0.08 IMPs a board (3,018 boards), bots 2 and 3 by 0.7, bot 1 by 1.7, and
trails 6-256 by 0.14 +- 0.11 (1,130). So the bench cannot place a bot that uses the tree from
trick 3 to the end between Gen 5 and Gen 6. Limits of the weighting: one card is swapped and the
arena's bots play the rest; the tree was two wide below the root; overrules of the same decision
are added.

The loss is at tricks 7-13. From trick 7 Gen 6 solves the list of deals still consistent, which
costs 0.29 cpu-s of a 9.1 s table and has no sampling noise (below). The tree replaces that with 8
layouts and a reply model. So the shape to test first is Gen 6's search through trick 2, the tree
at tricks 3-6, and Gen 6's search from trick 7. The split by trick was chosen after seeing these
pairs, so it needs pairs not used here; the 3,396 boards that arrived after them carry 9,615 at
tricks 3-6 (5,848 of those from self-play).

## The tree on boards no net had seen (11:40 UTC)

1,381 boards reached the feeds between 10:05 and 10:58 UTC, after v2's training set was fixed.
Their gap forks at tricks 3-6, read in file order until the time cap: 1,712 pairs from 658
self-play deals. Two-trick tree, two cards a seat, 8 layouts, v1 and v2 as the reply model on the
same pairs:

| Reply model | Tricks a pair against plain search | Correction share | Tricks a side, B among the net's top three |
| --- | --- | --- | --- |
| v1 | -0.020 +- 0.008 | 0.08 +- 0.07 | -0.23 +- 0.22 |
| v2 | -0.013 +- 0.008 | 0.15 +- 0.08 | -0.09 +- 0.24 |

So the tree at tricks 3-6 does not beat Gen 6 with either net, and the +0.11 a side in the table
above was the training deals speaking. v2 against v1 pair by pair is +0.007 +- 0.007.

Both trees are too kind to the worse card. Over these pairs plain search puts the cost of B at
0.47 tricks, it really cost 0.40, and the trees put it at 0.35 (v1) and 0.36 (v2). One pair shows
the mechanism. 3NT by North; East wins the spade ace and returns the five, dummy (T97) plays the
nine, West the queen, and North holds K3. Gen 6 wins the king. The tree prefers to duck, because in its
lookahead West, left with J6, leads the jack into the K3 in most layouts; at the table West cashed
the club ace and the duck cost a trick. Gen 6 never ducks there, so the net has few examples of
what a defender does next, and the tree asks it about such positions for every card but the best.

That was measured (`scripts/gen7_reply_check.py`, 2,222 gap forks at tricks
3-6 on the same unseen boards): the next searched decision after the forked ply, scored by Gen 6's
own estimates there, in the fork table and in the root table. Decisions with something to lose only.

| | v1 gives up | v1 plays an equal-best card | v2 gives up | v2 plays an equal-best card |
| --- | --- | --- | --- | --- |
| Right after a forced card | 0.121 +- 0.008 | 70.7% | 0.093 +- 0.007 | 74.3% |
| Right after the search's own card | 0.086 +- 0.006 | 72.5% | 0.077 +- 0.006 | 73.7% |

The net is worse right after a forced card, by 40% for v1 and 20% for v2, which had 2.3 times as
many gap forks to learn from. The larger fact is the second row: at a decision with something to
lose the net's card is not an equal-best one a quarter of the time, wherever it comes from. A
two-trick line asks for six or seven such replies.

**Spot cards.** Sampled layouts give the hidden hands different low cards, so the first low card
a hidden hand plays tells the layouts apart, and "one choice for layouts that look alike" stops
binding. `plain=1` deals the hidden hands' low cards (2-9) by a fixed rule, the same in every layout
as far as the suit lengths allow, and counts cards that do the same job as one card at every node
(touching cards; low cards that do not take the trick; low cards that do). Re-dealing the low
cards alone leaves the gap between A and B unchanged in 91% of pairs. 2,585 pairs from the same
unseen boards, each tree against plain search on the same re-dealt layouts:

| Tree, `plain=1` | Tricks a pair | Correction share | Seconds a pair | Layouts alike at the decider's later turn |
| --- | --- | --- | --- | --- |
| Net replies, v1 | -0.021 +- 0.007 | 0.14 +- 0.05 | 0.28 | 1.9 of 8 |
| Net replies, v2 | -0.017 +- 0.006 | 0.13 +- 0.06 | 0.25 | 1.9 of 8 |
| Double-dummy replies, every legal card at the decider's later turn | -0.007 +- 0.004 | 0.29 +- 0.10 | 0.41 | 2.1 of 8 |

The tree is about three times cheaper (two cards a seat no longer go to two cards that do the same
job) and no better. The last row needs no net: it is plain search with only the decider's own
later cards made honest. It does not beat plain search either; with two layouts to an
information set the constraint adds noise. That agrees with the consistent-strategy study of 8
November (`research/consistent-strategies-alpha-mu`).

So from trick 3 on no tree here beats Gen 6's search. For the net-reply tree the reply model has to
be near search quality first; on the learning curve above, a fourfold cut in what a reply gives up
is about thirteen times the deals.

## The tree with v3 (16:25 UTC)

1,962 gap-fork pairs at tricks 3-6 from the 1,891 newest boards, which no net has seen. Two-trick
tree, two cards a seat, 8 layouts, `plain=1`, v2 and v3 as the reply model on the same pairs:

| | Tricks a pair against plain search | Correction share | Tricks a side, B among the net's top three |
| --- | --- | --- | --- |
| v2 | -0.019 +- 0.007 | 0.30 +- 0.08 | -0.06 +- 0.17 |
| v3 | -0.006 +- 0.006 | 0.36 +- 0.08 | -0.02 +- 0.13 |

v3 against v2 pair by pair: +0.014 +- 0.006. By stage, v3: tricks 3-4 -0.016 +- 0.009, tricks 5-6
+0.007 +- 0.008. By Gen 6's estimated gap, v3: up to 0.125 +0.004 +- 0.013, up to 0.5 -0.009 +-
0.012, above -0.014 +- 0.006. v2's share here is 0.30 where it was 0.13 on the boards before, so
the share varies between sets of boards more than its error bar says; the comparison that holds is
the one on the same pairs.

The net's reply at the next decision with something to lose after the forked ply, on the same
boards (`scripts/gen7_reply_check.py`, 1,268 gap forks): after a forced card v2 gives up 0.089 +-
0.008 and v3 0.076 +- 0.008; after the search's own card 0.072 +- 0.007 and 0.055 +- 0.007.

So the tree's result moves with the net: from v2 to v3 it went from clearly behind Gen 6's search
to level within the error. It is not yet ahead anywhere, and the lead and tricks 1-2 are not
benched.

## The tree with v3.1 (17:40 UTC)

The same bench, run further through the 1,891 newest boards: 3,448 pairs at tricks 3-6 (the 1,962
above, which reproduce exactly, and 1,486 more). Every figure here is against Gen 6's own card A,
so it includes the cost of searching 8 layouts instead of Gen 6's 32:

| Tricks a pair, against Gen 6's card | All | Tricks 3-4 | Tricks 5-6 |
| --- | --- | --- | --- |
| Plain search on 8 layouts | -0.006 +- 0.003 | -0.004 +- 0.003 | -0.009 +- 0.004 |
| A fresh 32-layout search | -0.001 +- 0.002 | +0.000 +- 0.002 | -0.002 +- 0.003 |
| Tree, v3 replies | -0.010 +- 0.005 | -0.021 +- 0.008 | +0.003 +- 0.007 |
| Tree, v3.1 replies | -0.006 +- 0.005 | -0.011 +- 0.007 | +0.001 +- 0.007 |

v3.1 against v3 pair by pair: +0.004 +- 0.003. Against plain search on the same 8 layouts the
v3.1 tree is -0.002 +- 0.005 (tricks 5-6: +0.009 +- 0.007), so most of what it gives up against
Gen 6 is the 8-layout cap. By Gen 6's estimated gap, against Gen 6's card: up to 0.125 -0.001 +-
0.010, up to 0.5 -0.006 +- 0.009, above -0.011 +- 0.004. The correction share on this set is 0.25
+- 0.06 for both nets; 0.36 for v3 on the first 1,962 pairs was within its noise.

Used only on close calls the v3.1 tree is about level: +0.003 +- 0.004 a pair when it may overrule
only where its own 8-layout gap is at most 0.125, and +0.001 +- 0.004 where Gen 6's gap is at most
0.25. These are the best of six gates tried, so they are optimistic.

**16 layouts.** The same 3,448 pairs with the tree on 16 layouts (0.45 s a pair against 0.24):

| Tricks a pair, against Gen 6's card | 8 layouts | 16 layouts |
| --- | --- | --- |
| Plain search | -0.006 +- 0.003 | -0.004 +- 0.003 |
| Tree, v3.1 replies | -0.006 +- 0.005 | -0.005 +- 0.005 |

16 against 8 for the tree, pair by pair: +0.001 +- 0.003. Doubling the layouts halves plain
search's sampling loss but not the tree's deficit, which is in its correction (share 0.29 +- 0.06
at 16 layouts, so about 70% noise) and does not shrink with more layouts.

**Gen 6 with the tree's correction added**, the correction being the tree's gap minus plain
search's on the same layouts, added to Gen 6's own estimated gap: at full weight -0.017 +- 0.005
a pair (8 layouts) and -0.013 +- 0.005 (16). Shrunk to its measured share, with the weight (0.22
to 0.32) fitted on the other half of the deals: +0.002 +- 0.002 (8 layouts) and +0.000 +- 0.002
(16), overruling Gen 6 at 3% of decisions. So the tree can be added to Gen 6 without loss, but not
yet for a gain that can be measured; what has moved it is the net.

## The alpha bot with v3.1 over 414 boards (21:20 UTC)

The alpha branch's bot (`feature/gen7-alpha-20261111`, built in another session: Gen 6 with
play-weighted layouts from trick 7, the net breaking exact ties, and the two-trick tree at tricks
3-6) against Gen 6 (6-32), in whole boards, on the deals and seeds of that branch's run with v2.
The tree stage takes the cards within `root_margin` of the search's best (at most three) and adds
`trust` times its correction (tree value minus double-dummy value on the tree's layouts) to Gen
6's estimate. Here: v3.1, margin 0.25, trust 0.5, two wide. The v2 run: margin 0.125, trust 1,
three wide.

| IMPs a board for the alpha bot | v3.1 | The v2 run |
| --- | --- | --- |
| Boards 0-113 | +0.74 +- 0.34 | +0.65 +- 0.34 |
| Boards 114-413 | +0.21 +- 0.18 | +0.09 +- 0.16 |
| All 414 | +0.36 +- 0.16 (73 won, 40 lost, 301 flat) | +0.24 +- 0.15 |

No failures in 416 episodes. The two runs differ in net and in settings, so the 0.12 between them
is not a measurement of the net.

The tree's own forks (the card without the tree against the tree's card, both played out): 602
forks, +0.01 +- 0.03 tricks a fork, 71 better and 63 worse; at tricks 3-4 +0.04 +- 0.05, at tricks
5-6 -0.02 +- 0.03. The tree moved the card at 6% of its decisions. So at trust 0.5 the tree is
level, as the bench said it would be, and the match's margin comes from the rest of the bot. For
v2 the other session traced it to the play weights (+0.40 +- 0.12 IMPs a board by true-deal double
dummy); that split has not been redone for v3.1.

## What a Gen 7 board costs (22:10 UTC)

Cpu-seconds from the decisions' own records (`scripts/gen7_board_cost.py`), per board. The alpha
match gives both bots at root tables and at tie-fork tables; 500 feed boards give Gen 6's fork mix.

| Per decision, ms | Lead | Tricks 1-2 | Tricks 3-6 | Tricks 7-13 |
| --- | --- | --- | --- | --- |
| Gen 6, root tables | 1,216 | 766 | 51 | 12 |
| Alpha, root tables | 1,000 | 796 | 372 | 61 |
| Gen 6, after a fork | | 315 | 33 | 7 |
| Alpha, after a fork | | 258 | 260 | 27 |

A root table costs a Gen 6 side 3.85 cpu-s and an alpha side 7.1: the tree adds 2.57 (it runs at
a third of the decisions at tricks 3-6, about 1 cpu-s each) and the play weights 0.69. A feed
board is one root table (9.3 cpu-s), tie forks (4.0) and gap forks (5.0), and the forks are mostly
late tricks: 80 decisions a board at tricks 3-6 and 433 at tricks 7-13. Costing those at the alpha
bot's rates:

| Cpu-s a self-play board, today's fork mix | Gen 6 | Alpha, tree off | Alpha, tree at margin 0.25 |
| --- | --- | --- | --- |
| Root table | 9.3 | 10.8 | 16.0 |
| Tie forks | 4.0 | 9.2 | 17.5 |
| Gap forks | 5.0 | 9.0 | 18.6 |
| Board | 18.3 | 29.0 (1.6x) | 52.1 (2.9x) |

With a share f of boards tree-on, boards per unit of compute are 1 / (1.59 + 1.26 f) of Gen 6's.
Tree on at root tables only is 1.87x. The tree-off column assumes the net's tie-break costs
nothing at tricks 3-6; that was not measured. The feeds' workers run Gen 6 at this machine's
speed (9.0 against 9.1 cpu-s a root table), so 1,275 boards an hour is about 6.5 busy cores.

## The tree with v4, and two unseen sets that disagree (22:45 UTC)

The same bench on the 1,680 boards that reached the feeds after v4's training set was fixed
(21:19 UTC): 3,828 pairs at tricks 3-6, 1,488 deals, with v3.1 and v4 on the same pairs.

| Tricks a pair | v3.1, the earlier unseen set (3,448 pairs) | v3.1, this set | v4, this set |
| --- | --- | --- | --- |
| Tree against plain search on the same layouts | -0.002 +- 0.005 | -0.022 +- 0.005 | -0.021 +- 0.005 |
| Tree against Gen 6's card | -0.006 +- 0.005 | -0.027 +- 0.005 | -0.026 +- 0.005 |
| Correction share | 0.25 +- 0.06 | 0.17 +- 0.05 | 0.14 +- 0.05 |
| Spread of the corrections (sd, tricks) | 0.293 +- 0.008 | 0.348 +- 0.019 | 0.343 |

v4 against v3.1 pair by pair: +0.001 +- 0.004. So the same net and the same tree are about 2.7
standard errors apart on two sets of boards neither had seen. Checked and ruled out:

- **A leak.** All 23,144 boards on hand hashed by their hands: 23,101 distinct deals, each under
  one family name, none in more than one set, and none again when the seats, the partnerships'
  order or the suits are allowed to differ. The earlier held-out set shares no deal with v3's
  training set, nor this one with v4's.
- **The code and the net.** The tree file had not changed since 12:15 UTC; the v3.1 file has the
  same checksum in both runs.
- **The pairs.** Same bands, the same quartiles of Gen 6's gap, the same propensities, the same
  share at tricks 3-4. v3.1 has Gen 6's card as its first choice at 65% of the fork decisions in
  both sets.
- **The feeds' settings.** The feed that supplied half the earlier set (manifest 63d7bee7: +0.001
  +- 0.007 there) is at -0.031 +- 0.009 here.

What is left is chance or something about the boards not looked for. The figure to use is the
pooled one: the v3.1 tree against plain search on the same layouts is **-0.012 +- 0.004** a pair
over 7,276 pairs. The sequence given earlier in this file (-0.020 with v1, -0.006 with v3, -0.002
with v3.1) overstated the trend, because v3 and v3.1 were scored on the favourable set only. The
steps measured on the same pairs stand: v2 to v3 +0.014 +- 0.006, v3 to v3.1 +0.004 +- 0.003,
v3.1 to v4 +0.001 +- 0.004.

## Trust and margin (22:55 UTC)

`scripts/gen7_sweep.py` scores the alpha bot's rule on the bench's pairs without solving anything
again: with margin m and trust t the system plays B when Gen 6's gap for B is at most m and gap
+ t x (tree - plain search on the tree's layouts) is negative. Pairs are weighted by 1 /
propensity, so the figures are tricks a side a table against Gen 6. v3.1, both unseen sets (7,276
pairs, 5,842 sides):

| Margin | Trust 0.125 | 0.19 | 0.25 | 0.31 | 0.375 | 0.5 | 1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0625 | +0.00 +- 0.02 | +0.01 +- 0.02 | +0.01 +- 0.02 | +0.01 +- 0.02 | +0.01 +- 0.02 | -0.01 +- 0.03 | -0.01 +- 0.03 |
| 0.125 | +0.01 +- 0.02 | +0.01 +- 0.02 | +0.00 +- 0.02 | -0.01 +- 0.03 | -0.03 +- 0.03 | -0.07 +- 0.03 | -0.11 +- 0.04 |
| 0.25 | +0.01 +- 0.02 | +0.03 +- 0.03 | +0.02 +- 0.03 | +0.01 +- 0.04 | -0.02 +- 0.04 | -0.08 +- 0.05 | -0.19 +- 0.06 |
| 0.5 | +0.01 +- 0.02 | +0.03 +- 0.03 | +0.02 +- 0.03 | +0.01 +- 0.04 | -0.00 +- 0.04 | -0.08 +- 0.05 | -0.35 +- 0.08 |

- The correction carries signal: realized cost of B = a + b x gap + c x correction gives c 0.18 +-
  0.04 and b 0.91, so the trust the data supports is c / b = 0.20 [0.12, 0.28] per sampled pair
  and 0.28 [0.15, 0.42] weighted to sides.
- At that trust the gain is nil within 0.03 tricks a side. With the setting chosen on half the
  deals and scored on the other half (400 random halves): -0.003 +- 0.027.
- The sets apart: the earlier one has margin 0.25, trust 0.25 at +0.09 +- 0.055, this one at -0.02
  +- 0.03 with v3.1 and v4 alike, and on this one alone "no tree" is the held-out pick in 60% of
  the halves.
- Trust 0.5 and above loses. The match above played 0.5.

**The match's own forks.** The alpha bot records every candidate's gap, tree value and same-layout
value, and a setting no bolder than the one played switches at a subset of the same decisions, so
its switches can be scored from the forks already played (`scripts/gen7_match_forks.py`). The
recorded winners are reproduced at 603 of 603 forks. Kept at trust 0.25: 423
forks, +0.028 +- 0.029 tricks and +0.05 +- 0.12 IMPs a fork (48 better, 38 worse); at trust 0.31:
476 forks, +0.034 +- 0.027; as played, 599 forks, +0.013 +- 0.027.

So three readings (two bench sets and the match) agree that the tree at trust 0.2 to 0.3 does not
lose and has not been shown to gain; its cost is in the section above.

## Breadth and depth by stake (23:30 UTC)

Max's rule: the tree's width and depth should follow the IMPs at stake, more width where the call
is close, more depth where a lot is at stake and the plays are clear, and the stake estimate
should carry its own uncertainty.

**How skewed the stake is.** Of the 3,448 fork pairs of the earlier unseen set, 1,483 changed the
trick count. A one-trick swing was worth 0 or 1 IMP in 46% of them, 5 or more in 32% and 10 or
more in 18%; the 36% of swings worth 4 or more IMPs a trick carry 72% of the IMPs. At the 60,010
test decisions the trick at risk is worth 1 IMP at the median and 3.5 on average.

**Breadth by stake, offline** (v4 on the test deals; no solving). Keep cards in order of
probability while (probability not yet covered) x (IMPs a trick is worth) is above a threshold,
against the stake-blind rule (cover a fixed probability), at the same average number of cards
kept. IMPs given up because the best card was dropped: with the stake predicted from the net's
tricks head (off by 0.63 tricks on average; correlation 0.56 with the true stake), 17% to 33%
less at 1.9 to 2.5 cards; with the true stake (the board's result, a ceiling), 53% to 63% less.
No intervals; neighbouring settings scatter between 7% and 33%.
(`scripts/gen7_stake_breadth.py`.)

**The rule in the tree** (`path` in `TreeConfig`; see the module's docstring). A node carries its
share of the search: 1 at each root card, multiplied down the line by the probability of each
card, the other seats' by the net's reply and the decider's own by the net's policy. A node is
searched on only while share x stake >= `path`, and a card is kept only while the cards before it
leave that much uncovered. The stake is the IMP swing at declarer's double-dummy result in each
layout, averaged, plus `spread` standard deviations, so layouts that disagree about the contract
give a high stake by themselves. With a vanishing `path` the tree is the uniform tree exactly, and
with a huge one plain PIMC (tested).

**Bench.** v4, the newer unseen set, the first 2,905 of its pairs, stake-rule trees with limits of
3 tricks, 3 cards a node and probability 0.98, against the uniform two-trick tree on the same
pairs:

| Tree | Solves a pair | Against plain search, tricks a pair | Minus the uniform tree, tricks | Minus uniform, IMPs |
| --- | --- | --- | --- | --- |
| Uniform, 2 tricks | 151 | -0.023 +- 0.006 | | |
| `path` 0.1 | 157 | -0.024 +- 0.006 | -0.001 +- 0.004 | -0.00 +- 0.02 |
| `path` 0.25 | 90 | -0.017 +- 0.006 | +0.006 +- 0.005 | +0.03 +- 0.02 |
| `path` 0.5 | 61 | -0.012 +- 0.006 | +0.011 +- 0.005 | +0.05 +- 0.02 |
| 4 tricks, `path` 0.1, `spread` 1 | 220 | -0.020 +- 0.006 | +0.003 +- 0.005 | +0.01 +- 0.02 |

As the alpha bot would use them (margin 0.25, weighted to sides): at trust 0.25 the uniform tree
is -0.06 +- 0.04 tricks a side on these pairs, `path` 0.1 -0.04 +- 0.03, `path` 0.25 -0.03 +-
0.03, `path` 0.5 -0.01 +- 0.04. The correction share is 0.10 to 0.13 for every tree.

- At equal solves the stake rule is level with the uniform tree; with fewer it is better, and
  `path` 0.5 loses half as much at 40% of the solves. More depth did not help.
- On this set every tree loses to plain search, so what the stake rule buys here is less search
  where little is at stake. Whether it gains where a lot is at stake cannot be read from these
  rows: the bench did not record the stake of each pair. The alpha bot now logs it.
- One set, one net. The uniform tree's own figure moved by 0.02 between two unseen sets.

## The net as a second opinion, and the opening lead (12:30 UTC)

`scripts/gen7_second_opinion.py` writes, for every gap fork at any ply, where the net puts Gen 6's
card A and the forced card B, beside what really happened. No search is run, so the opening lead
is included. v1 on the 29,956 pairs of the 4,777 boards it never saw (2,232 of them leads):

| Decision at | Pairs | B estimated to cost, gap up to 0.125 | B really cost | When the net's first choice is B within 0.125, B then cost | Net's log-odds for B, tricks per unit |
| --- | --- | --- | --- | --- | --- |
| Lead | 2,232 | 0.080 | +0.020 +- 0.031 | -0.09 +- 0.08 (170 pairs) | -0.019 +- 0.013 |
| Tricks 1-2 | 5,197 | 0.069 | +0.080 +- 0.016 | +0.07 +- 0.04 | -0.009 +- 0.005 |
| Tricks 3-6 | 12,748 | 0.070 | +0.059 +- 0.009 | +0.04 +- 0.02 | -0.010 +- 0.003 |
| Tricks 7-13 | 9,779 | 0.038 | +0.038 +- 0.007 | +0.02 +- 0.02 | -0.002 +- 0.002 |

The last column is the coefficient of log(net's probability of B / of A) when the realized cost of
B is regressed on Gen 6's estimated gap and that log-odds.

- From trick 1 on, a close call by the search is worth what the search says it is, and playing the
  net's first choice instead loses or breaks even. The net knows a little the search does not at
  tricks 3-6 (the coefficient is three standard errors from zero) but not enough to overrule it.
- At the opening lead a close call is nearly a coin flip: the other lead cost 0.02 +- 0.03 tricks
  where the search said 0.08. 73% of leads are close calls. Playing the net's first choice there
  is +0.09 +- 0.08 tricks a switched lead for v1 (v2, on 828 unseen lead pairs: +0.23 +- 0.14):
  positive, not established.
- So at three leads in four neither the search nor a net that imitates it has the information.
  Real results could supply it. Because those leads are close to coin flips, self-play is already
  a natural experiment in them (like hands, different leads, real outcomes), and a lead model
  trained on results needs no forks. About 9,000 Gen 6 leads are on hand, which is too few.
- On the 1,891 newest boards (766 lead pairs) the net's first choice at a close lead did not hold
  up: B then cost +0.08 tricks a switch for v3 (50 switches). Pooled over every unseen lead pair,
  switching to the net's first choice at close leads is about zero.

## Sampling noise in Gen 6 (10:37 UTC)

`scripts/gen7_noise.py`, 4,097 searched decisions from trick 3 on, 120 held-out self-play deals.
Each decision is searched again nine times with fresh layouts: one draw is a fresh 6-32, four
pooled are a 128-layout search, four more pooled are the yardstick on which every card is valued.
Tricks given up per decision to the 128-layout search:

| Decider | All | Tricks 3-4 | 5-6 | 7-9 | 10-13 |
| --- | --- | --- | --- | --- | --- |
| Card played at the table (6-32) | 0.0007 +- 0.0001 | 0.0019 | 0.0013 | 0.0001 | 0.0000 |
| Fresh 6-32 | 0.0006 +- 0.0001 | 0.0018 | 0.0011 | 0.0001 | 0.0000 |
| 8 layouts | 0.0053 +- 0.0004 | 0.0099 | 0.0071 | 0.0055 | 0.0007 |
| Net v1, most probable card | 0.063 +- 0.005 | 0.061 | 0.059 | 0.076 | 0.052 |
| Net v1, gap head | 0.054 +- 0.005 | 0.060 | 0.047 | 0.071 | 0.038 |
| 8 layouts with the net's gap head as 8 more | 0.0074 +- 0.0007 | 0.0092 | 0.0108 | 0.0095 | 0.0017 |

A fresh 6-32 search plays the 128-layout search's card 97.5% of the time (99.5% at tricks 7-9, all
of the time after). So from trick 3 on:

- More layouts buy nothing: a 6-128 would gain 0.0006 tricks a decision. On the bench a redraw at
  close decisions had looked like a gain (+0.0017 +- 0.0010 a pair with two draws pooled); this
  bounds it lower.
- The net is a hundred times further from the 128-layout search than 6-32 is. Its labels are
  clean; what it lacks is deals, or capacity, or inputs.
- The net's gap head makes an 8-layout search worse, not better.

This is noise only. Every decider here, and the yardstick, shares the double-dummy assumption.
The opening lead and tricks 1-2 are not measured (the lead needs the lead net; tricks 1-2 are
slow), and that is where the time is. On 260 new self-play boards a root table is 9.1 cpu-s of
search: 4.4 s building layouts, which does not grow with the number of layouts, and 4.7 s of
solves. By trick: lead 17%, trick 1 50%, trick 2 22%, tricks 3-13 12%. A second card within 0.125
tricks of the best: 23% of decisions, 73% of opening leads, and half of all solve time. So 6-128
costs about 2.5 times a table, and extra layouts only at close decisions cost 26% for double, 78%
for 128.

## What is and is not verified

Verified:

- 23 new tests pass (`tests/test_gen7.py`: 12 for the player, 9 for the tree, 2 for the auction
  reading); the Gen 6 and gap-fork tests still pass.
- Switches off, Gen 7 plays Gen 6's game card for card.
- A hidden seat's rebuilt view equals the real one, for declarer and defender deciding, cards from
  dummy and from a hidden hand, and the opening lead.
- The batched net inputs for a layout equal the encoder run on that view.
- The play likelihood of the real deal equals the sum of the net's log-probabilities from the real
  Observations.
- NumPy inference matches the trained graph (largest logit difference 2e-6).
- The local Gen 6 reproduces the live bot's recorded estimates and tie-breaks.

Not verified:

- Strength. The match is too short to measure a difference and was not meant to.
- Play weights before the deal list (tricks 1-6). Not built.
- The net against anything but Gen 6-style play. The play likelihood assumes the hidden seats play
  like Gen 6; it still helped when a hidden seat was another bot, by less.
- Nothing was run through the collectors. `ops/gen5_runtime.py` and `ops/prepare_gen6.py` do not
  know the `gen7` engine.
- Two of the suite's 209 tests need TensorFlow, which this machine lacks, and error here as they
  did before this branch; the other 207 pass or skip as before.

## What this says to do next

1. **The tree is not yet a gain, and the earlier trend was overstated** (see "The tree with v4").
   As a replacement for plain search at tricks 3-6 the two-trick tree is about -0.012 a pair with
   v3.1 pooled over two unseen sets, and v4 is level with v3.1. As a correction to Gen 6 at trust
   0.2 to 0.3 it does not lose and has not been shown to gain; at trust 0.5 and above it loses.
   It loses clearly from trick 7, where Gen 6 is exact and nearly free. One unseen set is not
   enough to score a net's tree: two sets with the same design differed by 2.7 standard errors.
   Score each new net on boards that arrived after its training set, pool the sets, and trust the
   steps measured on the same pairs more than the levels. The gauge is the correction share
   (0.14 to 0.25 so far; full trust beats none only above about 0.5).
2. **More deals.** The curve is steep and still falling. Fast tables are the cheap source for
   tricks 3 on. They need the two ops files taught the `gen7` engine and a bot spec with
   `search_from_trick` 3 or 4, `play_weight` 0 and `tie_break` `gen5` so the searched decisions are
   Gen 6's. Cards played from the net carry no estimates and the dataset builder skips them.
   Opening leads and tricks 1-2 stay full price.
3. **Log what the search knew.** The owner probability of each unseen card under Gen 6's weighted
   layouts is computed at every decision and thrown away. Logged, it is a better auction input for
   the net than the per-seat reading used here, at no extra search cost.
4. **Check every turn of the loop by play**: new search against the old one on the same deals, and
   against BEN.

## Commands

```
python models/cardplay/hand-fit-scorer-v0-2026-11-11/restore.py
python models/cardplay/gen5-2026-11-10/restore_policy.py
python models/cardplay/gen7-policy-v0-2026-11-11/restore.py      # and -v1-, -v2-
python scripts/build_dds.py

python scripts/gen7_build_dataset.py --episodes EPISODES --scorer models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz --out gen7.npz
python scripts/train_gen7_policy.py --data gen7.npz --out run --kind suit --width 256 --epochs 3

P=models/cardplay/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz
python scripts/gen7_check.py fidelity  --episodes EPISODES
python scripts/gen7_check.py inference --episodes EPISODES --policy $P
python scripts/gen7_check.py match     --episodes EPISODES --policy $P
python scripts/gen7_check.py speed     --episodes EPISODES --policy $P --search-from-trick 3
python scripts/gen7_check.py auction   --episodes EPISODES
python scripts/gen7_lookahead.py       --episodes EPISODES_WITH_GAP_FORKS
python scripts/gen7_bench.py           --episodes EPISODES_WITH_GAP_FORKS --policy $P --tricks "1;2" --splits 1,2 --out rows.json
python scripts/gen7_bench.py           --episodes EPISODES_WITH_GAP_FORKS --policy $P --policy2 OTHER.npz --tricks "2;2:net=2" --from-trick 3 --to-trick 6 --splits 1,2
python scripts/gen7_noise.py           --episodes SELF_PLAY_EPISODES --policy $P --tables 120
python scripts/gen7_bench.py           --episodes EPISODES_WITH_GAP_FORKS --policy $P --tricks "0:plain=1;2:plain=1;3:plain=1,breadth=3,mass=0.98,path=0.25" --from-trick 3 --to-trick 6 --out rows.json
python scripts/gen7_sweep.py           rows.json:tree_2_plain1 [more.json:tree_2_plain1] [--other tree_2_net2_plain1]     # trust and margin
python scripts/gen7_match_forks.py     ALPHA_RUN_DIR                                                                  # the same on a match's own forks
python scripts/gen7_board_cost.py      EPISODES [MAX_FILES]                                                           # cpu by stage, root and fork tables
python scripts/gen7_head_eval.py       gen7.npz 2 0 v4=$P                                                             # policy head against gap head
python -m unittest discover -s tests -p "test_gen7.py"
```

`EPISODES` is a folder of the feeds' `*.json.gz` episode files. Training needs `jax` and `optax`
(`pip install jax optax`); everything else is NumPy.
