# Gen 7: phase 1 is authorized. Notice for the collectors (12 November 2026)

**Status: phase 1 is authorized. Phase 2 is not.** For the team controlling the workers. Branch
`feature/gen7-candidate-20261111`, cut from `feature/gen7-alpha-20261111` (`7690c3c`), which is cut
from `main` at `b0909bb`. The go-ahead is the commit that opened the phase 1 plan files; prepare
cohorts from that commit or a later one on this branch.

Max's instructions. 11 Nov, 23:29 UTC: tell the workers that Gen 7 is coming and give them the
match mix and a candidate build package. 12 Nov, 02:09 and 02:16 UTC: launch Gen 7 in the arena
with the mix as discussed; the standard bot's tree is margin 0.25, trust 0.3, `path` 0.5, 3 tricks.

Open: the five cross matches of phase 1, to 2,000 boards a pair. Closed: phase 2 (volume, with
self-play), which waits for phase 1 and for the self-play runtime to carry the `gen7` engine.
Nothing here changes Gen 6 data or scores, and this page stops no running collector: which
collectors move to Gen 7, and when, is Max's instruction to each of them.

## The bots

Each is Gen 6 fast (`6-32`: same bidder, lead net, hand-fit scorer, layouts, 32 samples) with
`engine: gen7` and policy net v4. The settings are spelled out in the plan files.

| Id | Label | What it adds to Gen 6 fast | Phase |
| --- | --- | --- | --- |
| `7s-32` | Gen 7 standard (32) | Layouts weighted by the play so far from trick 7 (`play_weight` 0.5); exact ties broken by the net; the tree search at tricks 3 to 6 | 1 and 2 |
| `7f-32` | Gen 7 fast (32) | The same without the tree | 2 |

The standard bot's tree, as set by Max: cards within 0.25 tricks of the search's best
(`root_margin`), at most 3; value = the search's estimate + 0.3 x the tree's correction (`trust`);
the stake rule with `path` 0.5 IMPs, limits of 3 tricks and 3 cards a node, 8 layouts, spot-card
mode (`plain` 1), replies averaged over the net's likely cards; budgets `path_solves` 3,000 a
candidate and `max_solves` 12,000 a decision. [The alpha guide](gen7_alpha_2026-11-11.md) explains
every setting, the stake rule included. The candidate of 11 November had trust 0.25; nothing else
in the bot changed at the go-ahead.

## The match mix

From `configs/gen7-candidate-mix.json`. The phases are separate plan files because a plan has one
set of pair weights. The file names keep "candidate" so that what was rehearsed still points at
them; the campaign names are `gen7-phase1-20261112` and `gen7-phase2-20261112`.

**Phase 1, open: cross-matched, for feedback before volume.** Equal weights, until every pair has
2,000 completed boards over all collectors together (10,000 in all):

| Pair | Purpose |
| --- | --- |
| `7s-32~6-32` | The generation comparison: standard against Gen 6 fast |
| `7s-32~ben64`, `7s-32~ben` | Anchors: BEN (64) and BEN (16) |
| `7s-32~5RZ32`, `7s-32~1` | Anchors: Gen 5 (32) and Gen 1 |

Three plan files hold it, with the same bot, net and settings in each:

| Plan | Pairs | For |
| --- | --- | --- |
| `configs/round7-candidate-phase1.json` | All five | A machine with both BEN servers |
| `configs/round7-candidate-phase1-nonben.json` | `7s-32` against `6-32`, `5RZ32`, `1` | A machine without BEN |
| `configs/round7-candidate-phase1-ben.json` | `7s-32` against `ben64`, `ben` | The BEN pairs alone, on a machine with BEN |

**Phase 2, closed: volume** (`configs/round7-candidate-phase2.json`). Shares of boards, as weights
in twentieths:

| Pair | Share | Weight |
| --- | --- | --- |
| `7f-32~7f-32` | 30% | 6 |
| `7s-32~7s-32` | 30% | 6 |
| `7s-32~6-32` | 20% | 4 |
| `7s-32~ben64`, `7s-32~ben`, `7s-32~5RZ32`, `7s-32~1` | 5% each | 1 each |

