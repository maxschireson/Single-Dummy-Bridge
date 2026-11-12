# Leakage: what our plays tell a reader, and what hiding it would cost (first figures)

12 November 2026, g9. Experiment E9-16, part 1a. A double-dummy proxy on p41's published pools (530 house tables,
21,417 decisions, policy v4, the prototype's settings), not played boards. `leak_first.py` in this folder, with
`scripts/gen8_reading_bench.py` from `feature/gen8-p41-20261112` and the pools of
`transfer/gen8-p41-reading-pools-20261112`.

## What a reader as good as our own net gains from each thing it reads

Tricks a board over no play reading (the auction is read in every row; a board is the four seats of one table):

| Who is reading | Every play | The opponents' plays alone | Partner's plays alone | The opening lead alone |
| --- | ---: | ---: | ---: | ---: |
| Declarer | +0.101 +- 0.020 | +0.061 +- 0.018 | | +0.026 +- 0.011 |
| A defender | +0.084 +- 0.019 | +0.063 +- 0.017 | +0.038 +- 0.014 | -0.014 +- 0.015 |
| Both | +0.185 +- 0.029 | +0.124 +- 0.026 | +0.038 +- 0.014 | +0.012 +- 0.019 |

So our plays give a reader of our own strength about 0.12 tricks a board (0.45 IMPs at 3.6 a trick): 0.06 from our
defenders' plays to declarer, plus the lead, and 0.06 from our declarer's plays to the defenders. Our own defence
gains 0.04 from reading partner. Declarer has no partner who reads it, so everything declarer's plays tell is given
away.

## The defenders' plays: who gains more from them

Max asked (15:03 UTC) for the net of both defenders reading each other against declarer reading the defenders
(`leak_net.py`; the difference is paired by deal):

| | Tricks a board |
| --- | ---: |
| The two defenders reading each other's plays, opening lead included | +0.029 +- 0.016 |
| ... partner's plays after the lead alone | +0.038 +- 0.014 |
| Declarer reading the defenders' plays, opening lead included | +0.101 +- 0.020 |
| ... the plays after the lead alone | +0.061 +- 0.018 |
| ... the opening lead alone | +0.026 +- 0.011 |
| **Net to the defending side of its plays being readable** | **-0.072 +- 0.025** |

The defenders' plays are worth three and a half times as much to declarer as to the defence, about a quarter of an
IMP a board against a declarer who reads as well as our own net. These are house bots, which have no agreed signals:
what partner reads is habit and inference, not a message meant for it.

## What choosing evenly among near-equal cards would cost

The decider's own values are the weighted double-dummy solves of every stored layout. Choosing evenly among the cards
within eps tricks of the best, against choosing among the equal best, on the true deal:

| eps, tricks | Decisions that gain a card to choose from | Mean cards to choose from | Added cost as declarer | As a defender | Both, tricks a board |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 (exactly equal) | | 2.37 | 0 | 0 | 0 |
| 0.02 | 16% | 2.68 | +0.013 +- 0.006 | +0.007 +- 0.004 | +0.020 +- 0.008 |
| 0.05 | 22% | 2.82 | +0.046 +- 0.011 | +0.019 +- 0.008 | +0.065 +- 0.013 |
| 0.1 | 27% | 2.99 | +0.094 +- 0.017 | +0.059 +- 0.013 | +0.153 +- 0.022 |
| 0.2 | 33% | 3.21 | +0.211 +- 0.026 | +0.171 +- 0.021 | +0.381 +- 0.034 |
| 0.3 | 37% | 3.39 | +0.381 +- 0.036 | +0.328 +- 0.031 | +0.709 +- 0.048 |

- At 71% of decisions two or more cards are rated exactly equal best. Choosing among those is free.
- The bot's small gaps are real: a card it rates 0.02 worse costs about 0.02 on the true deal. There are many such
  decisions, so randomizing all of them within 0.05 tricks costs 0.065 tricks a board, half of everything a reader
  gains from our plays, and within 0.1 costs more than all of it.

So randomizing has to start with exact equals, and anything beyond them has to be confined to kinds of decision
where one play tells a lot. Which those are, and how much of the 0.12 sits in the choice among equals, is parts 1b
to 1d of the experiment.

## How many of our cards are one of several equal cards

`equal_cards.py`. Of the 51 cards a table plays after the opening lead, 40.4 are choices. "Equal best" means rated
exactly equal by the weighted solves of every stored layout, which with a few hundred layouts means the cards do the
same in every one of them.

| Whose card | Choices a table | Legal cards | Two or more equal best | ... all touching cards | ... different cards among them | Cards in the equal-best set |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Declarer's own hand | 10.8 | 5.16 | 68% | 28% | 40% | 2.36 |
| Dummy | 10.4 | 4.63 | 71% | 25% | 46% | 2.39 |
| A defender | 19.3 | 4.36 | 72% | 27% | 46% | 2.37 |
| All | 40.4 | 4.64 | 71% | 26% | 45% | 2.37 |

- 28.6 of the 51 cards (56%) are played with two or more cards equal best: 10.7 where the equal cards are all
  touching, 18.0 where they include different cards (small cards of different suits, or cards separated by one that
  does not matter).
- Today the policy net picks among them (`tie_break: net`, `exploration: 0`), so the card is a fixed function of the
  hand that a reader with the same net can follow.
- **Double dummy, choosing among them at random costs nothing**: on the true deal the equal-best cards cost exactly
  the same at every one of those decisions (27.1 a table where the card played was one of them).
- What it costs in real play is not known. The Gen 8 session's matches say the rule matters: a bot that always plays
  the highest of equal cards loses 0.45 +- 0.12 IMPs a board to Gen 7. Its calibration also found that against a bot
  that plays a random card of equals the best weight for our reading falls from 1.0 to 0.25, which is the evidence
  so far that most of what the net reads is the choice among equals.

The engine already has the setting: `exploration` is the probability of a random one of the tied cards in place of
the net's pick. Bots `8r-32` (1.0) and `8h-32` (0.5) and three box matches of 800 boards are queued (E9-16's log).
