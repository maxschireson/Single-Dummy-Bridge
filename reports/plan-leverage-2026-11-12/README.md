# Plan-level search and leverage, 12 November 2026

Research report, branch `research/plan-leverage-20261112` (and the same commits on the Gen 8 prototype as
`research/plan-leverage-g8-20261112`, which also holds the match wrapper and bot settings). Nothing here is launched or
merged. Work in progress: the items marked *pending* are still running as this is written.

## The question

Max, 06:46 UTC: the tree does not capture as much gain from an improved net as expected. The formula should be:
the student is worse than the teacher, a harness on the student inverts that, and training on the new teacher makes
a better student. Explore plan-based approaches: whole plans against layout families, minimax over two or three
key variables instead of 32 layouts, nets that work out what is going on.

## Answers

1. **Why the tree shows no gain from a better net.** At the decisions where it acts (a second card close to the
   search's best, tricks 3 to 6), what real play adds to double dummy is small: an sd of 0.11 tricks for gaps up to
   1/8, 0.17 up to 1/2. One layout's played-out result differs by 0.6 to 0.8. On 8 to 32 layouts the estimate is
   noisier than the thing estimated. With the real bots themselves as the simulator, choosing on 12 layouts and
   scoring on 4 others gains +0.030 +- 0.021 tricks a side at one table. No net can do more through that channel
   at those layout counts. (Section 1.)
2. **The order is the one the formula wants; the size is not.** Playouts on 128 to 512 layouts, scored against the
   real bots' playouts: v0 -0.045 +- 0.035, v4 -0.012 +- 0.027, v4.1 +0.032 +- 0.019, v4.1 with a small search at each
   simulated seat +0.034 +- 0.020 tricks a side. At most about a quarter of an IMP a board. (Section 2.)
3. **Where look-ahead does pay: tricks 7 to 12 with the bot as its own simulator.** From the deal list a playout by
   the real bot costs 0.08 s. Half of the list's layouts choose, the other half score: +0.048 +- 0.014 tricks a side
   (2,802 forks, 1,347 deals), mostly at trick 7. A played test is running. (Sections 1 and 6.)
4. **Plans as layout families do not carry it.** About four double-dummy outcome families hold 90% of the weight at
   a decision, but three simple variables explain a third of the double-dummy swing, and grouping layouts by
   double-dummy outcome explains a quarter of where real play departs from double dummy. (Section 3.)
5. **A head fitted on fork outcomes is not a lever at this scale.** On 77,000 forks it explains 7% of what real
   play adds to double dummy, 2% at close decisions, and the learning curve has flattened. (Section 4.)
6. **Reading is where the headroom is, and the model's fidelity limits it.** With Gen 6 itself as the model of
   every past play, the plays hold 3.4 nats of evidence about where one honour is at trick 6; v4.1 reads 0.9 and
   points the wrong way for 32% of honours. None of it is double-dummy logic: it is which of several level cards
   this bot plays from this hand. Turning it into a reader needs a model that reproduces the bot and a way to move
   through layouts by that model's likelihood; rescoring a net-drawn pool recovers little. (Section 5.)

What this says about the formula: the student has leverage where it is used as a model of the other seats' cards,
and none where it is asked to out-evaluate the search at close decisions. v4 to v4.1 improved it as a player (26%
fewer tricks given up) much more than as a model (exact card 72.9% to 74.9%; the bot repeats its own card 92%).

## Units and method

- **Fork pair.** At a decision of a played table the bot played card A; the collector also played a forced card B
  out with the same bots. "B really cost" is A's result minus B's on the true deal, for the decider's side. The
  recorded gap is the search's estimate of that at the table. Pairs are drawn in three bands of the recorded gap (up
  to 1/8, 1/8 to 1/2, above) with a recorded probability; weighting by its inverse gives totals over every
  (decision, other card) of one side at one table.
- **Tricks a side at one table.** What a rule gains over the bot's card, summed over one side's decisions at one
  table. A bot plays one side at each of a board's two tables, so two of these make a board; at the fork pairs' 3.6
  IMPs a trick, 0.1 tricks a side is about 0.7 IMPs a board. The IMP figure is rough.
- **The ceiling.** For a fork pair, both cards are played out to trick 13 on layouts drawn from the decider's own
  beliefs, with the real bot (Gen 6, 32 layouts) at all four seats. The mean over layouts is what B costs in
  expectation when everyone plays on as the bots do. It replaces the one real deal (sd about 0.8 tricks a pair) as
  the measure of a rule. A rule is never scored on a layout it chose with: either the ceiling's layouts are split,
  or the rule's layouts come from another seed.
