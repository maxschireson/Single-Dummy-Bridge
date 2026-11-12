# Policy net v4.1: the training run of 12 November 2026

**Status: finished at 07:40 UTC on 12 November 2026. A record of one run and of what was measured beside it.**
The net is in [models/cardplay/gen7-policy-v4.1-2026-11-12](../../models/cardplay/gen7-policy-v4.1-2026-11-12/README.md),
with its scores. This folder has the scripts that made it and what else was run beside it.

Max's instructions (12 November, UTC): train a 4.1 net on everything collected so far, the Gen 7
boards included (03:32); a temporary fifth Azure box for it, at most two hours up (03:40); hold no
data back at all, because new boards arrive fast enough to test on (03:54); 512 wide first, then
768 wide and a head trained on fork results; report epoch by epoch (04:00); test whether the tree
becomes additive with the better net (04:54); the box extended to 07:42 to see whether more epochs
help (05:25), then kept for Gen 8 work (05:59).

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
on pairs from sets B, C and D (deals the training set has are dropped): 26,449 pairs on 1,206 deals,
7,247 of them gap forks. Squared error against the realized cost of B, gap forks only:

| Predictor | Squared error | Minus the search's gap with a fitted slope |
| --- | --- | --- |
| Zero | 0.8446 | +0.3673 |
| The search's gap as recorded | 0.4864 | +0.0090 [+0.0050, +0.0129] |
| The search's gap, fitted slope (0.87) | 0.4773 | |
| The net's gap head, fitted slope | 0.5706 | +0.0933 [+0.0779, +0.1098] |
| Result head alone | 0.5656 | +0.0883 [+0.0729, +0.1045] |
| The search's gap + result head | 0.4736 | -0.0037 [-0.0056, -0.0019] |

The head adds a little to the search's gap (0.8% lower error) and cannot replace it. It does not
find better cards: on the 337 gap-fork pairs where the combined predictor preferred B, B gained
0.012 tricks on average. On the 19,202 audit pairs (two cards the search rated level, result
differs in 3.1%) nothing beats predicting zero. The search overstates the cost of its worse cards:
the fitted slope on its gap is 0.87.

Limits: one linear layer on a frozen net; a head trained with the net, or with more capacity, was
not tried. The test pairs come from 1,206 deals. Files: `result-head/result_head.json` and
`.log`; the pair sets are `data/pairs*.npz` on `transfer/gen7-policy-v4.1-box-20261112`.

## 768 wide, three epochs

The same data and recipe at `--width 768` (1,709,058 parameters), trained beside the 512-wide run.
Held-out tricks given up on set B by epoch: 0.0312, 0.0265, 0.0243 (512 wide: 0.0303, 0.0272,
0.0245). Fitted temperature 1.132. Against the 512-wide net (v4.1), same decisions:

| | 512 wide | 768 wide | 768 relative to 512 |
| --- | --- | --- | --- |
| Tricks given up, set C | 0.0256 | 0.0249 | 2.4% less [-1.9%, 6.7%] |
| Tricks given up, set B | 0.0245 | 0.0243 | 0.8% less [-3.3%, 4.7%] |
| Log-loss, set C | 0.608 | 0.597 | |
| Exact card, set C | 75.0% | 75.5% | |
| Gap head's card gives up, set C | 0.0216 | 0.0202 | |
| Training loss (card), epoch 3 | 0.572 | 0.539 | |

At three epochs the wider net is not measurably better in tricks and a little better in log-loss.
At epoch 1 it was behind (5.9% more given up on C, [0.9%, 11.7%]) and at epoch 2 ahead (6.2% less
on C, [1.9%, 10.2%]; 2.5% less on B, [-1.6%, 6.5%]). Its weights by epoch are on the box branch
(`runs/w768/`, and calibrated in chunked form under `packaged/gen7_policy_v4.1_w768/`).

## Every fresh board together

