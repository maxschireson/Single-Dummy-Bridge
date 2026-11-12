E9-16 part 1c: reading every play by its own equal-best set costs the reader -0.36 nats but only -0.009 +- 0.017 tricks a board; partner's plays alone +0.008 +- 0.007

sam, 12 Nov 17:50 UTC. Task E9-15.

From sam, 12 Nov 17:50 UTC. reports/gen9-leakage-classes-2026-11-12 (feature/gen9-reading-bench 9e58f0c), tables.md and report.json updated. p41's 530 house tables, paired against the card reading (+0.185 +- 0.029), tricks a board:
- every hidden seat by its equal-best set: -0.009 +- 0.017 (-0.36 nats); declarer deciding -0.010 +- 0.013, a defender deciding +0.001 +- 0.011.
- opponents' plays only: -0.014 +- 0.017 (declarer -0.010 +- 0.013, defenders -0.003 +- 0.010).
- partner's plays only: +0.008 +- 0.007.
As you asked, the reading is approximate: the listed set is the true hand's, restricted in each layout to the cards that layout gives the chooser (a layout holding none of the others keeps the card's own probability). The opening lead has no listed set in your file (p41 stores no decision at ply 0) and is read by the card.
So 8r-32's randomization (a random one of the equal-best cards) is predicted to cost a reader of our strength no detectable tricks: about 0.01 +- 0.017 a board, against 0.038 +- 0.013 for reading by spot classes. The two measures treat different cards as interchangeable; I have not tried to say which is closer to what a match would show.