- **Share / coefficient.** In `realized cost = k + b x gap + c x correction`, c is how much of a simulator's
  correction (played-out value minus double dummy on the same layouts, A minus B) shows up in real results.
- Errors are standard errors with deals as the unit.
- Data: 1,561 fresh 6-32 self-play boards (feed `arena-gen6-fast-selfplay-20261111-19bbdce5-feed`, episodes 5214 to
  6774, completed 12 Nov 03:58 to 06:32 UTC, not in v4.1's training set), and for section 4 the feed's earlier
  boards and the independent self-play feed.

## 1. The ceiling: the real bots as the simulator

`scripts/plan_ceiling.py`, `scripts/plan_headroom.py`.

**Tricks 3 to 6** (first 500 boards: 1,298 pairs, 484 deals, 16 layouts a pair).

| | |
|---|---|
| B really cost, true deal | +0.384 +- 0.023 |
| Mean of the playouts over the layouts | +0.389 +- 0.013 |
| Double dummy on the same layouts | +0.458 |
| Real cost on the playout mean, slope | 0.90 (1.0 would show as 0.86 at 16 layouts) |
| Sd of (playout - double dummy), layout luck removed: gaps to 1/8, to 1/2, above | 0.11, 0.17, 0.27 |
| Per card and layout: real result equals double dummy; decider worse; better | 0.78; 0.12; 0.10 |

Split so that no layout both chooses and scores (rule: recorded gap + trust x correction < 0, margin 0.25):

| Layouts that choose | Trust 0.25 | Trust 0.5 | Trust 1.0 |
|---|---|---|---|
| 4 of 16 | -0.000 +- 0.018 | -0.020 +- 0.034 | -0.097 +- 0.044 |
| 8 of 16 | +0.014 +- 0.015 | +0.030 +- 0.035 | -0.041 +- 0.045 |
| 12 of 16 | +0.030 +- 0.021 | +0.061 +- 0.045 | +0.045 +- 0.052 |

A model of the same data (the true expected cost of B taken as normal within bins of the recorded gap; gaps above
one trick left out; errors from resampling deals). This is a model, not a measurement, and it sums over every other
card, so it is an upper bound:

| Knowing the expectation exactly | 8 layouts | 16 | 32 | 64 | 128 |
|---|---|---|---|---|---|
| 0.19 +- 0.05 | 0.02 +- 0.02 | 0.05 +- 0.03 | 0.09 +- 0.04 | 0.12 +- 0.05 | 0.15 +- 0.05 |

Five sixths of it sits at recorded gaps up to 0.25 (8.4 of the 23 pairs a side has at these tricks). By trick the
direct figure is nothing at tricks 3 and 4 and +0.04 +- 0.02 (trick 5), +0.01 +- 0.01 (trick 6) at trust 0.5.

**Tricks 7 to 12** (all 1,561 boards: 2,802 pairs, 1,347 deals, up to 32 layouts from the deal list). Half of a
pair's layouts choose, half score, margin 0.25:

| Trust | Tricks a side |
|---|---|
| 0.25 | +0.036 +- 0.012 |
| 0.5 | +0.049 +- 0.014 |
| 0.75 | +0.048 +- 0.014 |
| 1.5 | +0.041 +- 0.015 |

Scored by the real deals instead (every layout of a pair chooses; the noisier, independent measure): +0.097 +- 0.045
at trust 0.75 and margin 0.25, +0.068 +- 0.037 at margin 0.125. At tricks 3 to 6 the same check gives +0.056 +- 0.055
(trust 0.25, 16 layouts), at tricks 5 to 6 alone +0.060 +- 0.045.

By trick at trust 0.75: trick 7 +0.031 +- 0.012, trick 8 +0.010 +- 0.006, trick 9 +0.009 +- 0.004, later nothing.
Declaring +0.021 +- 0.007, defending +0.029 +- 0.012. Margin 0.125 gets +0.041 of it. On the first 500 boards alone
(942 pairs, 16 layouts) the figure was +0.026 +- 0.012; on the other 1,061 (2,048 pairs, 32 layouts) +0.060 +- 0.019.

**Tricks 1 to 2:** *pending* (`ceilT12` on azure5).

**A 64-layout ceiling for close decisions at tricks 3 to 6**, to check the model's layout curve directly: *pending*.

**Cards the search rates exactly level.** The gap forks above contain none (the smallest recorded gap is above zero),
so none of these figures covers the choice among level cards, which the bots make with a net. The collector's tie
forks (the card another selector would have played from the same search) are the data for it; a ceiling on them,
equivalent cards left out, is *pending* (`ceilTies`). The played test does re-value level cards.

Examples of what the ceiling finds (`scripts/plan_examples.py`: real playouts say the other card is better by more
than two standard errors): dummy cashing a side king at trick 5 in 3S where a trump first is 0.75 +-
0.21 better; a defender with KQ63 of trumps ducking where the king is 0.56 +- 0.16 better; declarer in 4H taking a
club finesse where drawing the last trump is 0.50 +- 0.20 better. Late in the hand: a defender in 3NT at trick 7
discarding from Q6 where a club from AJ6 is 0.91 +- 0.21 better; a defender in 5H at trick 7 playing the queen from
QT954 on the jack where the ten is 0.71 +- 0.14 better; declarer in 1NT at trick 9 leading a club where cashing the
spade king first is 0.47 +- 0.11 better. Double dummy rates each pair level or nearly so.

## 2. Simulated seats: what the playouts are worth by net and by seat

`scripts/plan_bench.py`, `scripts/plan_report.py`, `bridge_harness/plan_rollout.py`.

Seat types: `top` the net's likeliest card; `blend` the net's log-probability minus ten times its gap head; `hyb3`
the solver's choice among the net's three likeliest cards over three layouts the seat believes in (most likely by
the net's holder head); `map` the solver's card for the single most likely layout.

**On the real deal** (tricks 3 to 6; share c of the correction in the forced card's real cost).

| Seats, 32 layouts, to trick 13 | Share | Pairs |
|---|---|---|
| v0 top | +0.093 +- 0.027 | 3,969 |
| v2 top | +0.172 +- 0.034 | |
| v4 top | +0.157 +- 0.038 | |
| v4.1 top | +0.257 +- 0.042 | |
| v4 blend | +0.267 +- 0.039 | |
| v4.1 blend | +0.277 +- 0.045 | |
| v4.1 top, cut after 3 tricks then double dummy | +0.232 +- 0.046 | |
| v4.1 top | +0.337 +- 0.060 | 2,042 |
| v4.1 map | +0.329 +- 0.072 | |
| v4.1 hyb (one believed layout) | +0.372 +- 0.075 | |
| v4.1 hyb3 | +0.512 +- 0.068 | |
| real Gen 6 (16 layouts) | +0.71 +- 0.17 (first 486 pairs) | |

Paired on the same pairs: v4.1 top minus v4 top +0.101 +- 0.036; v4.1 blend minus v4 blend +0.010 +- 0.041; hyb3 minus
top +0.175 +- 0.058; hyb3 minus hyb +0.140 +- 0.049. Playing to trick 13 or cutting at three tricks is the same: the
double-dummy leaf was not the limit (my first hypothesis; wrong).

**Scored by the ceiling** (629 pairs with a recorded gap up to 0.25, 390 deals; the simulators' layouts from another
seed). "Explains" is the part of the variance of the real playout mean left by double dummy that the correction
accounts for, layout luck removed. Gain is the rule recorded gap + 0.25 x correction < 0.

| Seats | Layouts | Coefficient | Explains | Tricks a side |
|---|---|---|---|---|
| v0 top | 512 | 0.05 | 0.03 | -0.045 +- 0.035 |
| v4 top | 512 | 0.14 | 0.13 | -0.012 +- 0.027 |
| v4.1 top | 512 | 0.17 | 0.15 | +0.032 +- 0.019 |
| v4.1 blend | 512 | 0.24 | 0.29 | +0.029 +- 0.029 |
| v4.1 hyb3 | 128 | 0.36 | 0.44 | +0.034 +- 0.020 |
| v4.1 top | 32 | 0.28 (all gaps) | | +0.013 +- 0.029 |
| v4.1 hyb3 | 32 | 0.46 (all gaps) | | +0.010 +- 0.016 |

Above trust 0.5 every net-only row loses (v4.1 top at trust 1: -0.18 +- 0.07). Double dummy on 512 layouts in place
of the table's 32, with no playouts: -0.007 +- 0.024. The net's own heads say nothing about the correction: v4.1's
log-probability difference and gap-head difference together explain 0.02 of it at gaps up to 1/8.

`v41:hyb5`, `v41:hyb8` at 128 layouts: *pending* (`wide3` on azure5).

## 3. Plans, layout families and key variables

`bridge_harness/plan_families.py`, `scripts/plan_family_study.py`, `scripts/plan_matrix_study.py`, and the planner in
`bridge_harness/plan_rollout.py` (a plan is a family of layouts to play for until the cards seen refute it; a
matrix value[card, plan, layout] is filled by playouts in which the decider's side follows the plan).

- At 697 decisions with at least two candidate cards (tricks 2 to 6, 128 layouts): 3.8 candidates a decision; 7.5
  distinct double-dummy outcome patterns, of which 4.2 hold 90% of the weight (median 3).
- Yes/no variables about the first hidden hand ("holds card X" for each unseen card ten or higher, "has at least k
  cards of suit s"), up to three chosen greedily, scored on layouts they were not chosen on: they explain 0.21,
  0.29, 0.33 of the double-dummy swing with one, two, three variables. Of played-out outcomes they explain about
  nothing.
- In the ceiling's data, grouping a pair's 16 layouts by the double-dummy results of the two cards (4.5 groups a
  pair) leaves 74% of the layout-to-layout variance of (real play - double dummy) inside the groups.
- So the families exist and are few, simple variables do not describe them, and they describe the double-dummy
  problem, which the search already solves, not the departures of real play from it.
- The plan matrix machinery runs and is tested; its volume runs (`matrix1`, `matrix2`) were not run. They would
  measure plan choice inside a simulation whose seats explain 15 to 44% of real play (section 2), so I put the
  boxes on the ceiling and the reading instead.

## 4. A head fitted on fork outcomes

`scripts/plan_fork_data.py`, `scripts/plan_fork_fit.py`. Target: what the fork really cost minus the recorded gap.
Inputs: the v4.1 net's decoder activations for the suits of the two cards, its trunk, its own outputs for the
pair, the gap, trick, side. Fit: gradient-boosted trees. Judged on the 8,622 fresh forks and on the ceiling.

| Forks fitted on | Fresh forks: coefficient | Ceiling: coefficient | Explains | Gaps up to 0.25: explains |
|---|---|---|---|---|
| 9,586 | +0.62 +- 0.12 | +0.33 +- 0.12 | 0.016 | 0.002 |
| 19,188 | +0.73 +- 0.12 | +0.54 +- 0.12 | 0.044 | 0.018 |
| 38,461 | +1.16 +- 0.14 | +0.73 +- 0.15 | 0.067 | 0.009 |
| 76,913 | +1.16 +- 0.13 | +0.78 +- 0.14 | 0.073 | 0.018 |

The prediction is real (coefficient near one on deals it never saw) and small (sd 0.08 tricks), and most of it is
there without the activations (0.032 from the scalars alone at 28,868 forks). Rules built on it lose. Not tried: a
head trained through the net, or an order of magnitude more forks.

## 5. Reading: the bot as its own model

`scripts/plan_reading_bound.py`, `scripts/plan_reading_report.py`. One seat of a played 6-32 table at its first
decision of a trick; every earlier card chosen by a hidden hand except the opening lead. "The bot" is Gen 6 run
twice from the view that hand would have had in a candidate layout, read through how it rated the card played (a
card it played 0.965; rated level but another played 0.10; behind by up to 1/32 0.34, 1/16 0.20, 1/8 0.11, 1/4 0.03).
"The net" is v4.1 with floor 0.05, as the bots use it.

**One card's place** (the true layout against the same layout with one card given to the other hidden hand).
Mean log-likelihood ratio in nats; share of cards on which it points the wrong way.

| | Bot | Net | Bot wrong | Net wrong |
|---|---|---|---|---|
| Trick 6: honour, lengths kept (1,293) | +3.43 +- 0.16 | +0.92 +- 0.07 | 0.12 | 0.32 |
| Trick 6: honour and a length (395) | +7.39 +- 0.34 | +2.24 +- 0.15 | 0.03 | 0.18 |
| Trick 6: two small cards of a suit (297) | +1.08 +- 0.12 | +0.20 +- 0.05 | 0.22 | 0.45 |
| Trick 6: a defender's view, honours | +5.69 +- 0.20 | +1.53 +- 0.11 | 0.07 | 0.27 |
| Trick 6: declarer's view, honours | +2.27 +- 0.14 | +0.76 +- 0.07 | 0.14 | 0.31 |
| Trick 4: honour, lengths kept (1,210) | +2.02 +- 0.10 | +0.61 +- 0.06 | 0.12 | 0.37 |
| Trick 4: honour and a length (310) | +4.21 +- 0.28 | +1.59 +- 0.16 | 0.08 | 0.21 |

(305 seats, 120 deals at trick 6; 211 seats, 80 deals at trick 4.) By rank at trick 6, bot / net: A 6.3 / 1.7, K 5.3 /
1.5, Q 4.7 / 1.3, J 3.4 / 1.1, T 3.0 / 0.9. Of a defender's evidence, partner's plays alone give 1.8 / 0.6.

**A cheaper stand-in for the bot** (the same search on fewer layouts, run twice, read through how a card so rated
turned out to be the one really played; the same 305 seats). The mean evidence stays large but it is wrong more
often; the last column is the log-probability the true holder gets from that evidence at even prior odds (no
information: -0.693), which is the figure to compare.

| Model of the bot | Honour, lengths kept: evidence | Wrong | Log-probability | Honour and a length: log-probability |
|---|---|---|---|---|
| Gen 6 itself, 32 layouts | +3.43 | 0.12 | -0.287 | -0.088 |
| The search on 8 layouts | +4.31 | 0.18 | -0.487 | -0.104 |
| The search on 4 layouts | +3.26 | 0.20 | -0.551 | -0.220 |
| v4.1 net | +0.92 | 0.32 | -0.552 | -0.388 |

So where a card sits within a suit is only read by something close to the bot itself; lengths survive a cheap model.

**Does a bot whose ties its own net breaks read better with that net?** Little. Net-only runs of the same bench
(`--net-only`), policy v4, trick 6, honour with lengths kept: Gen 7 self-play (`7s-32`, ties broken by v4; 601 seats)
evidence +0.91 +- 0.04, wrong 0.29, log-probability -0.523 +- 0.011; Gen 6 self-play (ties broken by the Gen 5 selector;
521 seats) +0.84 +- 0.05, 0.31, -0.555 +- 0.014. Two small cards exchanged: +0.33 against +0.25.

**The whole layout** (82 seats, 34 deals; a pool of about 690 distinct layouts from Gen 6's beliefs; the bot is run
on 50 drawn by the net's reading and its reading of the pool follows by importance weights).

| | Net | Bot |
|---|---|---|
| True layout's log-weight gained against the pool | +0.94 +- 0.15 | +2.67 +- 0.24 |
| Log-probability of a play really made | -0.76 | -0.15 |
| Per unseen honour, true holder, true layout out of the pool (prior -0.553) | -0.447 | -0.409 (reweighting the net's 50) |

Gen 6 re-run from the true hand repeats its card in 0.923 of runs. The card played is double-dummy best in the
true layout 0.969 of the time and in the candidates 0.959; a reading by double-dummy consistency gains +0.35 nats
where the net gains +0.94 and adds nothing to the net.

Not measured: the posterior of a reading with the bot as the model. A first random walk over layouts (card
exchanges, 150 steps, three seats) reached the true layout in some chains and stuck elsewhere in others, and in one
seat two layouts unlike the true one explained the plays 2 nats better. The one-card figures are evidence at the
true layout.

Trick 9, and the posterior by tempered walks over layouts (`--chain`): *pending* (azure5).

## 6. Played test

`scripts/plan_match.py`, `configs/plan-bots.json` (Gen 8 prototype branch). `pr75-32-v41` is `7s-32-v41` (Gen 7.1)
that, at tricks 7 to 12 when a second card is within 0.25 of its best, plays its best three out on 16 of its layouts
with Gen 7 itself (no playouts) at every seat and adds 0.75 of the correction (`bridge_harness/plan_player.py`,
seat `gen7`). Against `7s-32-v41`, 1,600 fresh random deals, seed 131, duplicate, no forks: *pending* (azure2).

The bench figure it tests (+0.048 +- 0.014 tricks a side) is for Gen 6 among Gen 6 with Gen 6's beliefs. Gen 7
reads the play from trick 7, which the bench does not include.

## Limits

- Everything in sections 1 to 5 is Gen 6 (6-32) self-play. Gen 7's reading and tree are not in the ceiling.
- The ceiling measures one changed card followed by the bots' own play. A policy that also plays differently later
  collects one such advantage at each of its own decisions, so the sum of these headrooms bounds what any cardplay
  policy with Gen 6's beliefs can gain against Gen 6; a policy with better beliefs is not bounded by it.
- The "exact knowledge" row is a model and an upper bound. The direct figures are the split tables.
- The reading figures are for a bot read by an exact copy of itself. Against BEN, or a bot that plays its level
  cards at random, the evidence in section 5 is not there.
- No result here has been played except the pending match.

## Reproduce

Outputs are on `transfer/plan-leverage-azure2-20261112` and `transfer/plan-leverage-azure5-20261112` (rows as
`*.json.gz`, logs, the job queue with every command). Tests: `python -m unittest discover -s tests -p
"test_plan_rollout.py"` from the repository root.
