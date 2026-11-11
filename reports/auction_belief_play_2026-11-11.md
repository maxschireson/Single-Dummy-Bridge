# Auction belief in the play: exact lists, a hand-fit scorer, hand-type classes

**Status: research prototype. Not the final package for the Gen 6 cutover.** Measured on the Gen5 bidder and the v5 belief net; no arena bot uses any of it.

11 November 2026. Continues [auction_belief_lead_2026-11-10.md](auction_belief_lead_2026-11-10.md). Run in a Claude workspace (2 cores) on the `arena-gen5-codex-32-feed` branch: Gen5 bidder, v5 belief net, the runtime's own solver build. Nothing in the bot was changed. No arena match was played.

## Result

Whole play after the opening lead (199 tables, 8,014 decisions, 32 layouts per source). Tricks per table over all four seats, double-dummy scored on the true deal; positive favours the first source.

| Comparison | Tricks 1–5 | Tricks 6–12 | All tricks | IMPs per table, all tricks |
|---|---:|---:|---:|---:|
| Scorer on classes (no bidder at the table) vs v5 | +0.112 ± 0.047 | +0.069 ± 0.032 | +0.181 ± 0.057 | +0.48 ± 0.19 |
| Bidder on classes (ceiling) vs v5 | +0.094 ± 0.047 | +0.058 ± 0.034 | +0.151 ± 0.060 | +0.43 ± 0.25 |
| Ceiling vs scorer | −0.018 ± 0.043 | −0.011 ± 0.020 | −0.029 ± 0.050 | −0.04 ± 0.17 |
| v5 vs cards only | +0.084 ± 0.060 | +0.123 ± 0.040 | +0.207 ± 0.076 | +0.75 ± 0.25 |

- Over the whole play the scorer on classes beats v5 by 0.18 ± 0.06 tricks per table and is not distinguishable from the bidder-built ceiling.
- The gain is at tricks 3, 4 and 6. Nothing is measurable at tricks 1, 2 and 5 or from trick 7 on.
- Bidding information held, nats per decision: v5 0.52, scorer 1.50, bidder test 1.91.
- Which layouts are solved matters less than the belief: within the scorer's posterior, 256 layouts instead of 32 are worth 0.05 tricks per table in tricks 1–5, and 32 cluster centres 0.02.

Late play only (tricks 6–12), larger samples:

| Comparison | Tables | Tricks per table | IMPs per table |
|---|---:|---:|---:|
| Bidder-built list (up to 256 layouts) vs v5 | 251 | +0.172 ± 0.042 | +0.84 ± 0.23 |
| Bidder-built list (up to 256) vs v5 | 400 | +0.132 ± 0.028 | +0.34 ± 0.14 |
| Scorer-weighted list (256) vs v5 | 400 | +0.106 ± 0.028 | +0.27 ± 0.11 |
| Bidder-built list vs scorer-weighted list | 400 | +0.025 ± 0.017 | +0.07 ± 0.11 |
| v5 vs cards-only layouts | 400 | +0.038 ± 0.031 | +0.21 ± 0.13 |

- From trick 1 the layouts can be weighted for the bidding with no bidder at the table: a small net scores each hidden hand's fit to its seat's calls, and hand-type classes make the sum over all layouts exact.
- In tricks 6–12 v5 beats layouts that use the cards and show-outs alone by +0.04 ± 0.03, +0.05 ± 0.03, +0.10 ± 0.05 and +0.12 ± 0.04 tricks per table in the four samples.
- The two IMP figures for the bidder-built list differ by 1.9 standard errors between the two samples; the trick figures agree better.

## Yardstick

Recorded common-auction tables from the feed (one table per episode, all four seats played by the v5 bot). Each non-forced decision is remade from each source's layouts: the card with the best mean double-dummy value, exact ties split evenly. The choice is scored double-dummy on the true deal against the best card there. Costs are summed per table over all four seats; standard errors are across tables. IMPs convert each pair of choices at one decision, assuming double-dummy play afterwards.

