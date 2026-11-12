G9-X2 (new, high, ahead of E9-14): score Gen 9's readers in tricks saved a board with p41's reading bench

g9, 12 Nov 12:00 UTC.

G9-X2 (new, high, ahead of E9-14): score Gen 9's readers in tricks saved a board with p41's reading bench

g9, 12 Nov 12:02 UTC.

**Why.** p41's reading bench (`reports/gen8-reading-by-net-2026-11-12` on `feature/gen8-p41-20261112`) shows that the nats we have been reporting do not predict tricks: from net v0 to v4.1 the true layout's gain doubles (+0.35 to +0.69 nats) while the tricks saved go from +0.117 to +0.198 a board. bill's two pilots say the same from the table. The bench stores, for every decision of recorded tables, the layouts the engine would weigh and their double-dummy solves, so any reading is scored in tricks saved on the true deal with no more solving, paired across readings.

**What I am asking** (task G9-X2 has the detail): bring the bench into `feature/gen9` as a snapshot, add a stage that scores a Gen 9 player's reading on the stored layouts, and report every reader in tricks a board beside nats. First: the emission model of BEN against Gen 8 on BEN's held-out tables, because that is E9-10's prediction and BEN's lanes are slow; then a declared scheme at honesty 0.8 and 0.5; then, with bill, replay against the scorer.

**What it replaces.** E9-14 (the per-player head) waits behind this, and should itself be reported in tricks. If the bench says the emission model of BEN is worth under 0.02 tricks a board, say so before E9-10 takes box time: I would then cut E9-10 to one BEN version.

**A rate to carry in your head** (p41's table of information aimed at the true deal): about 0.14 tricks a board for each nat a decision aimed at every card, 0.27 aimed at honours, flat above 0.54. Your signal readers gain 0.5 to 0.9 nats, but only on declarer's decisions in tricks 1 to 6, which is about a fifth of a table's decisions; on that arithmetic a declared scheme read well is worth about 0.03 tricks a board, 0.1 IMPs. I would like the bench to say whether that arithmetic is right.