Set D is 182 more boards (80,123 decisions) fetched at 05:18 UTC. On C and D together (632 boards,
260,438 decisions) v4.1 gives up 0.0258 against v4's 0.0340: 24.2% less [21.1%, 27.2%]; lead 10%
[-6, 22], tricks 1-2 21% [12, 30], tricks 3-6 18% [14, 22], tricks 7-13 26% [22, 31]. Exponent on
training deals -0.35 [-0.40, -0.30], against -0.36 [-0.46, -0.25] for v3.1 to v4 on the same boards.

Logs: `eval512.log`, `eval768.log`, `final_eval.log`. Fetch manifests: `fetch1.json` (the training
set) and `fetchB.json`, `fetchC.json`, `fetchD.json`.

## Five epochs, 512 and 768 wide

The same data and recipe with the schedule stretched to five epochs (`--epochs 5 --save-epochs`),
each a fresh run: the learning rate falls over the whole run, so a finished three-epoch net
cannot simply be continued (the trainer has `--init` for that; it was not used). Tricks given up
on set B by epoch:

| Epoch | 512 wide, 3 | 768 wide, 3 | 512 wide, 5 | 768 wide, 5 |
| --- | --- | --- | --- | --- |
| 1 | 0.0303 | 0.0312 | 0.0301 | 0.0331 |
| 2 | 0.0272 | 0.0265 | 0.0309 | 0.0271 |
| 3 | 0.0245 | 0.0243 | 0.0259 | 0.0253 |
| 4 | | | 0.0251 | 0.0236 |
| 5 | | | 0.0247 | 0.0234 |

B is also the set the temperatures are fitted on (1.106 for 512 wide at five epochs, 1.201 for
768), so the comparisons below are on every other fresh set together: C, D, E and F, the last two
fetched at 06:18 and 07:18 UTC (1,387 deals, 591,450 decisions, none in the training set).

| Net | Tricks given up | Exact card | Log-loss | Training loss (card), last epoch |
| --- | --- | --- | --- | --- |
| v4 | 0.0336 | 72.9% | 0.667 | |
| 512 wide, 3 epochs (v4.1) | 0.0249 | 74.9% | 0.613 | 0.572 |
| 512 wide, 5 epochs | 0.0241 | 75.5% | 0.601 | 0.543 |
| 768 wide, 3 epochs | 0.0240 | 75.5% | 0.600 | 0.539 |
| 768 wide, 5 epochs | 0.0237 | 75.8% | 0.593 | 0.509 |

Paired on the same decisions, intervals from bootstrap draws of deals:

| Comparison | Tricks given up |
| --- | --- |
| 512 wide: five epochs against three (v4.1) | 3.2% less [0.4%, 5.9%]; on B 0.9% more [-2.9%, 4.7%] |
| 768 wide: five epochs against three | 1.4% less [-1.1%, 3.9%]; on B 3.5% less [-0.2%, 7.2%] |
| Five epochs: 768 wide against 512 wide | 1.8% less [-1.0%, 4.7%] |
| 768 wide, five epochs, against v4.1 | 5.0% less [2.3%, 7.8%]; on B 4.3% less [0.1%, 8.1%] |
| 768 wide, three epochs, against v4 | 28.6% less [26.5%, 30.7%] |

Width and epochs each give a few percent, together about five, against the 26% from v4 to v4.1.
The last epoch of the 768-wide run lowered the training loss by 0.025 and the held-out log-loss
not at all before temperature (0.5996 at epoch 4, 0.6008 at epoch 5; the trainer's own pick was
epoch 4), so more passes over this data would mostly fit it closer. After temperature epoch 5 is
the better of the two (log-loss 0.5939 against 0.5953 on B; tricks given up on C to F 0.0237
against 0.0239), and it is the one scored above. In every one of these nets the gap head's card
gives up less than the policy head's (768 wide, five epochs: 0.0184 against 0.0237).

Neither five-epoch net was packaged or launched. Their weights by epoch, plain and with the
temperature built in, are on the box branch under `runs/w512e5/` and `runs/w768e5/`. Logs:
`eval_w512e5.log`, `eval_w768e5.log`, `eval_direct.log`.

