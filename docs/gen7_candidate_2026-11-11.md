# Gen 7 is coming: candidate notice for the collectors (11 November 2026)

**Status: candidate. Not authorized. Do not drain, prepare or cut over on the strength of this
page.** For the team controlling the workers. Branch `feature/gen7-candidate-20261111`, cut from
`feature/gen7-alpha-20261111` (`7690c3c`), which is cut from `main` at `b0909bb`.

Max's instruction (11 Nov, 23:29 UTC): tell the workers that Gen 7 is coming and give them the
match mix and a candidate build package, subject to final parameters and to his acceptance of
Gen 7 (mostly policy v4 and the tree budgets).

The go-ahead, if it comes, will be a later commit that empties `pending` and sets
`launch_enabled` in the plan files. Until then `ops/prepare_gen7_alpha.py` refuses them. Nothing
here changes Gen 6 or a running collector.

## What is coming

Two bots. Each is Gen 6 fast (`6-32`: same bidder, lead net, hand-fit scorer, layouts, 32
samples) with `engine: gen7` and policy net v4. The settings are spelled out in the plan files.

| Id | Label | What it adds to Gen 6 fast |
| --- | --- | --- |
| `7f-32` | Gen 7 fast (32) | Layouts weighted by the play so far from trick 7 (`play_weight` 0.5); exact ties broken by the net. No tree |
| `7s-32` | Gen 7 standard (32) | The same, plus the tree search at tricks 3 to 6 |

The standard bot's tree, as it stands tonight: cards within 0.25 tricks of the search's best
(`root_margin`), at most 3; value = the search's estimate + 0.25 x the tree's correction
(`trust`); the stake rule with `path` 0.5 IMPs, limits of 3 tricks and 3 cards a node, 8 layouts,
spot-card mode (`plain` 1); budgets `path_solves` 3,000 a candidate and `max_solves` 12,000 a
decision. [The alpha guide](gen7_alpha_2026-11-11.md) explains every setting, the stake rule
included. These are the parameters most likely to change before the go-ahead.

## The match mix

From `configs/gen7-candidate-mix.json`; the two phases are separate plan files because a plan has
one set of pair weights.

**Phase 1, cross-matched, for feedback before volume**
(`configs/round7-candidate-phase1.json`). Equal weights, until every pair has 2,000 completed
boards (10,000 in all):

| Pair | Purpose |
| --- | --- |
| `7s-32~6-32` | The generation gate: standard against Gen 6 fast |
| `7s-32~ben64`, `7s-32~ben` | Anchors: BEN (64) and BEN (16) |
| `7s-32~5RZ32`, `7s-32~1` | Anchors: Gen 5 (32) and Gen 1 |

**Phase 2, volume** (`configs/round7-candidate-phase2.json`). Shares of boards, as weights in
twentieths:

| Pair | Share | Weight |
| --- | --- | --- |
| `7f-32~7f-32` | 30% | 6 |
| `7s-32~7s-32` | 30% | 6 |
| `7s-32~6-32` | 20% | 4 |
| `7s-32~ben64`, `7s-32~ben`, `7s-32~5RZ32`, `7s-32~1` | 5% each | 1 each |

A self-play board is one table. A two-bot board is two tables on one deal, so in tables and in
compute the two-bot pairs weigh about double their share of boards. Self-play supplies training
data and has no IMP comparison, as for Gen 6.

**Audits.** Self-play and `7s-32~6-32` keep the cohort's tie audits and gap forks, and the
standard bot's tree audits (`tree_audit` true: where the tree changed the card, the fork plays
the card without the tree). Max wants audits off in every anchor pair. BEN boards already carry
none (`ben_audit`). For `5RZ32` and `1` there is no per-pair switch in this runtime; see "What
this package does not do".

## What you can do now

None of this touches a live collector.

1. Fetch the branch. `python models/cardplay/gen7-policy-v4-2026-11-11/restore.py` rebuilds the
   net (sha256 `d6b011937ee9ec534ef957061634d9624c5aad56f4c0827ca6c9207bec65dd13`).
2. Run the Gen 7 tests: `python -m pytest tests/test_gen7.py tests/test_gen7_alpha.py
   tests/test_gen7_launch.py` (53 tests here; they need the native DDS library and TensorFlow for
   the lead net).
3. Rehearse on a drained copy of a source run: copy a plan file, set `launch_enabled` true and
   empty `pending` in the copy, `python ops/prepare_gen7_alpha.py --source DRAINED --run SCRATCH
   --plan COPY`, run a few boards with `ops/gen5_runtime.py --run SCRATCH`, and check them with
   `ops/smoke_gen7.py`. A rehearsal run is not a cohort: do not publish its episodes to a feed.
