# G9-S9: what knowing one of partner's cards could unlock for the defence (g9, 13 November 2026)

Gen 9 task G9-S9, for [the SiD plan](../../docs/gen9/sid-integration.md), section 2.4. A bound computed offline on
recorded play; no signal is modelled and nothing was played.

## Question

`DESIGN.md` of the conditional claims leaves a defender's own conditional lines ("we beat it if partner holds X") as
a game no solver plays yet. Partner's signals are how a defender learns whether partner holds X. Before building
anything, how much could perfect knowledge of one partner card be worth, in the one defensive quantity 8X already
measures: whether the defender's card hands declarer a guaranteed line?

## Method

- **Positions.** Ten board shards of four Gen 8 feeds (`arena-gen8-azure1-feed`, `gen8independent`,
  `gen8codexcandidate`, `gen8s3azure1`; cached 07:14 UTC), common and native tables, 2,513 tables. The first decision
  of a defender holding 8 cards, and holding 7, with the contract not yet settled and at least two legal cards: 4,577
  positions.
- **Layouts.** 48 the defender cannot rule out, uniform with hand sizes and show-outs kept (as 8X's defender rule
  samples them).
- **Hand-overs.** For each legal card and layout, whether declarer then holds a guaranteed line from its own view
  (8X's `Finder.handovers`, `sure_cpp` built from `research/sure-trick-table-20261112` at 2e6ed6d, on the X9 branch
  `feature/gen9-x9`).
- **Quantities.** p0: the hand-over probability of the defender's best card knowing only its view. For each unseen
  honour (ten to ace): the same when the defender is told whether partner holds it, best card on each side; the bound
  is the best honour's reduction. Against it, the reduction from knowing the whole layout (the most any information
  could give).

Script: `s9_bound.py`. One line a position: `positions.jsonl.gz`.

## Result

| Positions | Count | Hand-over probability of the best card (p0) | Card choice changes the odds | Lowered by knowing the layout | Lowered by knowing one partner honour | One honour lowers it by 0.10 or more |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All | 4,577 | 0.297 | 8.2% | 0.0042 +- 0.0003 | 0.0032 +- 0.0002 | 30 |
| Games, slams, doubled | 2,624 | 0.316 | 6.1% | 0.0037 +- 0.0004 | 0.0028 +- 0.0003 | 18 |
| Undoubled partscores | 1,953 | 0.271 | 11.0% | 0.0048 +- 0.0004 | 0.0038 +- 0.0003 | 12 |
| 8 cards | 2,324 | 0.258 | 8.7% | 0.0043 +- 0.0004 | 0.0032 +- 0.0003 | 14 |
| 7 cards | 2,253 | 0.336 | 7.6% | 0.0040 +- 0.0004 | 0.0032 +- 0.0003 | 16 |

- In 82% of positions some layouts let declarer claim whatever the defender plays (p0 averages 0.297), but the
  defender's card changes the odds in only 8.2% of them.
- Knowing the whole layout would lower the hand-over probability by 0.004 a position on average (0.051 where the
  choice matters). Knowing one partner honour gets 77% of that.
- One honour lowers the odds by 0.10 or more in 30 of 4,577 positions (0.7%).

## What it means for the plan

At these points of the hand (the first defender decision with 8 and with 7 cards), what the defence gives declarer
is mostly settled by declarer's own view, not by the defender's card. So perfect signalling of one card is worth
little here in hand-over terms, and building defenders' conditional lines on partner's signals gets low weight: no
new solver now. Signals still matter for the defence's own play (E9-6, E9-4), which this does not measure.

## Limits

- Hand-over avoidance only. A defender's own guaranteed defeat ("we beat it if partner holds X") is a different
  question that needs a solver for two hands that cannot see each other.
- Uniform layouts, not the defender's beliefs from the auction and the play.
- Two decision points per table; earlier decisions (the opening lead, tricks 2 to 5) are not covered.
- Probabilities, not IMPs.
