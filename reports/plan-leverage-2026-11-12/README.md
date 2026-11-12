# Plan-level search and leverage, 12 November 2026

Research report, branch `research/plan-leverage-20261112` (and the same commits on the Gen 8 prototype as
`research/plan-leverage-g8-20261112`, which also holds the match wrapper and bot settings). Nothing here is launched or
merged. Work in progress: the items marked *pending* are still running as this is written.

**Correction, 16:40 UTC.** Until then every "tricks a side" figure divided a total by the tables that had a sampled
pair in the trick range, not by the tables read. A table with no such pair adds nothing to the total and still
counts. The figures below are recomputed: tricks 3 to 6 change by 3%, tricks 7 to 12 fall by 12% (the late rule
+0.048 became +0.043), the simulated-seat rules of section 2 fall by 22% (v4.1 +0.032 became +0.025). No sign and no
ordering changed.

## The question

Max, 06:46 UTC: the tree does not capture as much gain from an improved net as expected. The formula should be:
the student is worse than the teacher, a harness on the student inverts that, and training on the new teacher makes
a better student. Explore plan-based approaches: whole plans against layout families, minimax over two or three
key variables instead of 32 layouts, nets that work out what is going on.

## Answers

**In short.** Against these bots and with their beliefs, the choice of card has little left in it: about 0.10 tricks a
side at tricks 3 to 6 and 0.07 at tricks 7 to 12 if every card's real expectation were known exactly, 0.02 in level
cards late. The bot simulating itself from trick 7 collects 0.043 of the late part, and in a played test it is worth
+0.175 +- 0.035 IMPs a board at about six times the CPU. Nothing I tried gives the net more leverage: it reaches the
table as a predictor of the bots' cards, and that predictor improves slowly with data. Plans as layout families, a
head fitted on outcomes and tables of play kinds add nothing measurable. The opening lead and tricks 1 to 2 are being
measured.

1. **Why the tree shows no gain from a better net.** At tricks 3 to 6, knowing exactly what every other card would
   bring with the bots playing on is worth about 0.10 tricks a side at one table (a fit gives 0.140 +- 0.047 and a
   simulation of the fit says it errs high by 0.03 to 0.04 at this sample size; section 1).
   That is everything a better judge of cards could add there with Gen 6's beliefs. A simulator collects the part
   its picture of the other seats explains and its layouts resolve. One layout's played-out result differs by 0.6 to
   0.8 tricks, and what real play adds to double dummy has an sd of 0.11 to 0.17 at close decisions, so on the
   tree's 8 layouts the estimate is noisier than the thing estimated. The real bots themselves as the simulator,
   choosing on 12 layouts and scored on 4 others, gain +0.030 +- 0.021.
2. **The order is the one the formula wants; the size is not.** Net-only playouts on 512 layouts, scored against
   the real bots' playouts: v0 -0.035 +- 0.027, v4 -0.009 +- 0.021, v4.1 +0.025 +- 0.015, v4.1 with a small search at
   each simulated seat (128 layouts) +0.026 +- 0.015 tricks a side. The nets explain 3%, 13% and 15% of what real
   play adds to double dummy; the small search 44%. (Section 2.)
3. **Where look-ahead does pay: tricks 7 to 12 with the bot as its own simulator.** From the deal list a playout by
   the real bot costs 0.08 s. Half of the list's layouts choose, the other half score: +0.043 +- 0.012 tricks a side
   (2,990 forks, 1,561 boards), mostly at trick 7; exact knowledge there would be worth 0.07. Played against Gen 7.1:
   +0.175 +- 0.035 IMPs a board over 1,600 boards (98 boards won, 24 lost), at roughly six times the bot's CPU.
   (Sections 1 and 6.)
4. **Plans as layout families do not carry it.** About four double-dummy outcome families hold 90% of the weight at
   a decision, but three simple variables explain a third of the double-dummy swing, and grouping layouts by
   double-dummy outcome explains a quarter of where real play departs from double dummy. (Section 3.)
5. **A head fitted on fork outcomes is not a lever at this scale.** On 77,000 forks it explains 7% of what real
   play adds to double dummy, 2% at close decisions, and the learning curve has flattened. (Section 4.)