The held-out-posterior yardstick of the lead report is not used here. After the lead the true posterior also depends on the cards players chose, which an auction-only posterior ignores.

## Late play with bidder-built lists (ceiling, 251 tables, episodes 0–253)

At the start of trick 6 each player lists every layout of the two hidden hands that fits the cards seen and show-outs (at most 12,870). A layout stays if each hidden seat's original 13 cards, held plus played, pass the Gen5 bidder test for that seat's calls. The list is then thinned by the cards played. 5,924 decisions.

| Source | Cost, tricks per table |
|---|---:|
| v5, 32 layouts | 0.381 ± 0.051 |
| Cards only, 32 layouts | 0.433 ± 0.054 |
| List, 32 layouts | 0.245 ± 0.035 |
| List, up to 256 layouts | 0.210 ± 0.030 |
| Cards actually played | 0.426 ± 0.049 |

| Paired | Tricks per table | IMPs per table |
|---|---:|---:|
| List vs v5 | +0.172 ± 0.042 | +0.84 ± 0.23 |
| List at 32 vs v5 | +0.137 ± 0.044 | +0.68 ± 0.23 |
| v5 vs cards only | +0.051 ± 0.033 | −0.07 ± 0.17 |

- By trick, list vs v5: +0.064 ± 0.021 (trick 6), +0.052 ± 0.020 (7), +0.030 ± 0.014 (8), +0.019 ± 0.015 (9), +0.009 ± 0.009 (10).
- Declaring side +0.085 ± 0.031, defenders +0.087 ± 0.025.
- The list is solved in full in 43% of trick-6 decisions, 67% at trick 7, 86% at trick 8 and all from trick 9.
- Build time with the bidder check, per player, Python: 3.2 s at the start of trick 5 (48,620 candidates), 0.9 s at trick 6, 0.2 s at trick 7 (16 tables).

## Card choices (76 tables, episodes 600–718)

Each listed layout is weighted by how likely the hidden players' actual cards were in it: P(card) ∝ exp(−λ · double-dummy loss) over the legal cards, with λ fitted per situation on the 251 tables above (0.825 for the opening lead, 1.75 to 3.2 elsewhere).

- Log-probability of the true layout: −0.009 ± 0.076 nats per decision from weighting by every earlier play, +0.046 ± 0.037 from plays in tricks 6–12 only. No information gain is shown.
- Decisions: weighted vs unweighted list +0.127 ± 0.054 tricks per table (2.3 standard errors). Suggestive, not established; it is not explained by the information figure.
- The bots' plays are double-dummy correct on the true deal 96–98% of the time (opening leads about 80%), and 75–90% of legal cards lose nothing, so a loss-based choice model separates layouts weakly.
- The bidder-built list vs v5 repeats on this sample: +0.185 ± 0.053.

## Hand-fit scorer (no bidder at the table)

