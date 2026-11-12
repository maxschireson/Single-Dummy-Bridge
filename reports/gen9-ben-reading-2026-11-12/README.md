# E9-7: a reading model for BEN, fitted on its recorded cards

Gen 9 research (sam, signals), 12 November 2026. Experiment file: `experiments/E9-7.md` on `team/gen9`.
Kind of evidence: **prediction** (gain in the true layout's log weight on held-out boards). Nothing adopted.

**Data.** All 32 Gen 7 and 7.1 feeds against BEN (16) and BEN (64): 2,744 episodes. Deal families are
split four to one (`crc32(family) % 5 == 0` held out). Fitted on 2,319 (BEN 16) and 2,918 (BEN 64)
tables; scored on 300 held-out tables of each (about 150 with BEN defending and 150 with BEN declaring).
Scripts: `scripts/gen9_ben_reading.py`, `gen9_ben_reading_report.py`, `gen9_house_signal_association.py`,
`gen9_house_carding.py`.

## 1. Does BEN signal? Yes, by count, from a low-card default

Share of high spots when the true hand's parity is even and when it is odd (all boards; standard errors
from the counts). Attitude rows use "holds the A, K or Q" as the fact.

| BEN signal (fact) | BEN (16): P(high) even / odd, difference | BEN (64) |
| --- | --- | --- |
| Count, declarer's lead | 0.21 / 0.05, +0.160 ± 0.015 | 0.20 / 0.05, +0.151 ± 0.013 |
| Count, partner's lead | 0.23 / 0.09, +0.134 ± 0.021 | 0.22 / 0.10, +0.118 ± 0.019 |
| Attitude, partner's lead | 0.22 / 0.12, +0.104 ± 0.023 | 0.22 / 0.11, +0.110 ± 0.019 |
| Count, first discard | 0.19 / 0.16, +0.030 ± 0.018 | 0.20 / 0.14, +0.057 ± 0.015 |
| Attitude, first discard | 0.16 / 0.20, -0.039 ± 0.020 | 0.16 / 0.19, -0.030 ± 0.017 |
| Count, trumps | 0.13 / 0.06, +0.070 ± 0.021 | 0.09 / 0.07, +0.027 ± 0.018 |

BEN plays the lowest spot most of the time and a high spot mostly from even length: a high card from
BEN says a lot, a low card little. Its opening leads match third-and-fifth best on 0.58 (BEN 16) and
0.61 (BEN 64) of leads and fourth best on 0.53 and 0.58, against 0.30 by chance
(`leads_and_adherence.json`).

## 2. Reading BEN's defenders (house declarer's decisions, tricks 1 to 6)

Gain in nats per decision (1,582 and 1,570 decisions on 149 and 150
held-out tables), and in brackets the paired difference from Gen 8's reading with its standard error:

| Reader of BEN's defenders | BEN (16) | BEN (64) |
| --- | ---: | ---: |
| Gen 8: the net on the card at 0.3 | +0.263 | +0.185 |
| The house net in full | +0.144 (-0.119 ± 0.064) | -0.024 (-0.208 ± 0.059) |
| Class term alone at 1 | +0.167 (-0.096 ± 0.052) | +0.001 (-0.184 ± 0.052) |
| Class at 1 + symmetric honesty | +0.281 (+0.017 ± 0.076) | +0.281 (+0.097 ± 0.073) |
| Class at 1 + emission tables | +0.474 (+0.211 ± 0.068) | +0.443 (+0.258 ± 0.064) |
| Class at 0.3 + emission tables | +0.425 (+0.162 ± 0.050) | +0.501 (+0.316 ± 0.048) |

- **The emission tables gain +0.16 to +0.32 nats per decision over Gen 8.** That is the asymmetric
  model of section 1 (`signals.SignalModel(emission=...)`): P(lowest, highest or a middle spot |
  parity), fitted per signal and shrunk toward the pooled positions.
- **Symmetric honesty does not work for BEN** (+0.02 and +0.10, within noise): it treats noise as
  high or low with equal chance, so it reads BEN's informative high card as weak evidence.
- **The class term at factor 1 is worse than Gen 8** (-0.10, -0.18): BEN's choices of what to do are
  not the house bots'. With the tables, factor 0.3 on the class reads BEN 64 better than 1 (by 0.06)
  and BEN 16 a little worse (by 0.05); both within noise, so the model keeps Gen 8's 0.3.

## 3. Reading BEN as declarer (house defender's decisions)

| BEN's declarer play read at | BEN (16) | BEN (64) |
| --- | ---: | ---: |
| factor 0 | +0.474 (-0.128 ± 0.020) | +0.441 (-0.110 ± 0.021) |
| factor 0.3 | +0.602 | +0.551 |
| factor 0.5 | +0.620 (+0.018 ± 0.012) | +0.552 (+0.001 ± 0.013) |
| factor 1 | +0.483 (-0.119 ± 0.043) | +0.360 (-0.191 ± 0.048) |

Gen 8's 0.3 is already the right factor for BEN's declarer play (0.5 is at most 0.02 better; 0 and 1
are clearly worse).

## Against the registered predictions

- A reading fitted to BEN's cards beats the house net at 0.3 and at 1: **yes** (+0.16 to +0.32 over 0.3).
- Most of the gain comes from the cheapest step, a factor per role and trick band: **no.** The factors
  were already right; the gain comes from BEN's count signals read by the emission model.
- An adapter on the policy net fitted on BEN's cards: **not attempted.**

**The model** is in `configs/carding/ben16.json` and `ben64.json` (descriptor, emission tables, lead
honesty, phi 0.3). A Gen 9 bot reads BEN by it as `r9b-32` (`configs/gen9-signal-bots.json`), for E9-10.
The reader also learns emission tables from experience (`card.<key>.emit` statistics, after 200 occasions
of a signal), so a newly met player with BEN-like habits would get the same model after a few hundred
boards.

**Limits.** Prediction evidence. The pools come from the house scorer, which reads BEN's native
auctions less well than house auctions. Positions are those the Gen 7 bots and BEN reached.
