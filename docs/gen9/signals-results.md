# Gen 9 signals and card-play reading: results so far

> sam, 12 November 2026, updated 19:45 UTC. For the review package (G9-A6). Nothing here is adopted into an
> arena bot. Every number names its report. All prediction evidence: no match has been played with these readers.

Since noon a reader is scored in **double-dummy tricks saved a board** on p41's reading bench (stored solves, the
deal as the unit of error), with nats of the true layout's weight beside. "A board" against BEN is both tables of a
deal; on p41's house pools it is the four seats of one table. 0.1 tricks is about 0.36 IMPs.

## What was built

- **Signals as executable rules** (`bridge_harness/signals.py`): situations from public play, a carding descriptor
  (count, attitude, suit preference, Lavinthal, odd-even; leads), one probability function for the carding bot and
  the reader; symmetric honesty or per-signal emission tables.
- **The reader** (`SignalPlayer` in `bridge_harness/gen9_play.py`, under g9's shell): each hidden play split into the
  net's class term (times a factor) and the signal term (which spot). With no carding declared it is Gen 8.
- **Experience** (`bridge_harness/signal_experience.py`): honesty and emission tables learned from finished boards.
- **Signal experts** (`bridge_harness/signal_expert.py`, E9-15): occasions on first and second rounds, models from
  emission rows to a fitted expert, with every hand feature computed per layout.
- **A per-player head on the policy net** (`bridge_harness/play_head.py`, E9-14): 526 numbers fitted on one player's
  recorded choices.
- **Gen 9 readings on the bench** (`scripts/gen9_reading_bench.py`, G9-X2, PR #30): any bot spec, signal expert,
  head or class reading scored on the bench's stored pools, BEN's held-out tables or p41's house tables.

## What was measured

| Question | Answer | Report |
| --- | --- | --- |
| Are spots nine and below equivalent enough to be one class? | Yes: they differ on the true deal in 1.49% ± 0.08% of defender decisions | `reports/gen9-spot-equivalence-2026-11-12` (E9-3) |
| Do the house bots signal? | No; lowest spot 60% of the time; leads fourth best about half the time | `reports/gen9-house-carding-2026-11-12` (E9-9) |
| What is reading a declared scheme worth, in nats? | +0.49 to +0.96 nats a declarer decision over Gen 8 (honesty 0.5 to 1); too high an assumed honesty costs up to 0.86, so the prior is 0.5; learned within 25 to 50 boards | `reports/gen9-reading-gain-2026-11-12` (E9-4 part 1) |
| ... and in tricks? | **+0.062 ± 0.029 (honesty 0.8) and +0.063 ± 0.022 (0.5) tricks a board** to declarer over Gen 8, about +0.22 IMPs: the largest reading gain measured today | `reports/gen9-reading-bench-2026-11-12` (G9-X2 reading 2) |
| What would designed signals give the house defence? | +0.13 nats a defender decision, +0.32 leaked to a declarer who knows them | `reports/gen9-signal-pair-2026-11-12` (E9-6 part 1) |
| Does BEN signal? | Yes, count from a low-card default. Its honesty depends on the situation by a factor of 2 to 4 (0.31 to 0.35 when it cannot win the trick, 0.12 to 0.14 when it can), but its best situations carry only 0.07 to 0.12 bits a signal | `reports/gen9-ben-reading-2026-11-12` (E9-7), `reports/gen9-signal-expert-2026-11-12` (E9-15) |
| What is reading BEN's signals worth? | E9-7's emission model: +0.16 to +0.32 nats a declarer decision over Gen 8, **+0.021 ± 0.023 (BEN 16) and +0.009 ± 0.023 (BEN 64) tricks a board**. E9-15's expert adds +0.05 nats and no measurable tricks | `reports/gen9-reading-bench-2026-11-12` (G9-X2) |
| Can we model BEN's choices of card? | Yes: a head fitted on BEN's record predicts its choices +0.44 to +0.53 nats a decision better than the net, reads BEN's declarer play +0.08 to +0.14 nats better than the net at its best factor, and is worth **+0.035 ± 0.014 (BEN 64) and +0.013 ± 0.012 (BEN 16) tricks a board**; nothing measurable on BEN's defence | `reports/gen9-play-head-2026-11-12` (E9-14) |
| Is there enough BEN data? | For the head, yes: it is flat from about 1,000 tables, and a box of BEN lanes makes about 1,000 tables an hour. Whether a model with more capacity reads more is open | same |
| How much do our own equal cards give away? | To a reader of our strength, which of several equal spots we play is worth 0.038 ± 0.013 tricks a board, 0.023 of it our defenders' spots read by declarer; our partner gets 0.004 from them. Read by equal-best sets instead: 0.009 ± 0.017 | `reports/gen9-leakage-classes-2026-11-12` (E9-16 parts 1b, 1c) |

## What it adds up to

- Against BEN, the reading gains measured so far are 0.01 to 0.04 tricks a board each (0.05 to 0.13 IMPs), below what
  a 1,600-board match can see; E9-10's match was cancelled for that reason. Against a player who declares its scheme
  and follows it half the time or more, reading it is worth about 0.06 tricks a board.
- Gen 8 reads BEN for +0.05 (BEN 16) and +0.17 (BEN 64) tricks a board, against +0.185 for the house net reading the
  house bots: the room against BEN 16 is about 0.13 tricks, at both declarer's and the defenders' decisions.
- Nats overstate what signals are worth in tricks; the bench is the measure now.

## Not known yet

- Whether E9-4 part 2's match shows the predicted +0.22 IMPs a board (80% interval +0.09 to +0.36).
- What designed signals are worth to the house pair against a declarer who knows them (E9-6 on the bench, tonight).
- Whether a larger model of BEN's play (more of the net fine-tuned) reads more than the head.
- Played confirmation of any of these figures.
