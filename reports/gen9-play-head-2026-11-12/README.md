# E9-14: a per-player head on the policy net, fitted on BEN's own cards

Gen 9 research (sam, signals), 12 November 2026. Experiment file: `experiments/E9-14.md` on `team/gen9`. It is also
the measurement for Max's question of 13:55 UTC: is there enough BEN data to train on its card play?
Kind of evidence: **prediction** (held-out log-likelihood of BEN's choices; the true layout's gain in nats; double-dummy
tricks saved on the reading bench). Nothing adopted.

**The head** (`bridge_harness/play_head.py`). The net (v4, the house net) ends in one 256-vector per suit and a linear
map to the 13 card logits of that suit. The head keeps the vectors and changes one player's logits:
`tau x logit + d_s.u + c[rank] + sum_k a_k d_s[k] W[k, rank]`, 526 numbers (a temperature, a suit preference, a
rank preference, and a reweighting of each of the 256 decoder units' share of the card logits). Fitted by maximum
likelihood on the player's recorded choices from its own view, shrunk toward no change; the penalty is chosen by
3-fold cross-validation over tables. BEN as declarer is fitted on its cards (its own and dummy's); BEN as a defender
on its classes of card (E9-3's class rule), since its spots are E9-7's emission tables' to read.

**Data and split** (E9-7's): the Gen 7 and 7.1 feeds against BEN 16 and BEN 64, deal families four to one; tricks 1 to
6; decisions with more than one legal card.

| | BEN 16 | BEN 64 |
| --- | ---: | ---: |
| BEN declaring: fit tables, decisions | 1,180; 12,608 | 1,461; 15,650 |
| BEN defending: fit tables, decisions | 1,129; 11,940 | 1,451; 15,299 |
| Held-out (300 tables a version): decisions as declarer, as defender | 1,598; 1,560 | 1,587; 1,603 |

All 13 tricks would about double these: of the order of 150,000 BEN decisions in the record. From the feeds'
manifests and last commits, a box of eight BEN lanes made about 2,700 BEN 16 tables in 2.3 hours (azure2) and 1,400
to 1,700 BEN 64 tables in 1.7 to 2.3 hours (azure3): of the order of 1,000 tables an hour, so the record can be
doubled in a few hours of one box.

## 1. How well the head predicts BEN's own choices (held out)

Log-likelihood per decision over the net, mean of 5 random subsets (all = every fit table):

| | 50 tables | 200 | 1,000 | all |
| --- | ---: | ---: | ---: | ---: |
| BEN 16 as declarer (cards) | +0.272 | +0.370 | +0.435 | +0.438 ± 0.030 |
| BEN 64 as declarer | +0.348 | +0.451 | +0.518 | +0.525 ± 0.032 |
| BEN 16 as defender (classes) | +0.090 | +0.140 | +0.169 | +0.170 ± 0.020 |
| BEN 64 as defender | +0.108 | +0.153 | +0.183 | +0.186 ± 0.019 |

A head fitted on one version predicts the other as well as its own (+0.446 and +0.518 as declarer, +0.172 and
+0.192 as defender): it is a model of BEN, not of one setting. The fitted temperature is 0.91 to 0.95 for BEN's
declarer play and about 0.80 for its defence (BEN is less predictable to the house net than the net thinks).

## 2. Reading gain at the house bots' decisions (E9-7's pools: 256 layouts, tricks 1 to 6), nats a decision

| | BEN 16 | BEN 64 |
| --- | ---: | ---: |
| **BEN declaring** (house defender deciding; 1,381 and 1,400 decisions) | | |
| Net at 0.3 (Gen 8) | +0.602 ± 0.039 | +0.551 ± 0.039 |
| Net at 0.5 (its best factor), against 0.3 | +0.018 ± 0.013 | +0.001 ± 0.014 |
| Head at 0.5, against the net at 0.3 | +0.100 ± 0.022 | +0.140 ± 0.022 |
| Head at 1, against the net at 0.3 | +0.084 ± 0.047 | +0.149 ± 0.043 |
| **BEN defending** (house declarer deciding; 1,582 and 1,570) | | |
| E9-7's reading (class at 0.3 + emission tables) | +0.434 ± 0.059 | +0.502 ± 0.059 |
| The net's class at 1, against it | +0.049 ± 0.042 | -0.057 ± 0.045 |
| The head's class at 0.3, against it | +0.028 ± 0.012 | +0.049 ± 0.012 |
| The head's class at 1, against it | +0.194 ± 0.038 | +0.132 ± 0.044 |

Curve, head at 0.5 on BEN's declarer play, against the net at 0.3 (mean of 5 subsets): +0.047 / +0.064 / +0.097 /
+0.100 at 50 / 200 / 1,000 / all tables (BEN 16), +0.056 / +0.104 / +0.137 / +0.140 (BEN 64). The head's class at 1:
+0.137 / +0.181 / +0.193 / +0.194 (BEN 16), +0.043 / +0.090 / +0.134 / +0.132 (BEN 64).

Control: the same head fitted on the house defenders and reading partner's plays: +0.023 ± 0.011 (on the BEN 16
tables) and +0.012 ± 0.011 at 0.3. Its temperature is 1.26 to 1.32: the net is somewhat too flat for the house bots too.

## 3. In tricks: the reading bench

p41's bench on E9-7's 300 held-out tables a version: every decision of the house bots after the opening lead,
pool 512, net v4 (`scripts/gen9_reading_bench.py`, feature/gen9-reading-bench). Tricks a board (both tables of a
deal), standard errors by deal; the bench's nats beside. Readers: `g8` = 8x-32 (Gen 8: the net at 0.3 on BEN);
`g9` = r9b-32 (E9-7's emission tables); `hd` = g8 with BEN's declarer play read by the head; `hc` = g9 with BEN's
defenders' classes read by the head; `hb` = both.

Against no reading (what the reading of BEN is worth at all):

| | BEN 16: all | declarer deciding | defender deciding | BEN 64: all | declarer deciding | defender deciding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gen 8 (`g8`) | +0.052 ± 0.028 | +0.042 ± 0.020 | +0.009 ± 0.019 | +0.166 ± 0.048 | +0.037 ± 0.018 | +0.129 ± 0.048 |
| Head on declarer at 0.5 (`hd05`) | +0.065 ± 0.029 | +0.042 ± 0.020 | +0.023 ± 0.021 | +0.201 ± 0.048 | +0.037 ± 0.018 | +0.164 ± 0.047 |
| Both heads at 1 (`hb1`) | +0.081 ± 0.040 | +0.065 ± 0.034 | +0.016 ± 0.021 | +0.173 ± 0.060 | +0.017 ± 0.029 | +0.156 ± 0.048 |

For comparison, the house net reading the house bots (p41's 530 house tables): +0.185 ± 0.029.

Paired, on the decisions where the head changes the reading:

| | BEN 16 | BEN 64 |
| --- | ---: | ---: |
| BEN's declarer play: head at 0.5 against the net at 0.3 (house defender deciding) | +0.013 ± 0.012 (+0.09 nats) | +0.035 ± 0.014 (+0.10 nats) |
| The same, head at 1 | +0.007 ± 0.013 (+0.06) | +0.026 ± 0.017 (+0.04) |
| BEN's defenders: head's class at 1 against E9-7's reading (house declarer deciding) | +0.002 ± 0.024 (+0.14) | -0.029 ± 0.027 (+0.16) |
| The same, head's class at 0.3 | -0.014 ± 0.013 (+0.04) | -0.003 ± 0.010 (+0.06) |
| Both heads at 1, against Gen 8, all decisions | +0.030 ± 0.028 | +0.006 ± 0.033 |

- On BEN's declarer play the head is worth +0.035 ± 0.014 tricks a board against BEN 64 and +0.013 ± 0.012 against
  BEN 16, about +0.13 and +0.05 IMPs at 3.6 a trick.
- On BEN's defence the head's larger gain in nats (+0.14 to +0.16 at factor 1) is not seen in tricks (+0.002 ± 0.024,
  -0.029 ± 0.027): the bench does not confirm that the class term can be trusted at 1.
- The room: Gen 8 reads BEN 16 for +0.05 tricks a board and BEN 64 for +0.17, against +0.185 for the house reading
  itself; most of the BEN 16 shortfall is at the house defenders' decisions (+0.009 ± 0.019), where the head adds
  +0.013.

## Against the registered predictions

- At all tables the head gains +0.10 nats or more a house defender decision over the factor alone: BEN 16 +0.08
  (head at 0.5, +0.100, less the net's own +0.018 at 0.5), BEN 64 +0.14. **Half met** (BEN 64 yes, BEN 16 just short).
- Ahead by 200 tables: **yes** for both (+0.064 and +0.104 at 0.5, against +0.018 and +0.001 for the factor).
- A head fitted on one version read on the other: as good as its own.
- The house control within 0.02 nats: **at the edge** (+0.023 ± 0.011, +0.012 ± 0.011).
- In tricks (not registered): +0.035 ± 0.014 (BEN 64) and +0.013 ± 0.012 (BEN 16) on BEN's declarer play; nothing
  measurable on its defence.

## What the curve says about training on BEN's card play

The head's own fit flattens from about 1,000 tables: from 1,000 to all (1,180 and 1,461 tables) it adds +0.003 to
+0.007 nats a decision, against +0.065 from 200 to 1,000. More tables alone would add little to a head of this size,
and tables are cheap (a few hours of one box doubles the record). What the curve does not settle is how much a model
with more capacity would read (fine-tuning the decoder or more of the net on BEN's decisions: the house net was trained
on 13.2 million examples, BEN's record holds about 150,000 decisions). Not started.

**Limits.** Prediction evidence. Fitted on tricks 1 to 6; the bench scores every decision after the lead, so from
trick 7 the head is applied outside what it was fitted on. The pools come from the house scorer, which reads BEN's own
auctions less well than the house's.