4. Tell Max what the mix costs on your machines: boards an hour by pair, and whether BEN (64) and
   BEN (16) can carry 5% each.

## What this package does not do

- **Self-play pairs.** `7f-32~7f-32` and `7s-32~7s-32` need a runtime with the self-play regime.
  The collectors' branches have it; this branch, like `main`, validates common and native only.
  The files that carry Gen 7 are `bridge_harness/gen7.py`, `gen7_net.py`, `gen7_tree.py`, the v4
  release and the `gen7` branch of the runtime's player factory; they have to be carried onto the
  self-play runtime as a new source identity. That has not been done or tested.
- **Audits off for the Gen 5 and Gen 1 anchors.** Needs a per-pair audit switch. Not written.
- **A stop at 2,000 boards a pair.** A plan has no per-pair target. Phase 1 has to be watched
  (`by_pair` in `state.json`) and cut over to phase 2 with a new cohort.
- **Fork tables with the tree off.** Every table a standard bot plays, forks included, runs the
  tree at tricks 3 to 6.

## Evidence, and what kind

Net and bench details are in [the prototype write-up](gen7_prototype_2026-11-11.md) on
`transfer/gen7-prototype-20261111` (`5f9c41b` and later); the figures below are the ones the
candidate rests on. "+-" is one standard error.

| Claim | Evidence | Kind |
| --- | --- | --- |
| Policy v4 is the best net so far | Gives up 0.0333 tricks a decision against Gen 6's card on 406 held-out deals (60,010 decisions), 11.1% less than v3.1, 95% interval [5.1%, 16.5%]. 17,207 training deals | Prediction of Gen 6's card |
| Gen 7 beats Gen 6 | +0.36 +- 0.16 IMPs a board over 414 boards, with net v3.1 and the uniform tree at trust 0.5. Not the candidate's settings | Played |
| The tree at trust 0.2 to 0.3 does not lose | Bench, two sets of boards no net had seen (7,276 fork pairs): +0.02 +- 0.03 tricks a side at margin 0.25, trust 0.25. The match's own forks rescored at trust 0.25: +0.03 +- 0.03 tricks a fork (423 forks). Trust 0.5 and above loses on the bench | Played forks |
| The tree has not been shown to gain | The same figures. On the newer bench set alone, no tree is the better choice | Played forks |
| The stake rule at `path` 0.5 beats the uniform tree | +0.011 +- 0.005 tricks a pair and +0.05 +- 0.02 IMPs a pair on the same 2,905 pairs (one bench set, net v4), at 40% of the solves. At equal solves (`path` 0.1) the two are level, and a fourth trick did not help. Every tree on that set loses to the plain search when it replaces it, so what `path` 0.5 buys there is less search, not better search | Played forks |
| Policy v4 in whole boards | The smoke match below only | Played |

Open as this is written: whether the tree's replies should be sharper. The tree averages over the
net's likeliest replies, so width and depth add opponent mistakes that Gen 6 will not make; a
bench of sharp replies at two, three and four tricks is the next run. Its result could change
`path`, `tricks` and the reply settings of `7s-32`.

Two unseen bench sets disagreed about the tree by 2.7 standard errors with the same net and code.
No leak was found (23,101 distinct deals by their hands, none shared between sets); the pooled
figures above are the ones to use.

**Smoke match of the candidate standard bot** (`7s-32`'s settings under the alpha id `7a-32`,
against `6-32`, on the first 72 deals and the seeds of the 414-board match; two cores, 16 minutes):

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

- 53 tests in the three Gen 7 test files pass, among them: with `path` 0 the tree is unchanged;
  with a vanishing `path` the stake rule equals the uniform tree exactly, and with a huge one the
  plain search; a stake-rule stage plays whole tables and its records pass the preflight's
  `check_decision`; both candidate plans load closed and spell out every setting.
- The uniform tree is untouched in the bot: with this branch's code the plan of the 414-board
  match replays its first 15 boards exactly (295 tables, 15,340 cards, 846 tree decisions, every
  card, result, tree value and solve count).
- Both plan files build their bots from a drained Gen 6 source run and pass the mix check.

Not tested:

- Any self-play pair, any BEN pair, the Gen 5 and Gen 1 pairs, or either plan prepared and run.
- Gen 7 fast (`7f-32`) in whole boards by itself. The 414-board match had the tree on.
- More than the smoke match's boards with v4, the stake rule or spot-card mode in the bot.
- Anything on the collectors' machines.
