From Max (14:53): how much our own plays leak. E9-16 registered; one reading I need from your bench stage (class-only on house pools)

g9, 12 Nov 14:58 UTC.

From Max (14:53 UTC): how much our own plays leak, and how to randomize cheaply. E9-16 is registered; one reading I need from your bench stage, ahead of E9-14

g9, 12 Nov 15:00 UTC.

Max: "We should consider information leakage from our plays. I am worried that the scorer and policy net is too good. We need to sort out how much to randomize to make ourselves harder to read... The basic principle is to randomize close decisions, but how close and which type needs analysis."

**What I have** (`reports/gen9-leakage-2026-11-12` on `feature/gen9`; experiment E9-16, mine). On p41's house pools a reader of our own strength gains +0.124 +- 0.026 tricks a board from the opponents' plays (0.061 declarer reading defenders, 0.063 defenders reading declarer) and +0.038 from partner's. Randomizing close choices is dear: choosing evenly within 0.05 tricks of the best costs 0.065 tricks a board. But at 71% of decisions two or more cards are exactly equal best, and those are free.

**What I need from you, because your reader already does it (part 1b):** how much of that 0.124 is carried by which of several equal cards we played. On the house pools, through your bench stage:
1. the prototype's reading (card, factor 1) as the check that the stage reproduces p41's +0.185;
2. every hidden seat read by class only: the net's probability of the class, the choice inside the class even (your reader at honesty 0, class factor 1), with the class as E9-3's (spots nine and below);
3. the same with the class widened to every set of touching cards in the hand, honours included, if `signal_row` can take the class from the layout's hand; if not, say so and I will write it;
4. each of 2 and 3 for the opponents' plays only and for partner's plays only, and split by declarer reading and a defender reading.
On recorded tables the class reading is exactly what a calibrated reader would gain against a version of us that randomizes inside the class, because it does not look at which equal card was played. So (1 minus 2) is what our spot habits give away, in tricks.

**Order:** E9-15's submission, then this (it should be configuration and a run), then E9-14. If this is more than an hour of your time, tell me and I take item 3.

For the design after that: a concealment setting in the engine, declarer first (declarer has no partner who reads it, so everything its equal cards tell is given away for nothing).
