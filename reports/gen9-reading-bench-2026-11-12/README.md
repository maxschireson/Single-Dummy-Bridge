# G9-X2: Gen 9's readers of BEN on the reading bench, in tricks saved a board

Gen 9 research (sam, signals), 12 November 2026. Task G9-X2 on `team/gen9`. Kind of evidence: **prediction**
(double-dummy tricks saved on the true deal, on stored solves; no match was played). Nothing adopted here.

**Method.** p41's reading bench (`scripts/gen8_reading_bench.py`, a snapshot of `feature/gen8-p41-20261112` at
cdde42a) solves, at every decision, the layouts the prototype's engine would weigh (before the deal list: 512
layouts drawn by the hand-fit scorer's class weights; from trick 7 the listed layouts) and the true deal, for every
legal card. A reading is the log weight it gives each stored layout; its cost is the double-dummy cost on the true
deal of the card the weighted solves choose, against no reading. `scripts/gen9_reading_bench.py` runs the bench's
`pools` on E9-7's held-out tables against BEN (deal families with crc32 % 5 == 0, the first 300 tables of each
version) at the house bots' decisions only, and adds readings by bot specs and by the Gen 9 models (`readings`).
Everything is paired on the same solves. "A board" is both tables of a deal (the house bot decides at both); standard
errors take the deal as the unit. Solved in the sandbox (12:15 to 16:37 UTC).

**Readers.** `g8`: 8x-32 (Gen 8: net v4, BEN's plays at factor 0.3, partner's in full). `g9`: r9b-32 (E9-7's emission
tables for BEN's defenders' spots; with the fix 8be31d6). `v4`: the net in full on BEN too. `x2`, `x3`, `x3f`: E9-15's
models M2, M3, and M3 on first rounds only, in place of the emission tables. `hd05`, `hd1`: E9-14's head on BEN's
declarer play at 0.5 and 1. `hc`, `hc1`: E9-14's head on BEN's defenders' classes at 0.3 and 1. `hb1`: both heads at 1.

## Result

300 tables a version: 6,036 decisions (BEN 16) and 6,070 (BEN 64) on 129 deals each. Tricks a board:

| Reading | BEN 16, against no reading | BEN 64, against no reading |
| --- | ---: | ---: |
| Gen 8 (`g8`) | +0.052 ± 0.028 | +0.166 ± 0.048 |
| Emission model (`g9`) | +0.072 ± 0.034 | +0.175 ± 0.053 |
| Net in full (`v4`) | +0.071 ± 0.047 | +0.079 ± 0.060 |

For comparison: the house net reading the house bots, p41's 530 house tables: +0.185 ± 0.029.

Paired:

| | BEN 16 | BEN 64 |
| --- | ---: | ---: |
| Emission model against Gen 8 (house declarer's decisions) | +0.021 ± 0.023 (+0.14 nats) | +0.009 ± 0.023 (+0.24 nats) |
| Net in full against Gen 8 | +0.020 ± 0.033 | -0.087 ± 0.035 |
| E9-15 M3 against the emission model | +0.005 ± 0.016 | +0.000 ± 0.011 |
| E9-15 M3, first rounds only | -0.011 ± 0.010 | -0.009 ± 0.009 |
| E9-15 M2 | -0.011 ± 0.014 | +0.009 ± 0.012 |
| E9-14 head on BEN's declarer play at 0.5, against Gen 8 | +0.013 ± 0.012 | +0.035 ± 0.014 |
| E9-14 head on BEN's defenders' classes at 1, against the emission model | +0.002 ± 0.024 | -0.029 ± 0.027 |
| Both heads at 1, against Gen 8 | +0.030 ± 0.028 | +0.006 ± 0.033 |

By stage, declarer or defender deciding: `tables_vs_gen8.md` and `tables_vs_r9b.md`.

- **The first reading (E9-10's question).** E9-7's emission model of BEN is worth +0.021 ± 0.023 (BEN 16) and +0.009
  ± 0.023 (BEN 64) tricks a board over Gen 8, +0.015 ± 0.016 pooled, about +0.05 IMPs. A 1,600-board match could not
  see that; E9-10 stays cancelled.
- **Nats and tricks.** The emission model's +0.14 to +0.24 nats a declarer decision, at the 53% of these decisions
  that are declarer's, would be +0.01 to +0.02 tricks a board at g9's rate of 0.14 a nat (p41's information aimed at
  every card); the bench agrees within its errors. E9-15's further +0.05 nats is not measurable in tricks.
- **The largest gain in tricks against BEN** is E9-14's head on BEN's declarer play: +0.035 ± 0.014 (BEN 64), +0.013
  ± 0.012 (BEN 16).
- **Reading BEN's plays in full** (factor 1) costs 0.087 ± 0.035 tricks a board against BEN 64: the factor 0.3 matters.

**What is left.** Reading (2) of G9-X2 (a declared scheme read at honesty 0.8 and 0.5, on E9-4 part 1's 300 house
tables relabelled) is queued on azure4 as `g9-x2-rel-std-80` and `-50` (priority 3; the box is busy until about 21:30).
Reading (3), bill's replayed bidder, runs on p41's pools by bill. E9-16 parts 1b and 1c: `reports/gen9-leakage-classes-2026-11-12`.

**Limits.** The pools come from the house scorer, which reads BEN's native auctions less well than house auctions.
The bench leaves out the tree and the tie-break. Positions are those the Gen 7 bots and BEN reached. E9-14's heads
were fitted on tricks 1 to 6 and are applied here at every trick.
