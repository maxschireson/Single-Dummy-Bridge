# E9-15: BEN's honesty by situation, and a signal expert per known opponent

Gen 9 research (sam, signals), 12 November 2026. Experiment file: `experiments/E9-15.md` on `team/gen9`.
Kind of evidence: **prediction** (held-out log-likelihood, the true layout's gain in nats, and double-dummy
tricks saved on the reading bench's stored solves). Nothing adopted.

**Data.** E9-7's: all 32 Gen 7 and 7.1 feeds against BEN (16) and BEN (64), deal families split four to one.
An occasion is a defender's choice among two or more spots (2 to 9) of a suit it holds, in tricks 1 to 9, in
one of signals.situation's keys (partner's lead, declarer's lead, first discard, trumps; opening leads are left
to the lead table) or on the second round of a suit it followed to on the first round (`.r2` keys). 31,502
occasions, BEN's and the house bots'. Fitted on the fit tables (1,126 BEN 16 and 1,450 BEN 64 tables with BEN
defending); measured on held-out tables only. Code: `bridge_harness/signal_expert.py`,
`scripts/gen9_signal_expert.py`, `scripts/gen9_signal_expert_report.py` (feature/gen9-signals-v2).

**Models** (each mixed with 5% of a uniform choice in the class, as the reader is):

- M0: one symmetric honesty per key (E9-7's).
- M1: an emission row per key and parity (E9-7's tables, refitted on the same split; with E9-7's own tables it
  reproduces `SignalModel` exactly). Second rounds: uniform, as today's reader.
- M2: cells key x length (2, 3, 4, 5+) x spots held (2, 3, 4+) x an honour in the suit, shrunk toward M1's row by
  alpha pseudo-occasions (cross-validated: 10 for BEN 16, 20 for BEN 64). Additive counts.
- M3: multinomial logistic for lowest / highest / middle, log M1 as offset, 93 one-hot features (key, parity by
  key, length by key, spots held, honour by key, points, strain, trump suit, who led, position, trick, dummy's
  length now, dummy's long suit with no entry, whether the signaller could win the trick, the first card's
  position on a second round), L2 penalty cross-validated (1 for both).

Every hand-dependent feature is computed per layout from the layout's hand when reading.

## 1. BEN's honesty and the information in its signals, by situation

Effective honesty: the symmetric honesty with the same information about the parity as the observed rates of
the highest spot from even and odd holdings (negative: a high card says odd). Bits: I(parity; lowest, highest
or middle card), less the Miller-Madow bias. 90% intervals by resampling tables. Full tables, held-out and all
tables, are in `tables.md`; held-out alone leaves few cells with 200 occasions, so the selection below is from
all tables (a description, not a prediction).

| Situation | BEN 16: h, bits | BEN 64: h, bits |
| --- | --- | --- |
| Declarer's lead, all | +0.27, 0.052 | +0.25, 0.044 |
| Declarer's lead, signaller could win the trick | +0.12, 0.011 | +0.14, 0.012 |
| Declarer's lead, could not win | +0.35, 0.088 | +0.31, 0.071 |
| Declarer's lead, second hand | +0.19, 0.028 | +0.18, 0.022 |
| Declarer's lead, fourth hand | +0.34, 0.085 | +0.32, 0.075 |
| Declarer's lead, second round, 2 spots left | -0.31, 0.066 | -0.35, 0.091 |
| Partner's lead, all | +0.18, 0.022 | +0.17, 0.021 |
| Partner's lead, trick 1 | +0.10, 0.007 | +0.09, 0.005 |
| Partner's lead, tricks 2-3 | +0.42, 0.124 | +0.34, 0.081 |
| First discard | +0.05, 0.001 | +0.10, 0.007 |
| Trumps | +0.12, 0.008 | +0.05, 0.000 |

- BEN's honesty varies by situation by a factor of 2 to 4: on declarer's lead it is about 0.12 when BEN could
  win the trick and 0.31 to 0.35 when it could not; on partner's lead 0.09 to 0.10 at trick 1 and 0.34 to 0.42
  at tricks 2 and 3. Its first discards and trump plays carry almost nothing.
- The most informative situations carry 0.07 to 0.12 bits a signal, up to about two and a half times the 0.04
  to 0.05 of declarer's lead taken as a whole. None carries ten times it.
- On the second round of declarer's suit, a high card from a holding with two spots left says odd (h -0.31 and
  -0.35): BEN's completed count. Today's reader gives these cards nothing.

## 2. Held-out log-likelihood of the spot played (nats an occasion over a uniform choice in the class)

