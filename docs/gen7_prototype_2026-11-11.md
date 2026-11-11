# Gen 7 prototype (11 November 2026)

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
| `tests/test_gen7.py` | 14 tests |
| `models/cardplay/gen7-policy-v0-2026-11-11/` | The trained net (258,434 parameters), in parts, with its training report. Every check below used it |
| `models/cardplay/gen7-policy-v1-2026-11-11/` | A wider net (828,098 parameters) trained on 5,240 deals (see "More boards") |

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

## What is and is not verified

Verified:

- 14 new tests pass; the Gen 6 and gap-fork tests still pass.
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

1. **Tree search over the net's top few cards.** A few plies now, two tricks as the target. Each
   seat's candidate moves are the cards its own view makes likely (variable breadth by probability,
   table above); other seats' nodes average over those; the decider's own later card is one choice
   per thing it will have seen; DDS at the leaves. A move enters the tree only by being likely from
   that seat's view. No double-dummy reply is added. Deeper solves are cheaper (a solve with cards
   already on the table costs a fifth of the opening-lead solve, a third at trick 2, under half at
   trick 3), which pays for part of it. Sized from 150 recorded tables with this net's breadth at
   every ply, expanding every kept move for eight plies over 32 layouts costs about 590
   cpu-seconds a table at probability 0.90, 1,800 at 0.95 and 4,800 at 0.98, against 7.6 today. So
   full width is for the first two plies only; deeper plies need one or two moves or sampled lines,
   fewer layouts, and in time a learned leaf value in place of the solve.
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
python models/cardplay/gen7-policy-v0-2026-11-11/restore.py
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
python -m unittest discover -s tests -p "test_gen7.py"
```

`EPISODES` is a folder of the feeds' `*.json.gz` episode files. Training needs `jax` and `optax`
(`pip install jax optax`); everything else is NumPy.
