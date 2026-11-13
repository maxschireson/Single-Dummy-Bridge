# Conditional claims: reference solver and measurements

13 November 2026. Branch `research/conditional-claims-20261113`, stacked on `research/sure-trick-table-20261112`
(`6032cd5`), whose `pooled_ref.py`, `sure.cpp`, `bench_lines.json` and ending-table counterexamples the checks use.
Nothing here is in a bot or adopted. `DESIGN.md` is the design; this file is what was measured.

Evidence: a solver's analysis of recorded play. No double-dummy proxy, and no play by a bot that uses any of it.

| Provenance | |
| --- | --- |
| Recorded tables | feed branch `arena-gen8-azure1-feed` at `210f7b2`, `arena/replays/data/b9900c30…/boards-00000.json` to `boards-00005.json`: 600 boards, 1,520 distinct played tables, 590 deals at 8 cards |
| Layout weights | `recovery/artifacts/gen6/scorer.npz` of the same feed (SHA-256 `56e64440…2245e73`, the hand-fit scorer its Gen 6 to Gen 8 bots name), through `bridge_harness/gen6_nets.py` of `feature/gen8x-rollout-bot-20261113` (`6cded27`) |
| 8X code read for `DESIGN.md` | `feature/gen8x-rollout-bot-20261113` at `6cded27` |
| Raw result lines and the extracted positions | branch `transfer/conditional-claims-raw-20261113` (gzip, with a manifest) |
| Errors | standard errors with the deal as the unit |

## 1. Contents