| Model | BEN 16 (1,130 occasions, 230 tables) | BEN 64 (1,677, 345) |
| --- | ---: | ---: |
| M0, symmetric honesty | +0.014 ± 0.022 | -0.040 ± 0.021 |
| M1 (E9-7's tables) | +0.270 ± 0.020 | +0.233 ± 0.018 |
| M2, finer cells | +0.342 ± 0.020 | +0.322 ± 0.015 |
| M3, the expert | +0.350 ± 0.019 | +0.325 ± 0.015 |
| M3 fitted on the other version | +0.355 ± 0.019 | +0.324 ± 0.015 |

Of M3's gain over M1 (+0.081 and +0.093), the second rounds give +0.064 and +0.066. A model of one version
reads the other as well as its own. Curve over tables of experience, M3: +0.298 / +0.337 / +0.350 at 50 / 200 /
1,000 tables (BEN 16), +0.240 / +0.297 / +0.323 (BEN 64); M2 is ahead of M3 at 50 tables and level from 200.

## 3. Reading gain at the house declarer's decisions (tricks 1 to 6, E9-7's 300 held-out tables, pool 256)

Nats a decision, standard errors by table, all readers with the class term at 0.3:

| Reader | BEN 16 (1,582 decisions) | BEN 64 (1,570) |
| --- | ---: | ---: |
| Gen 8 (the net at 0.3) | +0.263 ± 0.030 | +0.185 ± 0.028 |
| E9-7's tables (r9b-32) | +0.426 ± 0.059 | +0.501 ± 0.059 |
| M1 refitted, against E9-7's tables | +0.012 ± 0.005 | +0.003 ± 0.004 |
| M2, against E9-7's tables | +0.041 ± 0.017 | +0.052 ± 0.019 |
| M3, against E9-7's tables | +0.054 ± 0.018 | +0.048 ± 0.021 |
| M3 from 200 tables (one subset), against E9-7's | +0.028 ± 0.018 | +0.041 ± 0.020 |
| M3 from 1,000 tables (one subset), against E9-7's | +0.050 ± 0.018 | +0.047 ± 0.021 |

(M1's +0.012 is the refit and a fix found here: `SignalModel.emitted` gave a layout in which the signaller held a single
spot about -0.1 nats instead of certainty; fixed in 8be31d6. E9-7's column uses the old behaviour, as r9b-32 at
67c59de does.)

## 4. In tricks: the reading bench (G9-X2)

p41's bench on E9-7's held-out tables (the first 245 BEN 16 and 253 BEN 64 tables of the 300, all the house
bots' decisions after the opening lead, pool 512, net v4; `scripts/gen9_reading_bench.py`, feature/gen9-reading-bench).
Readers on r9b-32 (E9-7's tables, with the fix), the expert models replacing its emission term wherever an occasion
is defined. Tricks a board (both tables of a deal), paired against r9b-32 on the same solves, standard errors by deal;
in brackets the bench's nats a house declarer decision:

| Reader | BEN 16 | BEN 64 |
| --- | ---: | ---: |
| Gen 8 (the net at 0.3), against r9b-32 | -0.014 ± 0.027 (-0.11) | +0.002 ± 0.024 (-0.26) |
| M2 all | -0.011 ± 0.017 (+0.03) | +0.010 ± 0.013 (+0.06) |
| M3 all | +0.015 ± 0.018 (+0.05) | -0.006 ± 0.009 (+0.05) |
| M3, first rounds only | -0.004 ± 0.008 (+0.02) | -0.009 ± 0.009 (+0.02) |

- No expert is distinguishable from E9-7's tables in tricks; the 90% upper bounds are about +0.04 (BEN 16) and
  +0.01 (BEN 64) tricks a board for M3.
- In nats the second rounds give about 60% of M3's gain over the tables (+0.05 with them, +0.02 without).

## Against the registered predictions

- The expert adds +0.05 nats or more a house declarer decision over E9-7's tables: **at the threshold**, +0.054 ±
  0.018 and +0.048 ± 0.021 (M2 +0.041 and +0.052).
- BEN's effective honesty differs by a factor of two or more between situations: **yes** (section 1).
- The second round gives more than half of the added gain: **yes** in nats (about three quarters at the level of
  occasions, about 60% in the bench's reading gain); in tricks there is no gain to divide.
- House control: the house defenders' effective honesty is within ±0.05 of zero on declarer's and partner's
  leads, but +0.09 to +0.15 on first discards (BEN 16 and 64). Their reading through an expert was not scored.

**What it is worth.** By g9's table of what information is worth (`reports/gen9-auction-worth-2026-11-12`), +0.05
nats at declarer's early decisions is about 0.002 tricks a board; the bench measures zero within ±0.01 to ±0.02.

**Limits.** Prediction evidence. "Could the signaller win the trick" is computed from its hand in each layout; a
signaller void in the suit led counts as able to win if it held a trump. Cells are descriptive and overlap.