A self-play board is one table. A two-bot board is two tables on one deal, so in tables and in
compute the two-bot pairs weigh about double their share of boards. Self-play supplies training
data and has no IMP comparison, as for Gen 6.

**Audits.** `7s-32~6-32` keeps the cohort's tie audits and gap forks, and the standard bot's tree
audits (`tree_audit` true: where the tree changed the card, the fork plays the card without the
tree). BEN boards carry none (`ben_audit`). Max allows audits off in any anchor pair; for `5RZ32`
and `1` there is no per-pair switch in this runtime, so those boards carry the cohort's audits.

## Launch steps, phase 1

On a checkout of this branch at the go-ahead commit or later:

1. Restore the split model files (`models/*/*/restore*.py`; v4 is sha256
   `d6b011937ee9ec534ef957061634d9624c5aad56f4c0827ca6c9207bec65dd13`), build DDS
   (`python scripts/build_dds.py`) and run the Gen 7 tests:
   `python -m unittest discover -s tests -p "test_gen7*.py"` (54 tests; they need the native DDS
   library and TensorFlow for the lead net).
2. Pick the plan from the table above. The BEN bots are reached at the `url` in the source run's
   bot specs (`http://127.0.0.1:8087` for BEN (16) and `:8089` for BEN (64) in the capsule below).
   The collector stops on the first failed board, so a BEN pair on a machine without its server
   stops the run.
3. Pick the source: a drained Gen 6 run whose bots include `6-32`, `5RZ32`, `1`, the audit
   reference `3` and, for a BEN plan, `ben64` and `ben`. The one checked here is the recovery
   capsule of `arena-gen6-gen7-capture-feed` at `8833c62` (manifest `a76a39f1...`, 22,508 unplayed
   deals).
4. Prepare: `python ops/prepare_gen7_alpha.py --source DRAINED --run NEW_RUN --plan PLAN [--shard K/N]`.
   **Machines that share a source run must each pass their own shard**: the same N on all of them
   and K from 0 to N-1. Each then gets every N-th unplayed deal starting at the K-th, and no deal
   is played twice. Without `--shard` a cohort takes every unplayed deal of its source, so two
   unsharded cohorts from one source would play the same deals.
5. Preflight: `python ops/smoke_gen7.py --run NEW_RUN --out report.json`. It plays two boards of
   every Gen 7 pair except BEN (16) and fails if a record does not add up or the tree is never
   consulted. With a BEN plan it needs the BEN (64) server up.
6. Start `python ops/gen5_runtime.py --run NEW_RUN --workers W` under the collector's usual
   supervision and thread settings. The box test on `azure1` ran 8 workers with one BLAS, OpenMP
   and TensorFlow thread each (`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
   TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1`).
7. Watch `by_pair` in `NEW_RUN/state.json`. Phase 1 ends when every pair has 2,000 completed
   boards over all collectors together; then write `NEW_RUN/STOP`. A plan has no per-pair target,
   so a pair that reaches 2,000 early keeps being scheduled until the collector is stopped.
8. Report: `python scripts/gen7_alpha_report.py --episodes NEW_RUN/episodes`.

A prepared run pins `bridge_harness/`, `scripts/`, `ops/gen5_runtime.py` and
`ops/prepare_gen7_alpha.py` as they were when it was prepared, and refuses to continue if any of
them has changed. Keep a collector's checkout where it was when it prepared. Publication is as for any cohort (one
publication checkout per collector, a new feed branch, frozen runs not updated in place); this
package does not do it.

## What this package does not do

- **Phase 2's self-play pairs.** `7f-32~7f-32` and `7s-32~7s-32` need a runtime with the
  self-play regime. The collectors' branches have it; this branch, like `main`, validates common
  and native only. The files that carry Gen 7 are `bridge_harness/gen7.py`, `gen7_net.py`,
  `gen7_tree.py`, the v4 release and the `gen7` branch of the runtime's player factory; they have
  to be carried onto the self-play runtime as a new source identity. Not done or tested.
