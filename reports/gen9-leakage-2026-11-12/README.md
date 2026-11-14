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

## How much of the leak is the choice among touching cards (part 1b, sam)

`reports/gen9-leakage-classes-2026-11-12` on `feature/gen9-reading-bench` (47de109). The same pools; the reader is
given the net's probability of the class of the card, with the card inside the class chosen evenly, in place of the
card's own. That is what a reader who has adapted would gain against a version of us that randomizes inside the class.
The stage's reading of the actual cards reproduces p41's +0.185 +- 0.029. Tricks a board lost by the reader:

| What is hidden | All readers | Declarer reading the defenders | Defenders reading declarer | Partner |
| --- | ---: | ---: | ---: | ---: |
| Which spot of the suit (nine and below) | 0.038 +- 0.013 | 0.023 +- 0.010 | 0.005 +- 0.005 | 0.004 +- 0.007 |
| Which of touching cards, honours included | 0.036 +- 0.017 | 0.020 | 0.001 | 0.003 +- 0.006 |

- **The choice among touching cards carries about a fifth of what the reader gains** (0.038 of 0.185; for the
  opponents' reading 0.028 of 0.124). My expectation that most of the leak sits there was wrong for touching cards.
- Nearly all of it is the defenders' spots read by declarer. Declarer's own equal cards tell the defenders almost
  nothing, so hiding them as declarer alone buys little against a reader like ours.
- Hiding the defenders' spots costs our own defence 0.004.

Not yet measured offline: the larger group, 18 of the 29 equal-best cards a table, where the equal cards are
*different* cards (which suit to discard from, which of two safe exits). The class reading still reads those in
full. `equal_best.json.gz` in this folder lists, for every recorded decision, the cards the chooser's own solves rate
exactly equal, so that the same reading can be run with those as the class (part 1c). The matches with `8r-32`
randomize both groups.

## The larger group: any of the exactly equal-best cards (part 1c, sam) and the first played figure

Same folder of sam's as part 1b (9e58f0c). The reader takes each play as an even choice among the cards the chooser's
own solves rate exactly equal best (`equal_best.json.gz`; approximate, because in another layout the chooser would
hold other cards and other ties; the opening lead is still read by the card):

| What is hidden | Tricks a board lost by the reader | Nats |
| --- | ---: | ---: |
| Which of the equal-best cards, every hidden seat | 0.009 +- 0.017 | 0.36 |
| ... the opponents' plays only | 0.014 +- 0.017 | |
| ... partner's plays only | -0.008 +- 0.007 | |

Played, will's sandbox pilot (400 boards, seed 917, not the box's deals): `8r-32`, which plays a random one of its
exactly equal-best cards, against `8p-32`, which reads it with today's net at full weight: **+0.17 +- 0.17 IMPs a
board** for the randomizer (72 won, 59 lost, 269 flat).

What the three parts say together, at the capture rate of our own net:

- Randomizing among equal cards is free double dummy and showed no cost in 400 played boards.
- It denies a reader little: 0.01 to 0.04 tricks a board (0.04 to 0.14 IMPs), depending on which cards are treated
  as interchangeable.
- So most of the 0.124 tricks a reader takes from our plays comes from choices that are not equal: the suit we
  switch to, whether we win or duck, what we keep. Part 1a says randomizing those costs about what it would deny:
  0.020 tricks a board within 0.02 tricks of the best, 0.065 within 0.05.
- The 800-board matches on the box (`e9-16-r-v-p`, `-r-v-x`, `-h-v-p`) will put a tighter error on the played figure.
  Whether any kind of close decision is worth randomizing is part 1d, not yet done.