6. **The plays hold far more than the net reads, and it is expensive to get.** With Gen 6 itself as the model of
   every past play, the plays hold 3.4 nats of evidence about where one honour is at trick 6; v4.1 reads 0.9 and
   points the wrong way for 32% of honours. None of it is double-dummy logic: it is which of several level cards
   this bot plays from this hand, so it exists only against a bot the reader can run. p41's bench prices a reader
   at that level at +0.14 to +0.19 double-dummy tricks a board over v4.1's reading (0.07 to 0.10 a side), and such
   a reader costs a full search for every candidate layout and past play. The same search on 8 layouts keeps
   suit lengths and loses where a card sits. (Section 5.)
7. **A better net reaches the table only as a model of the bots' cards, and that improves slowly.** From v4 to
   v4.1, 2.3 times the data bought 0.04 of log-loss, 0.04 nats of reading and 0.02 of simulator share. (Section 7.)
8. **Not yet measured:** the opening lead and tricks 1 to 2 (ceilings running tonight), level cards at tricks 3 to 6.

What this says about the formula: the student has leverage where it is used as a model of the other seats' cards,
and none where it is asked to out-evaluate the search at close decisions. v4 to v4.1 improved it as a player (26%
fewer tricks given up) much more than as a model (exact card 72.9% to 74.9%; the bot repeats its own card 92%).

In one unit (tricks a side at one table, Gen 6 among Gen 6; a board is two sides):

