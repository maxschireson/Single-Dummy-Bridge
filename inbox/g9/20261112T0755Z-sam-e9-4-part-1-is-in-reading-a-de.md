E9-4 part 1 is in: reading a declared scheme gains +0.49 to +0.96 nats per declarer decision over Gen 8 at honesty 0.5 to 1; over-assuming honesty costs up to 0.86

sam, 12 Nov 07:55 UTC. Task E9-4.

From sam, 12 Nov.

**Part 1** (prediction; 296 recorded Gen 7 tables, defenders' spots relabelled by the carding bot's rule within the recorded tie sets, 3,153 declarer decisions per cell, tricks 1 to 6). Gain of the true layout's log weight over Gen 8's unknown-opponent reading (net on the card at 0.3), signal reader at class factor 1:

| Cell | Reader minus Gen 8 | Of which the facts |
| --- | ---: | ---: |
| std-100 | +0.90 ± 0.08 | +0.57 ± 0.06 |
| std-80 | +0.72 ± 0.07 | +0.37 ± 0.05 |
| std-50 | +0.49 ± 0.05 | +0.16 ± 0.03 |
| std-0 | +0.33 ± 0.04 | +0.00 ± 0.00 |
| ud-100 | +0.96 ± 0.07 | +0.63 ± 0.06 |
| ud-80 | +0.78 ± 0.06 | +0.46 ± 0.04 |
| ud-50 | +0.51 ± 0.05 | +0.19 ± 0.03 |
| std35-80 | +0.70 ± 0.06 | +0.37 ± 0.05 |

**What a wrong honesty costs, as you asked** (reader minus Gen 8; rows: true honesty; columns: honesty assumed):

| True | Assume 0 | 0.5 | 0.8 | 0.9 | True |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | +0.33 | +0.78 | +0.92 | +0.93 | +0.90 |
| 0.8 | +0.34 | +0.67 | +0.72 | +0.68 | +0.72 |
| 0.5 | +0.33 | +0.49 | +0.39 | +0.27 | +0.49 |
| 0 | +0.33 | +0.16 | -0.23 | -0.53 | +0.33 |

Over-assuming is the expensive direction: against honesty 0, assuming 0.9 loses 0.86 nats against the right reading. Against honesty 1, assuming 0.5 loses 0.12. Against honest bots 0.9 reads slightly better than 1, because the bot signals among its tied cards. So the reader's prior should sit low (about 0.5) until experience moves it. The learning curve (G9-S5) is running now on std-80, ud-80 and std-50 and will say how many boards that takes.

**Two things that change your shell or the plan.**
1. **Class factor.** Reading the class at factor 1 beats Gen 8's card at 0.3 by +0.12 to +0.16 even with spots ignored. These defenders' class choices are the house bots' own, so this overstates it for a foreign player, but it suggests Gen 8's 0.3 for the fixed-carding types was mostly about misread spots. Once spots are read by a scheme, `phi` for such opponents should be fitted on the class term, which the `play.info` statistic does.
2. **House bots signal nothing** (E9-9), so E9-6 starts from a defence with no information in its spots.

**Branch.** My work continues on `feature/gen9-signals-v2`, cut from `feature/gen9` at `2c4c8a2` with my later commits re-applied. `feature/gen9-signals` is superseded. Since `2c4c8a2`: G9-S5's module so far (`signal_experience.py` and its tests), G9-S6/E9-9's report, the E9-4 scripts and report, and `cp-std-100` rebased on `8p-32` plus `r9p-32` (8p-32 told its scheme) for E9-6. bill reviews the modules when G9-S5 is submitted.

Report: `reports/gen9-reading-gain-2026-11-12/README.md` at `5a5c51d`.
