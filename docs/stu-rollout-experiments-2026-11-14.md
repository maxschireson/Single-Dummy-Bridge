# Stu rollout experiments: protocol and execution

14 November 2026. Owner: codex-rollout. Max authorized local smoke tests and
reassigning one existing Azure collector to these experiments. Azure6 is reserved;
Azure2 is also authorized for independent reader/guarantee screens. Other boxes remain with their current owners.
This is the runnable appendix to the integrated recommendations in
[PR #35](https://github.com/maxschireson/Single-Dummy-Bridge/pull/35), not a separate
competing training plan. Harvesting work H01–H06 stays in
[PR #37](https://github.com/maxschireson/Single-Dummy-Bridge/pull/37).

## Review correction, 14 November 21:40 UTC

PRs [#41](https://github.com/maxschireson/Single-Dummy-Bridge/pull/41) and
[#43](https://github.com/maxschireson/Single-Dummy-Bridge/pull/43) found genuine
prototype errors. Azure6's `7c79acf` batch stopped at 21:23:14 UTC. Its recursive
and selective scores are **not valid evidence** and must not be extended or pooled
with corrected runs. Original results/episodes remain untouched; REVIEW_PAUSE.json
records the stop and inventory. Azure2's independent reader/guarantee screens may
continue as development diagnostics under B's disclosed cost/cache limitations.

The v2 correction uses fresh `rx2-*` identities and fresh output directories:

- Group by child Observation, apply every cached action before eligibility/budget,
  remove hidden-layout path gating, and continue checking cache hits at the cap.
  Rejected confident positions cannot block later uncertain positions. Count
  replacements of the actual sampled action, including cache applications; keep
  the argmax comparison as a separate counter.
- A fresh-only driver refuses **any nonempty output directory** before writing.
  It never invokes the inherited resume/retry loop. Each first attempt has a durable
  running/complete/failed ledger; no automatic retries; stop subsequent chunks on
  failure while retaining completed work from the current chunk.
- Native claim solvers belong to individual actors, reset between actual rooms;
  each child decision starts cold. Child and parent solvers never share caches.
  Native wall-clock timeouts can still vary with OS scheduling; record them and
  measure sensitivity before attributing small score changes.
- Record per-actor inclusive action wall time, worker CPU, native solver CPU,
  calls/cache hits/timeouts, actual policy precision, and recursive work. Child
  costs are already inside the parent action totals. Board attempts also include
  reaped external-process CPU and failed-attempt time. Native live CPU snapshots
  have Linux clock-tick resolution; initialization and final cleanup are included
  in whole-attempt cost, with actor initialization reported separately.
- Validate engine digest before model loading; pin imported source, implementation,
  model, DDS and native solver hashes plus precision environment in each manifest.

Local acceptance: **25 tests pass** (A's three unchanged assertions; B's nine
boundary checks with expected-failure markers removed and the first-rejection
witness converted to a desired-behavior regression; nine corrected-driver tests;
four original smokes). B's original inherited-driver evidence remains in #43.
Real R4c/BF16/native-SURE acceptance is a separate required gate before v2 smoke.
The v2 batch launcher is **16-board correctness smokes only**, at indices 2000–2015,
seed 2026111401. It does not automatically launch 128-board strength screens.

A's random-versus-S1 selector, matched windows/candidate quotas and calibrated
cost controls are the next experiment; the simple earliest/gap gates below remain
mechanism diagnostics, not the final allocator. A owns a pure selector follow-up;
B independently reviews this corrected implementation. Use per-actor measured cost,
not nominal 4×8 work or whole-match Python CPU, to calibrate later comparisons.
The original six-hour box budgets are not reset by this correction.

## Why study the search mechanism

The loop's published results show stronger nets have not transferred their full
net-only improvement into the search bot. The R3/R0 comparisons reported +0.40 ±
0.07 IMP/board for net-only play (4,000 boards), versus +0.16 ± 0.09 with both
table and rollout nets changed (2,000), and −0.13 ± 0.09 with only the rollout
net changed (2,000). These are historical measurements with different sample
counts, not independent reruns or an exact percentage of gain retained.
Source: [loop report at 5addd826](https://github.com/maxschireson/Single-Dummy-Bridge/blob/5addd826af8b10d7343df51ada528a7327d059b6/training/rollout-loop-20261113/README.md).

The table bot searches again every turn; the simulated continuation mostly plays
the net. Increasing the number of layouts reduces sampling noise but does not
remove that policy mismatch. A smaller, better continuation search could help.
It could also cost more than it gains or amplify posterior/model errors. Test it.

Two cheaper mechanisms warrant separate checks. In blind mode the history reader
inherits the table net's own identity for hidden players' past cards, whereas
rollout seats explicitly route identities by side. Also, an explicit opponent
list without `*` makes `aware(False)` false once blind mode removes the name.
These are observed code behaviors, not established causes of lost IMPs.

## Sequence and decision gates

| ID | Experiment | Control and decision |
| --- | --- | --- |
| R00 | Observation boundary, baseline parity, legality, bounded recursion and stable identity | Local fixtures, then small real-model Azure runs before larger matches |
| R01a | Role-correct history-reader identities | R4c 128 layouts, otherwise identical; plain and pooled history paths both covered |
| R01b | Generic opponent contract-preservation model | Only change `claims.opponents` to `['*']`; do not combine with R01a initially |
| R02 | Flat 128; flat 32; 32 outer layouts plus 8-layout child search | One child depth, two child candidates, at most four new child searches per root, own partnership only, within the next eight plies |
| R03 | Uniform versus uncertainty-selected child searches | Same maximum budget; report actual spend. Initial selector uses top-two policy log-probability gap ≤ 1; this is only a prototype uncertainty rule |
| R04 | Improve allocation by repeatable action disagreement, paired search uncertainty and contract leverage | Calibrate on development families; include randomly selected opportunities. Measure value of another search, not uncertainty alone |
| R05 | Training value of frontier-targeted reanalysis | Coordinate H03–H05: root-only, broad extra positions, frontier plus one/two tricks before it; equal training and labeling compute, held-out full-bot evaluation |
| R06 | Decision objective, conservative net/search blending and value cutoff | After the first screen; isolate score/IMP objective from guard/racing threshold units. Learned cutoff requires independently validated labels |

R02 is a bounded information-set replan, not a complete tree implementation.
For each child, reconstruct its own visible hand, public dummy, auction and play;
draw **fresh posterior layouts from that observation**. Do not optimize against
the enclosing sampled complete deal. Resume the outer simulation on its original
deal after choosing the child card. Cache identical child observations with a
seed derived only from that observation. Child continuations are flat and run to
the end; no DD leaf is introduced by this experiment. Opponent replanning,
multi-depth trees and shared-tree methods are later arms, after cost is understood.

The present implementation serializes a few child searches within the batch. It
tests whether the mechanism can matter; its timing is not a lower bound on a
batched tree implementation. The uniform arm spends at the first eligible own
decision in the window; the selective arm additionally requires uncertainty.
Neither is a learned frontier detector. Report node usage and every failed board.

## Equal time, statistical discipline and attribution

1. Pin the source, model SHA256, full actor specs and experiment source digest.
   Use the same deals, bidder, opponents, numerical mode and capture settings.
2. First run 16 paired duplicate boards per arm as correctness/cost smoke tests.
   Then 128 per arm on the same new development seeds for a diagnostic screen.
   These are too small to certify modest strength gains.
3. Choose the next root/child budget by measured CPU and wall time, **not** by the
   best noisy score. Match cost to flat 128 within about 10%; retain flat 32 so
   breadth/depth effects can be separated. Record latency tails and RSS too.
4. Confirm shortlisted choices on fresh families (initially 1,000 paired boards;
   extend only with a declared budget and precision target). Report board-clustered
   SE/intervals, paired score differences and cost. Boards, not decision rows or
   imagined forks, are independent units. Account for screening many alternatives.
5. Attribute decisions by role, lead/trick phase, contract class and whether search
   changes the net's card. Use held-out played continuations for action comparisons;
   DD hindsight is diagnostic, not the adoption metric. Protect BEN blind evaluation
   from development selection. No experimental result enters aggregate arena scores.

## Learning frontier: use it for both purposes, measure them separately

For playing strength, spend additional search where it has a reasonable chance
of changing the action and the potential score swing justifies the cost. A close
race with no consequence can be a poor use of time; a confident model disagreement
can be valuable. Gate on information available to the player, never true hidden cards.

For learning, favor positions where a stronger search produces a reproducible
action advantage that the current net misses, occurs often enough to matter, and
can be learned. Partition by role/phase/contract and locate the transition from
reliable to unreliable policy choices empirically. Include decisions at that
transition and one or two tricks before it, where the future problem is created.
Keep broad/random coverage so the frontier can move and blind spots can be found.
Avoid concentrating exclusively on irreducibly ambiguous or pathological positions.

The training allocation should ultimately track **held-out full-bot IMP gain per
labeling/training hour**. The playing allocation tracks **IMP gain at fixed move
time**. Compare both and their combination; extra search targets are not automatically
better training data. Existing `x8.forks` are one-layout continuation pairs, not
independent posterior-search labels. H02 handles extraction and provenance; selective
reanalysis can upgrade a subset without multiplying collection first.

All experimental evaluation families and descendants are excluded from training.
Use new development seed 2026111401 for the first batch; seed 131 and the squeeze
suite remain excluded. A later training experiment needs a separately declared
training seed/population and a fresh confirmation set. Do not infer independence
from a different fork, room, role, sample or auction of the same deal family.

## Running and preserving the experiment

New source lives on a main-based branch. The driver imports an immutable external
Stu checkout through `STU_RUNTIME`; it does not edit that checkout. This avoids
merging the research branch wholesale into main. Baseline runtime is the live
azure6 collector source `30e30af88ea196b8189ff39491c83cf531797868`; local tests use
`5addd826af8b10d7343df51ada528a7327d059b6`. Check core file hashes before accepting
Azure parity. R4c net SHA256 is
`e4b689c87db2f56b98221a491757dbf348ddaea066e016f06a9331fc671197f2`.

```bash
STU_RUNTIME=/path/to/pinned/stu python scripts/stu_rollout_experiments/test_smoke.py -v
python scripts/stu_rollout_experiments/make_config.py \
  --bots /path/to/pinned/stu/configs/loop-bots.json --out /new/run/bots.json
STU_RUNTIME=/path/to/pinned/stu python scripts/stu_rollout_experiments/match.py \
  --source /path/to/capsule/recovery --bots /new/run/bots.json \
  --pair rx2-recursive32~rx2-control --seed 2026111401 --first 2000 \
  --deals 16 --workers 4 --recycle 4 --common-only --episodes --out /new/run/recursive-smoke
```

The first box allocation is capped at six hours. Drain `loop-collect` at its normal
worker-recycle boundary; save the original command and completed row/episode
counts. Keep `loop-publish` and `loop-rows` running. Use isolated experiment outputs
and publish summaries/records on a dedicated transfer branch. Stop on invariant
failures. No model promotion or change to production actors is authorized by an
experimental improvement. Loop retains deployment/integration decisions.

Local verification: four new tests pass, including exact Observation equality and
hidden-hand permutation invariance, reader routing/restoration, bounded child calls,
and a real fixture child search. Existing X8 suite: 34 tests, 7 native-claim-solver
skips, no failures after building DDS. These checks establish implementation
properties, not playing strength. Azure results and allocation state are recorded
in the dated report and coordination board as they become available.
