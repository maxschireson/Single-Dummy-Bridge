# E9-3: how often spot cards nine and below are not equivalent

Gen 9 research (sam, signals), 12 November 2026. Experiment file: `experiments/E9-3.md` on
branch `team/gen9`. Kind of evidence: double-dummy proxy on the true deal. Nothing adopted.

**Data.** `arena-gen7-phase1-azure1-feed` at `f9dad79`, all 828 episodes, main tables only
(forks skipped). Every card played where the player held two or more spots (two to nine) in the
suit of the card played: 40,073 decisions, 21,057 of them by defenders. Each position was solved
by DDS on the true deal before the card was played. `rows.jsonl.gz` has one row per decision;
`tables.txt` is the output of `scripts/gen9_spot_equivalence_report.py`.

**Result.** Defenders: the spots did not all take the same number of tricks in 1.49% ± 0.08% of
decisions (registered threshold: below 5% keeps the class rule; below 90% equivalence would
change it). When they differed, the worst spot cost 1.13 tricks on average, and the lowest spot
was among the best in 99.2% of all decisions.

| Slice (defenders) | Decisions | Spots differ |
| --- | ---: | ---: |
| Discarding | 4,975 | 0.48% |
| Following, declarer's side led | 8,111 | 1.74% |
| Following, partner led | 3,534 | 1.75% |
| Leading (after trick 1) | 2,910 | 1.96% |
| Opening lead | 1,295 | 1.00% |
| Ruffing | 232 | 7.33% |
| Top spot a nine / an eight / seven or lower (not leading) | 5,666 / 4,006 / 7,180 | 2.82% / 1.17% / 0.91% or less |
| Trump suit / side suit at suits / side suit at no-trump (not leading) | 1,861 / 11,046 / 3,945 | 3.22% / 0.91% / 2.13% |
| No outstanding card above the top spot (not leading) | 1,082 | 4.99% |
| Five or more outstanding above (not leading) | 4,343 | 0.25% |
| Tricks 10 to 12 (not leading) | 2,398 | 0.6% to 1.2% |
| Declarer's own spots / dummy's | 9,478 / 9,538 | 3.62% / 2.03% |

**The search's ties.** From each decision's record (`proposal_probabilities`, else
`behavior_probabilities`): in 91.5% of defender spot plays the search's exactly tied set held
every spot of the class. Where it did, the spots differed on the true deal in 0.10% of
decisions; where it did not (8.5%), in 15.5%, and in 57% of those only one spot was left tied.

**Limits.** One feed (Gen 7 phase 1 on azure1: the Gen 7 standard bot against Gen 6, Gen 5 and
Gen 1), so the decisions are those bots' choices of which suit to play; a population with other
habits could meet spots in other positions. Double-dummy value on the true deal is a proxy for
what a single-dummy player gives up.

**Reproduce.** Build DDS (`scripts/build_dds.py`), check out the feed's `recovery/episodes`, then
`python scripts/gen9_spot_equivalence.py EPISODES --out rows.jsonl --decisions 1000000` (about four
minutes on two cores) and `python scripts/gen9_spot_equivalence_report.py rows.jsonl`.