| Lever | Available | Collected so far |
|---|---|---|
| A different card at tricks 3 to 6, same beliefs | about 0.10 (fit 0.14 +- 0.05, less its error of 0.03 to 0.04) | Gen 7's tree 0.01 to 0.03 (p41: +0.046 +- 0.014 tricks an override, about 0.3 overrides a side); net playouts on 512 layouts 0.025; real playouts on 12 layouts 0.03 to 0.06 |
| A different card at tricks 7 to 12 | 0.07 +- 0.01 (fit) | 0.043 +- 0.012 with the bot as its own simulator |
| Level cards, tricks 7 to 12 | 0.02 | 0.01 |
| Opening lead, tricks 1 to 2, level cards at tricks 3 to 6 | not measured yet | |
| Reading the play (p41's bench, double-dummy tricks) | 0.37 if told the deal | 0.10 with v4.1; 0.07 to 0.10 more with the bot as the model |

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
| 4 of 16 | -0.000 +- 0.017 | -0.019 +- 0.033 | -0.094 +- 0.043 |
| 8 of 16 | +0.014 +- 0.015 | +0.029 +- 0.033 | -0.040 +- 0.044 |
| 12 of 16 | +0.030 +- 0.021 | +0.059 +- 0.043 | +0.044 +- 0.050 |

**How much is there in all.** A fit of the same data. On one layout the other card costs a trick, gains one, or
(mostly) changes nothing, so a pair is described by two chances; their distribution over the pairs of a bin of the
recorded gap is fitted freely (maximum likelihood from each pair's counts, gaps above one trick left out, errors
from resampling deals). The columns are the best possible use of n layouts of real playouts.

| Knowing the expectation exactly | 8 layouts | 16 | 32 | 64 | 128 |
|---|---|---|---|---|---|
| 0.140 +- 0.047 | 0.041 +- 0.023 | 0.082 +- 0.032 | 0.116 +- 0.040 | 0.133 +- 0.045 | 0.138 +- 0.047 |

This is a fit, not a measurement, and at this sample size it errs high: pairs drawn from the fitted distribution
with the real layout counts and fitted again come out 0.03 to 0.04 above what was put in, in every column (`--fit-check`:
exact +0.031 +- 0.009 in one run of 24, +0.041 +- 0.007 in another). So read the row as about 0.10 for exact knowledge,
0.05 on 16 layouts and 0.09 on 32. The late-trick and level-card fits below show no such error (+0.002 +- 0.002 and
-0.001 +- 0.001): they have more pairs. One check against a measurement is possible: playing the other card whenever
8 layouts' playouts favour it is worth -0.127 by the fit and -0.168 +- 0.057 in the split. An earlier version took the true cost as normal in
each bin: 0.182 +- 0.050 exact and 0.085 at 32 layouts. On the level cards below, where almost every pair is exactly
level in truth, the normal version is five times too high and the count fit agrees with the split, so the count fit
is the one reported. Choosing with hindsight on all 16 layouts gives 0.44 +- 0.06, an upper bound that is mostly
noise. Seven eighths of the fitted 0.140 sits at recorded gaps up to 0.25 (8.1 of the 22 pairs a side has at these
tricks). By trick the split gives nothing at tricks 3 and 4 (-0.017 +- 0.033), +0.044 +- 0.022 at trick 5 and +0.014 +-
0.011 at trick 6 (12 of 16 choose, trust 0.5). Fitted trick by trick (fewer pairs each, so each errs higher still):
0.062, 0.052, 0.091, 0.020 at tricks 3, 4, 5, 6.

**Tricks 7 to 12** (all 1,561 boards: 2,990 pairs, 1,378 boards with one, up to 32 layouts from the deal list). Half
of a pair's layouts choose, half score, margin 0.25:

| Trust | Tricks a side |
|---|---|
| 0.25 | +0.033 +- 0.010 |
| 0.5 | +0.041 +- 0.011 |
| 0.75 | +0.043 +- 0.012 |
| 1.5 | +0.037 +- 0.013 |

The fit above gives 0.071 +- 0.014 for exact knowledge, 0.047 on 16 layouts and 0.057 on 32; hindsight on all layouts
(an upper bound with no model) 0.087 +- 0.014.

Scored by the real deals instead (every layout of a pair chooses; the noisier, independent measure): +0.086 +- 0.040
at trust 0.75 and margin 0.25, +0.060 +- 0.032 at margin 0.125. At tricks 3 to 6 the same check gives +0.055 +- 0.053
(trust 0.25, 16 layouts), at tricks 5 to 6 alone +0.059 +- 0.044.

By trick at trust 0.75: trick 7 +0.028 +- 0.011, trick 8 +0.011 +- 0.005, trick 9 +0.008 +- 0.003, later nothing.
Declaring +0.018 +- 0.007, defending +0.025 +- 0.010. Margin 0.125 gets +0.035 of it. On the first 500 boards alone
(942 pairs, 8 of 16 layouts choosing) the figure is +0.014 +- 0.009; on the other 1,061 (2,048 pairs, 16 of 32) +0.056
+- 0.017.

**The opening lead.** On the real deals (6,632 lead gap forks of 6-32 self-play, 16,866 leads): a forced lead the
search rated up to 1/8 behind cost +0.042 +- 0.018 tricks, 1/8 to 1/2 behind +0.211 +- 0.018 (recorded gap 0.293),
further behind +0.628 +- 0.033 (0.752). Real cost over recorded gap is 0.75 +- 0.04 at the lead, 0.80 to 0.83 at tricks
1 to 6 and 0.88 to 0.96 from trick 7.

By kind of lead (`scripts/plan_lead_scan.py`, `scripts/plan_lead_rule.py`, `scripts/plan_lead_kinds.py`). Real play
shrinks every gap the search sees (at the lead, real cost = 0.84 +- 0.05 of the recorded gap), and without a term for
that the shrinkage shows up as an effect of whatever kinds are mostly played or mostly forced. With the term in, what
is left by kind (+ means the search flatters the kind; the two columns are different deals and different measures:
the real deal's result against the recorded gap, and the playouts against double dummy on the same 16 layouts):

| Kind | Real deals, 6,632 forks | Ceiling so far, 311 forks | The search leads it |
|---|---|---|---|
| Singleton | +0.044 +- 0.042 | +0.106 +- 0.034 | 7% |
| An ace | +0.035 +- 0.024 | +0.086 +- 0.031 | 21% (24% against suit contracts) |
| A trump | +0.055 +- 0.023 | -0.001 +- 0.031 | 7% |
| Small from small cards | -0.010 +- 0.025 | -0.016 +- 0.030 | 16% |
| An honour, not touching | -0.012 +- 0.025 | -0.006 +- 0.025 | 10% |
| Small from a doubleton | -0.022 +- 0.031 | -0.050 +- 0.041 | 10% |
| Top of touching honours | -0.050 +- 0.031 | -0.033 +- 0.041 | 11% |
| Small from an honour | -0.040 +- 0.018 | -0.085 +- 0.022 | 19% |

An ace against a small card from an honour: the search is off by +0.075 +- 0.029 on the real deals and +0.170 +- 0.038
in the ceiling. Both say double dummy flatters the ace (the defence that follows is never as good as double dummy's)
and is hard on the small card from an honour (declarer does not always guess); they disagree on the size. A rule that
adds the table to the search's gaps (fitted on half the deals, scored on the other half through the forks, switching
only to a card the search rated behind) changes 8% to 15% of the leads and gains +0.005 +- 0.003 to +0.005 +- 0.004
tricks a side: not distinguishable from nothing. The same table for every play after the lead (85,535 forks, 28
kinds of play a side such as "second hand takes the trick" or "lead low from an honour"; `scripts/plan_play_scan.py`,
`scripts/plan_play_rule.py`) gives a rule worth -0.004 +- 0.004 a side. So tables of play kinds are not a lever either.

The lead's ceiling (both leads played out by Gen 6 on 16 layouts from the leader's beliefs; 311 of about 690 forks so
far): the forced lead costs +0.21 +- 0.03 by the playouts where double dummy on the same layouts says +0.27; one
layout's played-out difference between two leads has an sd of about one trick, so 16 layouts say little about one
pair; 12 of 16 layouts choosing gains +0.04 +- 0.04 a side at trust 0.25 and loses at higher trust. The amount
available: *pending* (`ceilLead`, azure5, about 19:50 UTC).

**Tricks 1 to 2 after the lead:** *pending* (`ceilT12`, azure2, overnight).

**A 64-layout ceiling for close decisions at tricks 3 to 6** (recorded gap up to 0.25), to check the fit on other
boards and more layouts: 94 pairs on 80 boards so far. 48 of 64 layouts choosing gains +0.04 +- 0.04 to +0.07 +- 0.06
by rule; hindsight on all 64 layouts, the upper bound, 0.20 +- 0.06. (The fit on 94 pairs, 0.134 +- 0.051, is too few
pairs to trust.) 300 more boards *pending* (`ceil64b`).

**Cards the search rates exactly level.** The gap forks above contain none (the smallest recorded gap is above zero),
so none of the figures above covers the choice among level cards, which the bots make with a net. The collector's
tie forks are the data: the card played against the card the reference selector would have played from the same
search, equivalent cards left out. At tricks 7 to 12 (4,356 pairs on 566 boards, sandbox): the other card really
cost +0.001 +- 0.002; the playouts say +0.0025 +- 0.0010; half the layouts choosing gains +0.009 +- 0.003 tricks a side;
the fit gives 0.024 +- 0.003 for exact knowledge and hindsight on all layouts 0.020 +- 0.004. So late level cards hold
about a fiftieth of a trick a side between these two selectors. Level cards neither selector chose are not in the
data. Tricks 3 to 6: *pending* (`ceilTies`, azure2). The played test does re-value level cards.

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

**Scored by the ceiling** (629 pairs with a recorded gap up to 0.25 on the first 500 boards; the simulators' layouts
from another seed). "Explains" is the part of the variance of the real playout mean left by double dummy that the
correction accounts for, layout luck removed. Gain is the rule recorded gap + 0.25 x correction < 0.

| Seats | Layouts | Coefficient | Explains | Tricks a side |
|---|---|---|---|---|
| v0 top | 512 | 0.05 | 0.03 | -0.035 +- 0.027 |
| v4 top | 512 | 0.14 | 0.13 | -0.009 +- 0.021 |
| v4.1 top | 512 | 0.17 | 0.15 | +0.025 +- 0.015 |
| v4.1 blend | 512 | 0.24 | 0.29 | +0.023 +- 0.022 |
| v4.1 hyb3 | 128 | 0.36 | 0.44 | +0.026 +- 0.015 |
| v4.1 top | 32 | 0.28 (all gaps) | | +0.013 +- 0.029 |
| v4.1 hyb3 | 32 | 0.46 (all gaps) | | +0.010 +- 0.016 |

Above trust 0.5 every net-only row loses (v4.1 top at trust 1: -0.14 +- 0.05). Double dummy on 512 layouts in place
of the table's 32, with no playouts: -0.006 +- 0.019. The net's own heads say nothing about the correction: v4.1's
log-probability difference and gap-head difference together explain 0.02 of it at gaps up to 1/8.

For scale: section 1 puts exact knowledge at these pairs at about 0.09 tricks a side and the best use of 16
layouts of the real bots at about 0.05 (the fit less its error).

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

**Cleaner labels, fewer of them** (`scripts/plan_clean_fit.py`): the ceiling's playout mean in place of one real deal,
five folds by deal. At tricks 7 to 12 (2,990 pairs; the real correction has an sd of 0.12) the scalars explain 0.04
+- 0.01 of it and the activations add nothing (0.03 +- 0.02 with them). At tricks 3 to 6 (1,298 pairs; sd 0.20) the
scalars explain 0.19 +- 0.05, which is mostly that real play shrinks the gap and cannot change a card, and the
activations again add nothing. A few thousand labels cannot say what a head would learn from a hundred thousand; a
bot that runs the late rule produces that many as a by-product (each consultation is a playout mean for up to three
cards), which is the one untried way I see to train a student on this teacher.

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
| Trick 9: honour, lengths kept (432) | +12.2 +- 0.7 | +1.81 +- 0.14 | 0.08 | 0.22 |
| Trick 9: honour and a length (211) | +20.9 +- 1.1 | +3.59 +- 0.27 | 0.00 | 0.10 |

(305 seats, 120 deals at trick 6; 211 seats, 80 deals at trick 4; 206 seats, 80 deals at trick 9, where the true
holder's log-probability from the evidence alone is -0.239 +- 0.049 with the bot and -0.449 +- 0.033 with the net.) By rank at trick 6, bot / net: A 6.3 / 1.7, K 5.3 /
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

**What it would be worth.** p41 priced this on its reading bench (board, 15:25 UTC): adding to v4.1's reading a
fixed bonus for every honour a layout gives to its true holder, sized to match the step above (0.147 an honour better
than the net at trick 6), is worth +0.14 tricks a board in double-dummy tricks on the true deal; sized to the bot's
level, +0.19. p41 notes that this bench has run above matches. A board is two sides, so this is about 0.07 to 0.10
tricks a side: the same size as the look-ahead headroom of section 1, and for a reader that costs one full search for
every candidate layout and past play.

The posterior by tempered walks over layouts (`--chain`): started and stopped after 35 minutes without output (hours
longer than estimated); two short parts are queued behind the played test on azure5. *Pending*, low priority.

## 6. Played test

`scripts/plan_match.py`, `configs/plan-bots.json` (Gen 8 prototype branch). `pr75-32-v41` is `7s-32-v41` (Gen 7.1)
that, at tricks 7 to 12 when a second card is within 0.25 of its best, plays its best three out on 16 of its layouts
with Gen 7 itself (no playouts) at every seat and adds 0.75 of the correction (`bridge_harness/plan_player.py`,
seat `gen7`). Against `7s-32-v41`, 1,600 fresh random deals, seed 131, duplicate, no forks (`match1`, azure2).

Result, 1,600 boards: **+0.175 +- 0.035 IMPs a board** for the candidate. 98 boards won (366 IMPs), 24 lost (86),
1,478 flat. Boards of 10 IMPs or more: 13 for, 3 against; every other board together +0.100 +- 0.019. First half
+0.152 +- 0.055, second half +0.198 +- 0.045. The candidate changes 1.00 cards a board (its opponent's tree 0.61).

Cost: the match ran at 78 CPU seconds a board. On six boards timed in the sandbox two tree-only bots cost 22 CPU
seconds a board together and this pairing 83, so the candidate runs at roughly six times its opponent's CPU. Cheaper
settings save little (same six boards; none played): a margin of 0.125 costs 72; tricks 7 to 9 only with two
candidate cards and that margin, 65; no playouts where every near-best card is rated exactly level, 68
(`pr75m-32-v41`, `pr75c-32-v41`, `pr75n-32-v41`). Half of the consultations are between level cards, and they are the
cheap half.

The bench figure it tests (+0.043 +- 0.012 tricks a side) is for Gen 6 among Gen 6 with Gen 6's beliefs. Gen 7
reads the play from trick 7, which the bench does not include. At the fork pairs' 3.6 IMPs a trick that figure
would be 0.3 IMPs a board; the same rule priced in IMPs from the real deals of the bench gives +0.33 +- 0.35 a board.

`match3`: the same rule on the Gen 8 prototype's card play (`pr75-8p-32-v41` against `8p-32-v41`: the play read from
trick 1 at exponent 1.0, policy v4.1; the arena's `8s-32` has these card-play settings), 1,600 deals, seed 131:
*pending* (azure2, from 18:48 UTC, about 4.3 hours).

`match2`: `pr75x-32-v41` (the late rule, and from trick 5 on 12 layouts at trust 0.5, its tree stopping after
trick 4) against `7s-32-v41` on `match1`'s deals. 199 CPU seconds a board on four boards timed, so about 11 hours:
*pending* (azure2, after `match3`).

## 7. What a better net buys

The nets' own records (model READMEs; log-loss on Gen 6's card, 60,010 test decisions of v0's split; the last row is
on boards that arrived after v4.1's training cut, where v4 has 0.650):

| Net | Training decisions | Log-loss | Nats for the true layout from its reading (g8, p41) | Share as a simulator (section 2) |
|---|---|---|---|---|
| v0 | 0.5 million | 0.920 | +0.49 | 0.09 |
| v2 | 2.0 million | 0.779 | +0.84 | 0.17 |
| v4 | 5.8 million | 0.682 | +0.99 | 0.16 |
| v4.1 | 13.2 million | 0.608 | 0.04 more than v4 | 0.26 |

From v4 to v4.1, 2.3 times the data bought 0.04 of log-loss and 0.04 nats of reading. Gen 6 run again from the same hand
repeats its card 92% of the time; on the plays of the reading bench it gives the card really played a
log-probability of -0.15 where v4.1 gives -0.76. So the bot is far easier to predict than the net predicts it, and
at the present rate data alone closes little of that.

Every channel through which a better net reaches the table is the net as a model of the bots' cards: the reading
(p41: v4.1 over v4, +0.012 +- 0.012 tricks a board), simulated seats (above), and ties (p41: -0.0001 +- 0.0005 tricks
a pair). None of them asks the net to judge a position.

## Limits

- Everything in sections 1 to 5 is Gen 6 (6-32) self-play. Gen 7's reading and tree are not in the ceiling.
- The ceiling measures one changed card followed by the bots' own play. A policy that also plays differently later
  collects one such advantage at each of its own decisions, so to first order the sum of these headrooms is what a
  cardplay policy with Gen 6's beliefs can gain against Gen 6. Two things are outside it: a line that needs two cards
  the bots would not play, each of which looks wrong without the other (not measured; a card that only gathers
  information is inside, because the bots' later play uses what it shows), and better beliefs.
- The "exact knowledge" figures are a fit, corrected at tricks 3 to 6 for an error found by simulating it. The direct
  figures are the split tables; hindsight on all layouts is the only model-free upper bound and it is loose at 16
  layouts.
- The ceiling covers the gap forks (a second card the search rated behind) from trick 3 and, for level cards, one
  other selector's card at tricks 7 to 12. The opening lead, tricks 1 to 2 and level cards at tricks 3 to 6 are
  pending.
- The reading figures are for a bot read by an exact copy of itself. Against BEN, or a bot that plays its level
  cards at random, the evidence in section 5 is not there.
- One result here has been played (`match1`); two more matches are running.

## Reproduce

Outputs are on `transfer/plan-leverage-azure2-20261112` and `transfer/plan-leverage-azure5-20261112` (rows as
`*.json.gz`, logs, the job queue with every command). Tests: `python -m unittest discover -s tests -p
"test_plan_rollout.py"` from the repository root.