`fit.py`. A dense net (1,435,393 parameters) that outputs P(a hand would have made this seat's calls) from the hand type (suit lengths, honours A–T, high-card points), the seat, both vulnerabilities and the whole auction. A layout's weight is the product of the scores of the two hidden hands' original 13 cards. Like the bidder it does not see spot cards below the ten.

- Data (`gen_fit.py`): 230,010 random deals bid by the Gen5 bidder, 14 minutes in one process. For every seat: the true hand (fits by construction), 3 random hands and 5 hands made by swapping 1–8 cards of the true hand, each labelled by replaying the seat's calls with the bidder. 8,280,360 examples; 20% of the random hands and 33% of the near hands fit.
- Training: 22 minutes on two cores, 1.84 passes.
- Held-out deals (109,908 examples): correct side of 0.5 for 92.2% of true hands, 97.2% of random hands, 94.5% of near hands; mean score of true hands 0.867.

Grading in tricks 6–12 (400 tables, episodes 1000–1399, 9,426 decisions). The list holds every layout that fits the cards; no bidder is consulted for the scorer arms.

| Source | Cost, tricks per table |
|---|---:|
| v5, 32 layouts | 0.348 ± 0.039 |
| Cards only, 32 layouts | 0.386 ± 0.041 |
| Scorer-weighted, 32 layouts | 0.255 ± 0.035 |
| Scorer-weighted, 256 layouts | 0.242 ± 0.034 |
| Bidder-built list, up to 256 layouts | 0.217 ± 0.030 |

| Paired | Tricks per table | IMPs per table |
|---|---:|---:|
| Scorer 256 vs v5 | +0.106 ± 0.028 | +0.27 ± 0.11 |
| Scorer 32 vs v5 | +0.093 ± 0.027 | +0.18 ± 0.12 |
| Bidder list vs v5 | +0.132 ± 0.028 | +0.34 ± 0.14 |
| Bidder list vs scorer 256 | +0.025 ± 0.017 | +0.07 ± 0.11 |

Information about the true layout beyond cards and show-outs, nats per decision:

| Trick | v5 | Scorer | Bidder list | Median layouts, cards only | After bidding |
|---:|---:|---:|---:|---:|---:|
| 6 | 0.66 ± 0.04 | 1.88 ± 0.05 | 2.38 ± 0.06 | 6,435 | 330 |
| 7 | 0.57 ± 0.04 | 1.62 ± 0.04 | 2.06 ± 0.05 | 924 | 108 |
| 8 | 0.47 ± 0.03 | 1.38 ± 0.04 | 1.76 ± 0.05 | 252 | 36 |
| 9 | 0.36 ± 0.03 | 1.15 ± 0.04 | 1.44 ± 0.04 | 70 | 15 |
| 10 | 0.25 ± 0.02 | 0.85 ± 0.03 | 1.04 ± 0.03 | 20 | 6 |
| 11 | 0.16 ± 0.02 | 0.58 ± 0.02 | 0.71 ± 0.03 | 6 | 3 |
| 12 | 0.07 ± 0.01 | 0.30 ± 0.02 | 0.37 ± 0.02 | 3 | 1 |
| All | 0.36 ± 0.02 | 1.11 ± 0.03 | 1.39 ± 0.03 | 70 | 12 |

Scoring a player's list takes 0.048 s on average (0.18 s at most) against 0.9 s for the bidder check.

## Hand-type classes (every trick after the lead)

`classes.py`. The bidder and the scorer see a hand as A–T per suit plus a count of low cards. Layouts that give one hidden seat the same unseen honours and the same number of unseen low cards in each suit are interchangeable for the bidding. Such a set is a class; its multiplicity is the number of layouts in it. Weighting each class by its multiplicity times the two hands' scores (or bidder verdicts) gives the same posterior as listing every layout, from trick 1.

- Checks: on 139 decisions of the scorer-grading run the class sums equal the listed layout counts, cards-only and bidder-consistent, and the scorer's log-probability of the true layout agrees to 0.00005 (`test_classes.py`). On 75 positions the classes expand to exactly the brute-force layouts (`test_spaced.py`).
- Scores and verdicts are cached by hand type for the table, so each player's first decision carries nearly all the cost.

Concentration of the scorer posterior over classes (`conc.py`, 23 tables, medians):

| Trick | Classes | Effective number | Classes holding 99% | Mass of the 32 most likely |
|---:|---:|---:|---:|---:|
| 1 | 32,236 | 967 | 1,782 | 0.11 |
| 2 | 14,188 | 671 | 1,139 | 0.15 |
| 3 | 6,808 | 366 | 619 | 0.23 |
| 4 | 3,062 | 192 | 256 | 0.38 |
| 5 | 1,093 | 95 | 146 | 0.58 |
| 6 | 514 | 66 | 84 | 0.71 |
| 7 | 218 | 32 | 44 | 0.95 |
| 8 | 88 | 15 | 18 | 1.00 |
| 9 | 41 | 9 | 11 | 1.00 |

### Whole-play test (199 tables, episodes 1400–1599)

`play_classes.py`, `late_classes.py`, `late_v5x.py`. Every non-forced decision from trick 1 to trick 12 after the lead: 8,014 decisions, 40 per table. 32 layouts per source.

- **v5**: the bot's sampler on v5 logits, independent draws.
- **Cards only**: the bot's uniform sampler in tricks 1–5; in tricks 6–12 the layouts that fit the cards, picked at layout level.
- **Scorer on classes**, **bidder on classes**: in tricks 1–5, 32 classes spaced evenly through the cumulative posterior weight with the low cards dealt at random inside each. In tricks 6–12, layout-level picks: 32 spaced evenly through the cumulative weight over layouts, and every layout with its exact weight when 32 or fewer carry weight.

| Source | Tricks 1–5 | Tricks 6–12 | All tricks |
|---|---:|---:|---:|
| Cards only | 0.651 ± 0.067 | 0.380 ± 0.049 | 1.031 ± 0.090 |
| v5 | 0.567 ± 0.060 | 0.256 ± 0.038 | 0.824 ± 0.075 |
| Scorer on classes | 0.455 ± 0.053 | 0.188 ± 0.033 | 0.643 ± 0.062 |
| Bidder on classes | 0.473 ± 0.055 | 0.199 ± 0.034 | 0.672 ± 0.067 |

By trick: paired gains in tricks per table, information beyond cards and show-outs in nats per decision, and median sizes.

| Trick | Decisions | Scorer vs v5 | Ceiling vs v5 | v5 nats | Scorer nats | Bidder nats | Classes | Layouts, cards only | After bidding |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 552 | −0.005 ± 0.006 | −0.006 ± 0.008 | 0.68 | 2.22 | 2.82 | 31,558 | 5,200,160 | 235,885 |
| 2 | 719 | −0.005 ± 0.024 | −0.001 ± 0.023 | 0.85 | 2.40 | 3.03 | 16,062 | 1,352,141 | 57,102 |
| 3 | 705 | +0.069 ± 0.023 | +0.056 ± 0.024 | 0.82 | 2.21 | 2.83 | 7,218 | 352,709 | 17,508 |
| 4 | 690 | +0.044 ± 0.021 | +0.042 ± 0.027 | 0.77 | 2.11 | 2.68 | 3,062 | 92,374 | 5,004 |
| 5 | 684 | +0.008 ± 0.017 | +0.003 ± 0.018 | 0.68 | 1.89 | 2.42 | 1,238 | 24,309 | 1,379 |
| 6 | 674 | +0.054 ± 0.022 | +0.042 ± 0.027 | 0.64 | 1.67 | 2.15 | 480 | 6,435 | 468 |
| 7 | 659 | +0.005 ± 0.009 | +0.006 ± 0.009 | 0.54 | 1.47 | 1.86 | 196 | 1,716 | 164 |
| 8 | 684 | +0.008 ± 0.014 | +0.001 ± 0.013 | 0.45 | 1.30 | 1.65 | 82 | 462 | 48 |
| 9 | 653 | +0.000 ± 0.010 | +0.006 ± 0.010 | 0.36 | 1.08 | 1.36 | 30 | 70 | 16 |
| 10 | 656 | +0.003 ± 0.009 | +0.003 ± 0.009 | 0.26 | 0.82 | 1.05 | 14 | 20 | 6 |
| 11 | 672 | +0.000 ± 0.007 | +0.003 ± 0.005 | 0.17 | 0.55 | 0.70 | 6 | 6 | 3 |
| 12 | 666 | +0.000 ± 0.000 | −0.003 ± 0.003 | 0.09 | 0.28 | 0.35 | 2 | 3 | 1 |
| All | 8,014 | +0.181 ± 0.057 | +0.151 ± 0.060 | 0.52 | 1.50 | 1.91 | 276 | 1,716 | 247 |

- Nats per decision over the whole play: v5 0.525 ± 0.030, scorer 1.503 ± 0.047, bidder test 1.910 ± 0.056. The scorer's share of the bidder figure is 78–81% at every trick.
- Scorer vs v5 by side: declaring side +0.059 ± 0.039, defenders +0.121 ± 0.042.
- Scorer vs v5 by contract: suits +0.218 ± 0.060 (138 tables), notrump +0.097 ± 0.128 (61 tables).

How the layouts are picked, tricks 6–12 on the same tables:

- v5 with layout-level picks vs v5 as the bot draws it: −0.050 ± 0.027. The picking method does not explain the gain over v5.
- Both beliefs with layout-level picks: scorer vs v5 +0.119 ± 0.037, ceiling vs v5 +0.108 ± 0.036, v5 vs cards only +0.073 ± 0.038.
- Where 32 or fewer layouts fit the cards (1,914 decisions) the sources do not differ: 0.005 ± 0.009 or less.
- Layout-level picks vs class picks with random low cards: scorer +0.008 ± 0.015, bidder +0.037 ± 0.017.
- Cards only, layout-level picks vs the bot's uniform sampler: +0.070 ± 0.035.

Cost, Python and NumPy on one thread:

- Per table: class building 0.05 s, scoring 3.4 s (worst table 25 s), bidder checks for the ceiling arm 6.6 s. Mean hand types scored per table: 274,789.
- Per decision, scoring: median under 1 ms, 99th percentile 2.0 s, worst 23.7 s at a decision with 892,126 classes. A deployed version needs a cap or pruning for such positions; none was tested.

### Which layouts to solve

`select_layouts.py`, `analyze_select.py`. 80 tables (episodes 300–310 even and 326–399), 1,356 decisions in tricks 1–5. For each decision 512 layouts are drawn independently from the scorer posterior and solved: 256 form a pool and 256 are held out as the reference. A scheme chooses a card from the layouts it selects, and the choice is scored by the reference's mean double-dummy value. Every scheme uses the same belief, so this isolates the choice of layouts from the quality of the belief and carries no true-deal noise.

Tricks per table over tricks 1–5, relative to 32 independent picks:

| Scheme | Solves | vs 32 independent picks |
|---|---:|---:|
| Independent picks | 4 | −0.410 ± 0.035 |
| | 8 | −0.170 ± 0.020 |
| | 16 | −0.048 ± 0.011 |
| | 64 | +0.033 ± 0.009 |
| | 128 | +0.048 ± 0.009 |
| | 256 | +0.053 ± 0.009 |
| Classes spaced evenly through the cumulative weight (the play test's method) | 32 | −0.004 ± 0.012 |
| The 32 most likely classes, weighted by their mass | 32 | −0.092 ± 0.017 |
| Cluster centres, weighted by cluster size | 8 | −0.146 ± 0.020 |
| | 16 | −0.031 ± 0.014 |
| | 32 | +0.022 ± 0.008 |
| | 64 | +0.040 ± 0.009 |
| One random member per cluster, weighted by cluster size | 8 | −0.156 ± 0.025 |
| | 16 | −0.034 ± 0.012 |
| | 32 | +0.013 ± 0.012 |
| | 64 | +0.039 ± 0.009 |

- Clusters are k-medoids on the 256 pool layouts. Distance: L1 over one hidden hand's unseen cards (A 4, K 3, Q 2, J 1.5, T 1, lower cards 0.5) plus its suit lengths (2 per card, 3 in trumps). One hand-made distance; no other was tried.
- Layout count: 256 independent picks are worth 0.053 ± 0.009 over 32, and 64 give 0.033 ± 0.009 of that.
- Cluster centres against independent picks at equal solves: +0.024 ± 0.027 at 8, +0.017 ± 0.017 at 16, +0.022 ± 0.008 at 32, +0.007 ± 0.005 at 64. 32 centres are behind 64 independent picks by 0.011 ± 0.005.
- Cluster centres against evenly spaced classes at 32: +0.026 ± 0.009.
- The 32 most likely classes lose 0.092 ± 0.017 to 32 independent picks.
- These are expectations under the scorer posterior, not true-deal results. For scale, the scorer's gain over v5 in tricks 1–5 is 0.112 ± 0.047 on the true deal.
- Solving takes about 35 s per table per core for 576 layouts per decision.

## Limits and checks not run

- Double-dummy scoring of single decisions on positions the v5 bot reached. Summing decision costs per table treats them as additive; the bot's 0.125-trick window and selector are not modelled. No arena match.
- Common-auction self-play only. Against another bidder the scorer would be trained on that bidder's auctions, and the bidder test is no longer a ceiling.
- The scorer is a first version: one architecture, one training run, 22 minutes. It must be retrained when the bidder changes.
- Card choices are not used by any scorer or class arm. The one model tried (double-dummy loss) showed no information gain.
- Scorer and bidder arms take their layouts evenly spaced through the cumulative weight; v5 is drawn independently, as the bot draws it. In tricks 6–12 giving v5 the same picks did not help it. In tricks 1–5 that difference was not isolated against v5.
- The opening lead is not part of these tests; see the lead report.

## Files

Code and per-table results are in `analysis/auction_belief/`; the scorer is in `models/cardplay/hand-fit-scorer-v0-2026-11-11/` as 512 KiB parts with its log; `python restore.py` there rebuilds `hand_fit_v0.npz`. Nothing under `bridge_harness/` or `scripts/` is changed.

- `late_play.py`, `analyze_late.py` bidder-built lists in tricks 6–12. `time_lists.py` build times.
- `fit_lambda.py`, `late_play3.py`, `analyze_late3.py` card-choice weighting.
- `gen_fit.py` scorer training data. `fit.py` the scorer and its trainer.
- `late_net.py`, `analyze_net.py` scorer grading in tricks 6–12.
- `classes.py` hand-type classes. `test_classes.py`, `test_spaced.py` check them against layout listing and brute force.
- `play_classes.py` whole-play test. `late_classes.py`, `late_v5x.py` its tricks 6–12 again with layout-level picks, for the class arms and for v5 and cards only. `analyze_classes.py` reports all three. `conc.py` posterior concentration by trick.
- `select_layouts.py`, `analyze_select.py` which layouts to solve.
- `early_play.py`, `analyze_early.py` an earlier early-trick test by rejection sampling. Superseded by the class test; never run for results.
- `out/` results, gzipped: `late_*`, `late3_*`, `net_*`, `cls_*`, `clsx_*`, `clsv_*`, `sel_*`, and `lambda.json`.

Set `SDB_FEED` to the feed's `recovery` folder. Needs NumPy, h5py and autograd. Training data is not stored; `gen_fit.py` regenerates it from the seeds below.

```bash
cd analysis/auction_belief
export SDB_FEED=/path/to/feed/recovery
S=../../models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
python analyze_late.py && python analyze_late3.py && python analyze_net.py && python analyze_classes.py && python analyze_select.py   # tables from stored results
python late_play.py out/late_0.jsonl 0 254 2 0                       # offset 1 in a second process, here and below
python fit_lambda.py
python late_play3.py out/late3_0.jsonl out/lambda.json 600 720 2 0   # the stored run was stopped early: 59 even and 17 odd tables
python gen_fit.py data/fit_train.npz 2000 230000 && python gen_fit.py data/fit_val.npz 9 3000
python fit.py weights/fit 22 data/fit_val.npz data/fit_train.npz
python late_net.py $S out/net_0.jsonl 1000 1400 2 0
python test_classes.py $S && python test_spaced.py $S
python play_classes.py $S out/cls_0.jsonl 1400 1600 2 0
python late_classes.py $S out/clsx_0.jsonl 1400 1600 2 0
python late_v5x.py out/clsv_0.jsonl 1400 1600 2 0
python conc.py $S 1400 1424
python select_layouts.py $S out/sel_1.jsonl 326 400 2 1               # stored: sel_0 holds 300-310 even, sel_1 to sel_4 hold 326-399
```
