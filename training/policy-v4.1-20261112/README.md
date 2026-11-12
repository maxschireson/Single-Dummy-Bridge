# Policy net v4.1: the training run of 12 November 2026

**Status: a record of one run on a temporary machine. Work in progress while this note says so.**
The net is in [models/cardplay/gen7-policy-v4.1-2026-11-12](../../models/cardplay/gen7-policy-v4.1-2026-11-12/README.md),
with its scores. This folder has the scripts that made it and what else was run beside it.

Max's instructions (12 November, UTC): train a 4.1 net on everything collected so far, the Gen 7
boards included (03:32); a temporary fifth Azure box for it, at most two hours up (03:40); hold no
data back at all, because new boards arrive fast enough to test on (03:54); 512 wide first, then
768 wide and a head trained on fork results; report epoch by epoch (04:00); test whether the tree
becomes additive with the better net (04:54).

## What ran, in order

| Step | Script | Time on 8 cores |
| --- | --- | --- |
| Fetch every episode on `arena-gen6-*`, `arena-gen7-phase1-*` and `transfer/pre7-test-azure*`, one file per blob | `fetch_feeds.py` | 58 s for 38,207 episodes, 6.2 GB |
| Build the set in 16 parts and join them | `scripts/gen7_build_dataset.py`, `merge_sets.py` | 26 min; 38,128 boards, 13,239,367 examples |
| Held-out set B: what arrived since, minus deals the training set has | `fetch_feeds.py --seen`, `fresh_set.py` | 1 min; 631 boards |
| Train 512 wide on every deal | `scripts/train_gen7_policy.py --all-train --val-data` | 30 min (beside the 768-wide run) |
| Held-out set C, the same way, when that run ended | | 450 boards |
| Temperatures on B, the comparison on C | `evalnet.sh` | 5 min |

`chain.sh` is those steps as they ran on the box; `side.sh`, `after512.sh`, `after768.sh` and
`final_eval.sh` are the jobs that ran beside and after it. The manifests of the three fetches
(`fetch1.json`, `fetchB.json`, `fetchC.json`: every branch tip and count) and all logs are on branch
`transfer/gen7-policy-v4.1-box-20261112`, with every epoch's weights for both widths and the fork
pairs. The 10 GB training set is not kept; the first manifest and the builder reproduce it.

Changes to existing scripts: `scripts/train_gen7_policy.py` takes `--all-train` (train on every
deal of the set) and `--val-data` (held-out rows from a second set). Nothing else was changed.
New: `scripts/gen7_score_nets.py` (the trainer's per-epoch figures for any net on any set),
`scripts/gen7_pairs.py` and `scripts/gen7_result_head.py` (below).

## The tree with v4.1 (bench of 12 November, 05:04 UTC)

Max's question: is the better net enough to make the tree additive? `scripts/gen7_bench.py` on fresh
fork pairs, the launched tree (3 tricks, breadth 3, mass 0.98, stake rule 0.5 IMPs, 3,000 solves,
8 layouts, tricks 3 to 6) with v4 and with v4.1 on the same pairs:

    python scripts/gen7_bench.py --episodes FRESH --policy v4.npz --policy2 v4.1.npz --from-trick 3 --to-trick 6 \
      --tricks "0:plain=1;3:plain=1,breadth=3,mass=0.98,path=0.5,path_solves=3000;3:plain=1,breadth=3,mass=0.98,path=0.5,path_solves=3000,net=2"

FRESH is the 1,081 episodes of sets B and C on deals the training set does not have (622 Gen 6
self-play, 402 Gen 7 phase 1 without BEN, 57 with BEN). The Azure and Codex phase 1 records carry no
gap forks, so the pairs come from the Gen 6 self-play feed and the independent collector. The bench
read 2,613 pairs; 852 of them are at `7s-32`'s decisions, where the card played is not Gen 6's, and
`bench_report.py` drops them. Left: **1,761 pairs at 6-32's decisions on 666 deals, 1,378 sides.**

Under the bot's rule (margin 0.25, trust 0.3), per side per table against Gen 6's card, errors
clustered by deal (`scripts/gen7_sweep.py`):

| Tree with | Tricks | IMPs | Switches a side |
| --- | --- | --- | --- |
| v4 | +0.019 +- 0.055 | +0.106 +- 0.189 | 0.77 |
| v4.1 | -0.062 +- 0.055 | -0.022 +- 0.173 | 0.63 |
| v4.1 minus v4, same pairs | -0.081 +- 0.055 | -0.128 +- 0.151 | |

Neither tree is distinguishable from zero and neither is their difference. The rule switches the
card at 81 of the sampled pairs with v4 and 73 with v4.1 (36 in common), so this bench cannot
resolve small effects. At trust 0.125 the difference is +0.042 +- 0.036 tricks the other way.

Regression of the realized cost of B on Gen 6's gap and the tree's correction, per sampled pair:
the correction's coefficient is +0.251 +- 0.071 with v4 and +0.263 +- 0.082 with v4.1 (trust
supported 0.29 [0.14, 0.45] and 0.31 [0.12, 0.50]). The correction carries information with both
nets and the better net did not raise its share. v4.1's corrections are smaller (sd 0.282 against
0.321) and the two are correlated 0.66. Followed without the rule, either tree loses to the plain
search: -0.009 +- 0.008 tricks a pair with v4 and -0.011 +- 0.007 with v4.1.

Not measured here: the net's two other uses in Gen 7 (layout weights from trick 7, tie-breaks),
where v4.1's gain over v4 is largest. Only play measures those.

Files: `bench/rows.json.gz` (the bench's rows), `bench/bots.json` (who played each deal),
`bench/summary.json`, `bench/sweep_v4.txt`, `bench/sweep_v4.1.txt`.

## The result head (experiment E2 on the fleet's queue)

A fork pair records what a forced card B really did against the card played A. `scripts/gen7_pairs.py`
lists every pair with the row of its decision in the set: 722,589 pairs from the training boards
(169,601 gap forks, 552,988 audits; the two cards' results differ in 12.9%). `scripts/gen7_result_head.py`
fits one more decoder channel on those results by ridge regression, with v4.1 frozen, and scores it
on pairs from sets B and C (deals the training set has are dropped): 22,312 pairs on 1,024 deals,
6,161 of them gap forks. Squared error against the realized cost of B, gap forks only:

| Predictor | Squared error | Minus the search's gap with a fitted slope |
| --- | --- | --- |
| Zero | 0.8289 | +0.3611 |
| The search's gap as recorded | 0.4770 | +0.0092 [+0.0049, +0.0140] |
| The search's gap, fitted slope (0.87) | 0.4678 | |
| The net's gap head, fitted slope | 0.5595 | +0.0917 [+0.0759, +0.1081] |
| Result head alone | 0.5540 | +0.0862 [+0.0694, +0.1030] |
| The search's gap + result head | 0.4639 | -0.0040 [-0.0060, -0.0020] |

The head adds a little to the search's gap (0.8% lower error) and cannot replace it. It does not
find better cards: on the 285 gap-fork pairs where the combined predictor preferred B, B gained
0.018 tricks on average. On the 16,151 audit pairs (two cards the search rated level, result
differs in 3.2%) nothing beats predicting zero.

Limits: one linear layer on a frozen net; a head trained with the net, or with more capacity, was
not tried. The test pairs come from 1,024 deals. Files: `result-head/result_head.json` and
`.log`; the pair sets are `data/pairs*.npz` on `transfer/gen7-policy-v4.1-box-20261112`.

## Still running when this was written

- The 768-wide run on the same data, and one more batch of fresh boards (set D) to score every net on.

Their results will be added here.