- **Audits off for the Gen 5 and Gen 1 anchors.** Needs a per-pair audit switch. Not written.
- **A stop at 2,000 boards a pair.** See step 7.
- **Fork tables with the tree off.** Every table a standard bot plays, forks included, runs the
  tree at tricks 3 to 6.
- **BEN.** No BEN server was available where the package was built, so neither BEN pair was run.

## Evidence, and what kind

Net and bench details are in [the prototype write-up](gen7_prototype_2026-11-11.md) on
`transfer/gen7-prototype-20261111` (`4a84478` and later); the figures below are the ones the
go-ahead rests on. "+-" is one standard error.

| Claim | Evidence | Kind |
| --- | --- | --- |
| Policy v4 is the best net so far | Gives up 0.0333 tricks a decision against Gen 6's card on 406 held-out deals (60,010 decisions), 11.1% less than v3.1, 95% interval [5.1%, 16.5%]. 17,207 training deals | Prediction of Gen 6's card |
| Gen 7 beats Gen 6 | +0.36 +- 0.16 IMPs a board over 414 boards, with net v3.1 and the uniform tree at trust 0.5. Not the candidate's settings | Played |
| The tree at trust 0.2 to 0.3 does not lose | Bench, two sets of boards no net had seen (7,276 fork pairs): +0.02 +- 0.03 tricks a side at margin 0.25, trust 0.25. The match's own forks rescored at trust 0.25: +0.03 +- 0.03 tricks a fork (423 forks). Trust 0.5 and above loses on the bench | Played forks |
| The tree has not been shown to gain | The same figures. On the newer bench set alone, no tree is the better choice | Played forks |
| The stake rule at `path` 0.5 beats the uniform tree | +0.011 +- 0.005 tricks a pair and +0.05 +- 0.02 IMPs a pair on the same 2,905 pairs (one bench set, net v4), at 40% of the solves. At equal solves (`path` 0.1) the two are level, and a fourth trick did not help. Every tree on that set loses to the plain search when it replaces it, so what `path` 0.5 buys there is less search, not better search | Played forks |
| Trust 0.3 rather than 0.25 | Not separated. Bench, net v4, 2,905 pairs, the standard tree under the bot's rule: +0.05 +- 0.17 IMPs a side a table at trust 0.25, -0.24 +- 0.25 at 0.31, -0.76 +- 0.44 at 0.5. The 414-board match's forks rescored: +0.034 +- 0.027 tricks a fork at 0.31, +0.028 +- 0.029 at 0.25. Trust 0.3 has not been played in whole boards | Played forks |
| Policy v4 and the standard tree in whole boards, at trust 0.25 | The smoke match below (72 boards), and a box test on `azure1` run by another session from this branch at `1042db5`: 308 boards of `7s-32~6-32`, no failures, +0.38 +- 0.16 IMPs a board (51 won, 28 lost, 229 flat), 959 boards an hour on 8 vCPUs, 14.3 tables a board; tree audit forks -0.15 +- 0.18 IMPs a fork (325). Figures as reported on `box/azure1/status`, not rerun here | Played |

