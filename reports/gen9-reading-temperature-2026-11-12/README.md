# The prototype's play reading with the net sharpened or flattened, on p41's house pools

Gen 9 research (sam, signals), 13 November 2026. A side measurement prompted by E9-14's control: on house
defenders' choices, a fitted head scaled the net's logits by tau 1.26 to 1.32 (the net looked too flat for the house
bots' own cards). Kind of evidence: **prediction** (double-dummy tricks saved on stored solves; no match). Nothing
adopted.

**Data.** p41's published pools (`transfer/gen8-p41-reading-pools-20261112`): 530 tables, 21,417 decisions of every
seat after the opening lead, 329 deals. "A board" is the four seats of one table. Standard errors by deal.

**Readings** (`scripts/gen9_reading_bench.py readings --class-reading tT=card@T`, on 8p-32's player, net v4): each
hidden seat's play read by the net's probabilities over the legal cards raised to the power T and renormalised (the
same as scaling the logits by T), with the prototype's floor 0.05; `proto` is T = 1.

## Result

Paired against `proto`; tricks a board, the true layout's log-weight in nats a decision:

| T | Tricks a board | Nats | Declarer deciding | Defender deciding |
| --- | ---: | ---: | ---: | ---: |
| 0.85 | -0.001 ± 0.006 | -0.002 ± 0.004 | -0.005 ± 0.004 | +0.004 ± 0.004 |
| 1.15 | +0.000 ± 0.005 | -0.012 ± 0.003 | +0.001 ± 0.004 | -0.000 ± 0.003 |
| 1.3 | -0.009 ± 0.008 | -0.035 ± 0.006 | -0.002 ± 0.005 | -0.007 ± 0.005 |
| 1.5 | -0.019 ± 0.011 | -0.078 ± 0.010 | -0.009 ± 0.007 | -0.010 ± 0.009 |

The true layout's log-weight is highest at T = 1 among these, and no T gains tricks. E9-14's tau above 1 was fitted
to which card a house defender chose among the legal cards in the true deal; here the same scaling is applied to the
reading over layouts, where the net's probabilities at T = 1 already give the true layout the most weight.

Evidence: `report.txt` and `report.json` (the bench's report, `--against proto`).
Sample: 21,417 decisions on 530 tables of 329 deals, every seat's decisions after the opening lead; double-dummy
proxy with the tree off and no tie-break.
Revisit if: the net is replaced (a new net's calibration differs), or the reading is used on tables of other bots.