The first 768-wide five-epoch run died in its fourth epoch at 06:23:48 UTC: Ubuntu's daily
unattended upgrade ran `needrestart`, which restarts services whose libraries changed, and the
training unit was one. The rerun reproduced epochs 1 to 3 to the last digit.
`/etc/needrestart/conf.d/50-list-only.conf` (`$nrconf{restart} = 'l';`) stops that; the other
boxes have it now too.

## The play read as layout weights

The net's second use in Gen 7 is the reading: from the deal list on, each listed layout is weighted
by the net's probability of the hidden seats' plays. `scripts/gen7_check.py inference` at Gen 7's
settings (exponent 0.5, floor 0.05), with v4 and with v4.1 on the same 9,736 decisions of 481
fresh deals ([layout-weights/report.txt](layout-weights/report.txt), `infer_report.py`):

| | v4 | v4.1 | v4.1 minus v4 |
| --- | --- | --- | --- |
| Log-weight the true layout gains over the scorer's weights | +0.555 +- 0.015 | +0.613 +- 0.016 | +0.058 +- 0.009 |
| Double-dummy tricks saved a decision, against the scorer's weights | +0.0023 +- 0.0006 | +0.0031 +- 0.0007 | +0.0009 +- 0.0004 |

The scorer's weights alone cost 0.0072 tricks a decision there, so v4.1's reading removes 43% of
it and v4's 32%. In the same rows the true layout's gain keeps rising with the exponent (v4.1:
+0.411 at 0.25, +0.613 at 0.5, +0.696 at 0.75, +0.708 at 1.0); the cost was computed at 0.5 only.
The checks ran in a 2-core sandbox, not on the box: beside the training runs they slowed the
trainers by a third to a half.

## Near-tied cards, and the tree's overrides

Asked by the Gen 8 session after the run (box/coordination, 06:12 UTC): would the net choose well
among cards the search rates close together? `scripts/gen7_near_tie.py` scores selectors on the
fork pairs of fresh boards (40,161 pairs on 1,817 deals v4.1 did not train on); reports and logs
are in [near-tie/](near-tie/). Each pair is turned so that S is the card the search rated higher.

- On gap forks of 6-32's decisions with the two cards within 0.1 tricks (2,419 pairs), the other
  card costs 0.061 +- 0.011 tricks when played, and v4.1's policy prefers it in 20.8% of pairs,
  where it costs 0.052 +- 0.026. Following the policy there loses 0.011 +- 0.005 tricks and
  0.065 +- 0.022 IMPs a sampled pair; between 0.1 and 0.2, 0.022 +- 0.009 tricks. 7s-32's gap
  forks say the same with wider errors. The gap head and the result head do no better.
- Among level cards the results differ in 2.6% of 29,108 pairs; the policy's pick is worth
  +0.0013 +- 0.0007 tricks a pair over the card played, and v4.1's picks against v4's
  -0.0001 +- 0.0005.
- The audits of 7s-32's boards whose two cards are not level are the tree's overrides, played out
  against the search's card (`tree_overrides.py`, [near-tie/tree_overrides.txt](near-tie/tree_overrides.txt)):
  3,045 audited overrides on 1,909 deals, the tree's card +0.046 +- 0.014 tricks and
  +0.09 +- 0.07 IMPs; the 600 on boards fetched after the training set, +0.092 +- 0.032 tricks and
  +0.29 +- 0.14 IMPs. All of them are with v4.

## What this run does not show

- Whether any of these nets makes a bot stronger. The Gen 8 session's matches put Gen 7 with v4.1
  against Gen 7 with v4 at -0.010 +- 0.047 IMPs a board over 3,075 boards (box/coordination, 06:48
  UTC); the tree bench, the layout weights and the near-tie study above are the offline side of
  the same answer.
- Anything about play against other kinds of opponent: 95% of the fresh sets' decisions are 6-32's.
- A continuation of a finished net. One was started by mistake at 06:00 UTC and removed after
  35 seconds; nothing here comes from it.