| File | What it is |
| --- | --- |
| `cells.cpp` | Reference solver for the cell game: knowledge is a set of cells (East's length in each suit, plus the holder of each named card), one yes/no question per set. No ending table. |
| `celllib.py` | Driver, cell enumeration, and `Brute`: the same question over explicit layouts, no pruning. |
| `pipeline.py` | One decision: single-cell answers, ceilings, the joint step, refinement by named cards. |
| `belief.py` | Layout weights from the arena's hand-fit scorer (needs the repo for `bridge_harness/gen6_nets.py`). |
| `arena_positions.py` | Declarer-side decisions from recorded tables, as solver positions. |
| `study.py`, `report.py`, `saves.py` | The main study and its tables. |
| `extra_cost.py`, `extra_report.py` | Cost details: shapes in weight order, one-card searches, nodes a 4-card table would replace. |
| `allruns.py`, `allruns_report.py` | Every run of unseen cards named in turn. |
| `ddrules.py`, `ddrules_report.py`, `rule_diffs.py`, `lost_lines.py` | Certified probability against double-dummy value, card by card, and the lines dropped later (section 8). |
| `targets.py`, `targets_report.py` | One trick fewer and one trick more than the contract (section 8). |
| `check_cells.py`, `check_k3.py`, `stress_def.py`, `calib.py`, `xcheck_sure.py`, `xcheck_def.py`, `e2e_check.py` | Checks. |
| `results/` | Tables as printed and check logs. The raw result lines are on `transfer/conditional-claims-raw-20261113`. |

## 2. In brief

Positions: the first decision by declarer or dummy with 8 (and with 7) cards in hand, contract not yet settled, in
1,520 played tables of one Gen 8 arena feed. Declaring bots: `8s-32`, `8c-32`, `71s-32`, `5RZ32`, `1`; none has
claim logic. Weights: the arena's hand-fit scorer over every card-fit layout. The auction only: the bots' reading of
the play is not included.

| | 8 cards | 7 cards |
| --- | --- | --- |
| Positions | 1,450 | 1,405 |
| Some card guarantees the contract outright | 647 (44.6%) | 745 (53.0%) |
| No outright claim | 803 | 660 |
| of these, certified probability of the best card, shapes only: mean | 0.356 ± 0.017 | 0.324 ± 0.018 |
| 0.5 or more | 307 (38.2%) | 227 (34.4%) |
| 0.9 or more | 143 (17.8%) | 105 (15.9%) |
| no cell certified for any card | 223 (27.8%) | 233 (35.3%) |
| with two named cards: mean | 0.451 (+0.094 ± 0.007) | 0.410 (+0.085 ± 0.007) |
| with three named cards: mean | 0.453 | 0.413 |
| Cost of the shape level, this solver, one thread, no table: mean / median / 99th | 117 / 39 / 1,136 ms | 17 / 6 / 139 ms |

"Certified probability" is the weight of the cells one line wins, against best defence.

## 3. Checks

| Check | Result |
| --- | --- |
| `cells.cpp` against brute force over explicit layouts: random 2-, 3- and 4-card endings with random show-outs, cell subsets, 0 to 2 named cards, and positions inside a trick | 14,533 compared (854 / 12,720 / 959 by size), 0 mismatches, for each of four defender-card rules |
| `pooled_ref.py` against the same brute force (every shape; one whole shape) | 9,600 compared, 0 mismatches |
| The table build's 114 three-card counterexamples to the two-ends defender rule | every card, low-middle-high and middle-only give the plain value in all 114; two-ends gives the wrong value in all 114 |
| Reduced defender rules against trying every card, random 3- to 6-card endings, three kinds of knowledge each | 2,250,000 values: low-middle-high 0 differences, middle-only 0, two-ends 18 |
| The same on recorded 6-, 7- and 8-card positions (outright, per shape, joint) | 29,085 answers: low-middle-high 0 differences, middle-only 0 |
| Outright answers against `sure_cpp` on all 2,855 recorded positions | 14,623 card answers, 0 differences |
| Refined sets (sub-cells of a certified set) asked again as one question | 0 failures in the study |
| Recorded play, 1,518 tables, every turn of declarer or dummy with 9 cards or fewer: the cell is the actual shape; once a card played keeps a guarantee in that cell, a guarantee must still exist at the declaring side's next turn, and a table that keeps one to the end must make (`e2e_check.py`) | 27,324 turns; guarantee held at 17,899 and kept by the card played at 17,791; lost without a declarer deviation 0 times; 1,047 tables kept it to the end, all made. Replayed trick counts equal the record in all 1,518 |

- The two-ends rule is the one in `sure.cpp` and `sure.py` today. It leaves the defenders fewer cards, so its
  errors can only favour declarer. On the 2,855 recorded positions it changed no outright answer.
- The 4-card brute-force checks are few (959): each takes about a second in Python.
- No independent solver checks 7- and 8-card answers beyond the agreement with `sure_cpp` on the outright
  question. The recorded-play row is the check on whole-shape answers at those sizes: it would catch a guarantee
  that real defenders broke. It does not test sets of several cells or named cards.

## 4. Yield, shapes only

No outright claim; scorer weights; `results/report8_all.txt`, `report7_all.txt` (uniform weights are there too).

| | 8 cards (803) | 7 cards (660) |
| --- | --- | --- |
| Shapes consistent with hand sizes and show-outs: median / 90th / max | 40 / 72 / 85 | 19 / 52 / 60 |
| Shapes holding 90% / 95% / 99% of the scorer weight, median | 7 / 9 / 11 | 5 / 6 / 8 |
| the same with uniform weights | 20 / 24 / 32 | 10 / 12 / 16 |
| Floor of the best card, mean | 0.356 | 0.324 |
| Ceiling of the best card (cells one at a time), mean | 0.376 | 0.342 |
| Ceiling minus floor above 0.01 | 174 (21.7%) | 107 (16.2%) |
| above 0.10 | 58 (7.2%) | 37 (5.6%) |
| Joint step settled by its first question, best card | 282 of 580 (48.6%) | 239 of 427 (56.0%) |

- Adding up per-shape answers overstates in about a fifth of the positions. The joint step is what makes the number
  a floor.
- The joint step is greedy, so the floor may be below the best possible set. The ceiling bounds the difference:
  0.020 on average at 8 cards.

Claimed against realised, 8 cards (the actual layout is known from the record):

| Floor of the best card | Positions | Mean floor | Actual layout inside the certified set |
| --- | --- | --- | --- |
| below 0.25 | 212 | 0.035 | 0.038 |
| 0.25 to 0.50 | 61 | 0.382 | 0.311 |
| 0.50 to 0.75 | 89 | 0.608 | 0.494 |
| 0.75 to 0.90 | 75 | 0.826 | 0.680 |
| 0.90 and above | 143 | 0.975 | 0.937 |

The scorer's weights overstate the certified probability by 4 to 15 points above 0.25 (7 cards: the same pattern).
Two things are mixed in that gap and not separated here: the weights ignore the play, and the best card is the one
with the highest claim.

## 5. Named cards

Candidates in the main study: the top card of a run of unseen touching cards with a North-South card below it, single
cards first; up to three per position. Each level refines the one above.

| Scorer weights, no outright claim | 8 cards (803) | 7 cards (660) |
| --- | --- | --- |
| Shapes only | 0.356 | 0.324 |
| First candidate named | 0.418 | 0.384 |
| Best of up to three, one named | 0.441 | 0.402 |
| Two named | 0.451 | 0.410 |
| Three named | 0.453 | 0.413 |
| Two named add 0.20 or more | 19.9% | 17.1% |
| Nodes, mean: shape level / one named card / two / three | 945k / 779k / 906k / 1,459k | 140k / 117k / 128k / 197k |

Of the 2,409 cards named at 8 cards, 1,002 (42%) were a nine or lower. Mean gain by the rank of the named card:
A 0.082, K 0.078, Q 0.074, J 0.036, T 0.026, 9 0.013, 8 and lower under 0.01.

Every run named in turn, 300 positions without an outright claim per card count (`results/allruns_report.txt`):

| | 8 cards | 7 cards |
| --- | --- | --- |
| Shapes only | 0.386 | 0.359 |
| Best of the three the rule picks | 0.472 | 0.426 |
| Best of every run | 0.494 | 0.447 |
| Runs adding 0.05 or more, by class: top / middle / bottom / free | 15.1% / 8.6% / 1.6% / 1.5% | 12.8% / 8.4% / 1.4% / 1.2% |
| Positions where the best run adds 0.05 or more | 120 | 91 |
| its class: middle / top / bottom / free | 68 / 50 / 1 / 1 | 49 / 40 / 1 / 1 |
| its card a nine or lower | 7 | 6 |
| the three-card rule misses it by more than 0.02 | 37 | 24 |
| Bottom run (unseen cards under declarer's lowest of the suit): positions where it adds 0.05 or more | 9 of 281 | 7 of 277 |

No bottom run added 0.20 or more. With the length fixed by the cell, naming the one card under declarer's lowest
also fixes how many of the higher unseen cards each defender holds, so part of that gain is the count and not the
duck.

## 6. Cost

Nodes of `cells.cpp`, low-middle-high defender rule, no ending table. In the study its searches ran at about 120 ns
a node on one thread of a shared 2-core VM; `sure_cpp` without a table ran at 90 to 170 ns a node on the same
machine.

Main study, positions without an outright claim:

| Nodes | 8 cards: median | mean | 90th | 99th | 7 cards: median | mean | 90th | 99th |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Outright question | 13k | 50k | 132k | 547k | 3k | 10k | 24k | 94k |
| One search per shape, every shape, every card | 297k | 741k | 2,050k | 4,973k | 50k | 118k | 320k | 911k |
| Joint step | 7k | 203k | 547k | 2,923k | 0.5k | 22k | 68k | 339k |
| Shape level in all | 347k | 945k | 2,607k | 8,116k | 52k | 140k | 381k | 1,121k |

Cost details, 300 positions per card count (150 at 9), claims included (`results/cost_report.txt`). Mean nodes:

| Cards | Shapes, median | for 99% of weight | Per-shape searches, every shape | 99% of the weight | one card only, 99% | Joint step, best card |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | 12 | 5 | 13k | 8k | 2k | 2k |
| 7 | 19 | 8 | 88k | 42k | 14k | 11k |
| 8 | 28 | 11 | 519k | 218k | 62k | 102k |
| 9 | 58 | 16 | 3,265k | 1,481k | 458k | 1,180k |

- About six times the nodes for each extra card.
- Stopping at 99% of the scorer weight: 2.4 times fewer nodes at 8 cards (measured in weight order, not scaled).
- Asking about one card instead of all (5.5 runs of legal cards on average at 8): 3.5 times fewer.
- A 4-card ending table: counting the nodes with more than four cards left plus one lookup per 4-card boundary,
  2.2 to 2.8 times fewer for the outright question and the per-shape searches at 8 cards. That is an estimate from
  node depths. No table was read, and for the joint step the table has no entry to read (`DESIGN.md` 3.5).
- At 9 cards the joint step's 99th percentile is 18 million nodes.

## 7. Recorded outcomes

What the record shows about contracts that failed (scorer weights; `results/saves_report.txt`). "Sure" means the
actual layout was inside the certified set of the card with the highest floor, so that line makes against any defence.

| | 8 cards | 7 cards |
| --- | --- | --- |
| Outright claim available, contract then went down | 5 | 5 |
| No claim; went down; shape-level line sure on the actual layout | 13 | 7 |
| the same with two named cards | 21 | 13 |
| No claim; bot made with another card; actual layout outside the best card's set (shape level) | 66 | 37 |

Tables with a sure make at 8 or 7 cards that went down: 32 of 1,520. 6 through an outright claim, 13 more through a
shape-level line, 13 more only with two named cards.

By the floor of the best card, 8 cards, shape level, positions where the bot played another card:

| Floor | Positions | Went down, line was sure | Made, layout outside the set |
| --- | --- | --- | --- |
| 0.50 and above | 151 | 8 | 15 |
| 0.75 and above | 110 | 6 | 6 |
| 0.90 and above | 72 | 4 | 1 |

The last column is not a count of losses: the result after switching cards is unknown there. Nothing here was
played.

## 8. Certified probability against double-dummy value (added after the first push, same day)

Question: at an 8-card decision, can the certified probability replace the double-dummy value?
`ddrules.py` gives, for every card of every position without an outright claim: its certified probability (shapes;
two named cards), its double-dummy value D on 256 layouts drawn by scorer weight, and whether it makes double dummy on
the actual layout. Double dummy here is `cells.cpp` with every unseen card named. A card certified on the actual
layout was double-dummy making there in every case.

The card the bot played, by what the actual layout was for it (`results/ddrules8.txt`, `ddrules7.txt`):

| | 8 cards: positions | made | 7 cards: positions | made |
| --- | --- | --- | --- | --- |
| Inside its certified set (shapes) | 249 | 96.0% | 190 | 96.8% |
| Double-dummy making, not certified | 173 | 82.1% | 117 | 82.9% |
| Not double-dummy making | 381 | 4.7% | 353 | 3.4% |
| With two named cards: inside / double-dummy making only | 311 / 111 | 94.9% / 77.5% | 232 / 75 | 95.7% / 78.7% |

The bot's card by its double-dummy value, 8 cards: D = 1.00 made 94.7% (132 positions); mean D 0.958 made 80.7%;
0.822 made 74.8%; 0.632 made 50.5%; 0.372 made 28.4%. Among the cards with D = 1.00: certified 0.9 or more made
78 of 78, the others 47 of 54.

Rules for choosing the card, scored by what their card was on the actual layout: 1 if inside its certified set
(the line kept), otherwise the conversion rate above. Expected makes minus those of "double-dummy value, ties by
certified probability" (`results/rule_diffs.txt`; errors by deal, conversion rates taken as given):

| Rule | 8 cards, shapes (803) | 8 cards, two named | 7 cards, shapes (660) | 7 cards, two named |
| --- | --- | --- | --- | --- |
| Certified probability only, ties by double-dummy value | -8.5 ± 3.2 | -6.6 ± 3.9 | -1.2 ± 2.3 | -0.2 ± 2.6 |
| Certified + 0.50 × (DD - certified) | +0.4 ± 1.5 | +1.9 ± 2.6 | +0.5 ± 2.0 | +2.8 ± 1.9 |
| Certified + 0.75 × (DD - certified) | +0.2 ± 1.4 | +1.2 ± 2.0 | +2.1 ± 1.4 | +1.9 ± 1.3 |
| Double-dummy value, ties at random | -0.4 ± 0.6 | -0.3 ± 0.6 | -0.9 ± 0.3 | -0.7 ± 0.3 |

- Certified-only loses where certification is partial: in the 143 positions at 8 cards whose best certified
  probability is 0.9 or more it changes the expected makes by +0.2; below that by -8.7 in all.
- The double-dummy value ties at the top between two or more cards in 474 of the 803 positions; the tied cards differ
  by more than 0.05 in certified probability in 39.
- This scores one decision. The rules' later play is not simulated.

Lines dropped later (`results/lost_lines8.txt`). In 16 tables the bot's own card at 8 cards left the actual layout
inside a certified set (10 at the shape level, 6 more with two named cards) and the contract went down; 13 are games,
slams or doubled. At the turn where the card played dropped the line, a card guaranteeing the contract outright
existed in 3. In the other 13 only the conditional line existed. The count is one-sided: it takes the tables where the
line's condition held, and says nothing of what keeping to a line costs where it did not.

Other targets, shape level, 600 positions at 8 cards, each target searched on its own (`results/targets8.txt`):

| | |
| --- | --- |
| Contract guaranteed outright | 271; an overtrick also outright in 105; otherwise its certified probability 0.377 on average |
| No outright claim | 329; one down guaranteed outright in 151 |
| Mean certified probability there: contract / one down / overtrick | 0.378 / 0.766 / 0.083 |
| Nothing certified at the contract (107) | one down: outright in 19, certified 0.9 or more in 35, nothing in 37 |
| Best card for the contract and best card for one down differ | 25 of 97 positions where both exist and one down is not outright |
| Went down two or more (58) | one down was outright in 2; the actual layout was inside the best one-down set in 3 |
| Nodes, mean: contract target / the two other targets together | 445k / 717k |

## 9. Run

```
g++ -O2 -march=native -std=c++17 -o cells cells.cpp
python check_cells.py 3 1500 --seed 2 --pooled ..
python check_k3.py ../endtable/k3_defender_rule_counterexamples.txt
python stress_def.py 4 300000 --seed 22
python calib.py ../bench_lines.json ../sure_cpp 9 ; python -I e2e_check.py 9 boards-00000.json ...
python arena_positions.py positions.jsonl 9,8,7,6 boards-00000.json ...      # arena/replays/data/<id>/ in a feed branch
python study.py positions.jsonl out8.jsonl 8 --repo REPO --scorer recovery/artifacts/gen6/scorer.npz
python report.py out8.jsonl ; python saves.py b out8.jsonl -- out7.jsonl
python extra_cost.py positions.jsonl cost8.jsonl 8 300 --repo REPO --scorer SCORER ; python extra_report.py cost8.jsonl
python allruns.py positions.jsonl allruns8.jsonl 8 300 --repo REPO --scorer SCORER ; python allruns_report.py allruns8.jsonl
python ddrules.py positions.jsonl dd8.jsonl 8 --repo REPO --scorer SCORER --samples 256 ; python ddrules_report.py dd8.jsonl ; python rule_diffs.py dd8.jsonl
python -I lost_lines.py dd8.jsonl -- boards-00000.json ... ; python targets.py positions.jsonl tgt8.jsonl 8 --repo REPO --scorer SCORER --limit 600 ; python targets_report.py tgt8.jsonl
```

Run from this folder. `REPO` is a checkout that has `bridge_harness/gen6_nets.py`. Solver input and output are
described at the top of `cells.cpp`. The tables in `results/` print standard errors that treat positions as
independent; the by-deal figures quoted above are 0.003 larger for the floors.

## 10. Limits

- One feed, 1,520 tables, the first declarer-side decision at each card count. Bots without claim logic.
- Weights from the hand-fit scorer alone; no reading of the play.
- No bot has played with any of this; section 7 counts sure makes that were missed, not IMPs.
- The joint step is greedy.
- Times are from a prototype without an ending table; the table's effect is estimated, not run.
- The named cards of the main study come from a fixed rule that section 5 shows is not the best one.
- Section 8 scores choice rules on one decision with conversion rates measured on these bots' own play; it is not
  a played comparison.
- Node caps: 20 million a question in the study (never reached at 7 and 8 cards), 30 million in the cost runs.