Benched after the candidate was cut and before the go-ahead (prototype write-up, "Sharp replies,
depth, and all 32 layouts"; 2,270 fork pairs on boards no net had seen): replies taken from the
net's gap head instead of averaged, at two, three and four tricks, and the tree on all 32 layouts
instead of 8. None beat the candidate's tree, the correction's share that shows up in results
stayed at 0.13 to 0.23, and no tree beat the plain search. Nothing in the bot changed for it.

Two unseen bench sets disagreed about the tree by 2.7 standard errors with the same net and code.
No leak was found (23,101 distinct deals by their hands, none shared between sets); the pooled
figures above are the ones to use.

**Smoke match of the candidate standard bot at trust 0.25** (`7s-32`'s settings of 11 November
under the alpha id `7a-32`, against `6-32`, on the first 72 deals and the seeds of the 414-board match; two cores, 16 minutes):

- 72 boards, no failures. +0.50 +- 0.32 IMPs a board (12 won, 5 lost, 55 flat). The same 72
  boards in the v3.1 match were +0.64 +- 0.45; board by board the difference is -0.14 +- 0.34.
  This is a check that it runs, not a measure of strength.
- 9,001 searched decisions of the bot passed `check_decision`; none failed. 1,887 fell in the
  tree's tricks, the tree was consulted at 881 and moved the card at 52. No decision went over
  budget.
- Tree decisions: 88 solves on average (95th percentile 207, most 413) and 0.16 s (95th 0.48,
  most 1.34), against roughly 1 s for the uniform tree in the 414-board match. So `path_solves`
  3,000 and `max_solves` 12,000 never came near binding; they can be cut by a factor of five.
- The stake: 4.1 IMPs a trick on average, median 3.0. Solves follow it (correlation 0.86; 54
  solves below the median stake, 118 above). A fifth of the tree's decisions end with no
  correction at all.
- 64 tree audit forks: 0.00 +- 0.25 IMPs a fork (7 better, 4 worse).

## Cost

Cpu-seconds from the decisions' own records, per board with the feeds' fork mix, on a core that
plays a Gen 6 root table in 9.1 cpu-s. Measured in the 414-board match (uniform tree, no
spot-card mode), not with the candidate's tree:

| Board | Cpu-s | Against Gen 6 self-play |
| --- | --- | --- |
| Gen 6 self-play | 18 | 1.0 |
| Gen 7 fast self-play | 29 | 1.6 |
| Gen 7 standard self-play, the 414-board match's tree | 52 | 2.9 |
| Gen 7 standard self-play, the candidate's tree | about 32 | 1.7 |
| Standard v Gen 6 (two tables), the candidate's tree | about 50 | 2.7 |

The play weights cost more than their share at root tables suggests, because fork tables replay
the late tricks: about 430 decisions a board at tricks 7 to 13, at 27 to 61 ms against Gen 6's 7
to 12. The candidate's tree is much cheaper than the one first measured: in the smoke match a
root table cost a standard side 4.82 cpu-s against Gen 6's 3.80, of which the tree is 0.48 (it
was 2.57), and a decision at tricks 3 to 6 took 111 ms at root tables and 77 ms after a fork,
against Gen 6's 51 and 36. The two "candidate's tree" rows apply those per-decision costs to the
feeds' fork mix; they are estimates, not measured boards.

## Tested, and not

Tested here, on two cores:

- 54 tests in the three Gen 7 test files pass, among them: with `path` 0 the tree is unchanged;
  with a vanishing `path` the stake rule equals the uniform tree exactly, and with a huge one the
  plain search; a stake-rule stage plays whole tables and its records pass the preflight's
  `check_decision`; the three phase 1 plans load ready with the settings Max gave, their two
  halves are the five pairs with none shared, and phase 2 loads closed; cohorts prepared with
  `--shard` take disjoint deals that together are every unplayed deal.
- The uniform tree is untouched in the bot: with this branch's code the plan of the 414-board
  match replays its first 15 boards exactly (295 tables, 15,340 cards, 846 tree decisions, every
  card, result, tree value and solve count).
- All three phase 1 plans build their cohorts from the capsule named in the launch steps. The
  non-BEN plan as shards 0/4 and 1/4 took 5,627 deals each, none shared, each every fourth of the
  22,508.
- Preflight of the non-BEN plan at trust 0.3 (shard 0/4): one board of each of its three pairs,
  603 decisions of the standard bot checked and none failed, the tree consulted at 57 of the 101
  in its tricks and moving the card at 8, nothing over budget.

Not tested:

- Any self-play pair or BEN pair. The BEN-only plan and the five-pair plan were prepared but
  not played.
- Trust 0.3 in a match: the smoke match and the box test ran at 0.25. The preflight above is the
  only play at 0.3.
- More than one board of the Gen 5 and Gen 1 pairs.
- The deal split on real machines, and publication of a Gen 7 cohort.
- Gen 7 fast (`7f-32`) in whole boards by itself. The 414-board match had the tree on.
- More than the smoke match's boards with v4, the stake rule or spot-card mode in the bot.
- Anything on the collectors' machines.
