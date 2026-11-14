# Stu helper A: search-allocation review and test contract

14 November 2026. Owner: codex-rollout-helper-a. Status: independent review for
codex-rollout; proposed acceptance conditions, not a deployment instruction.
Max asked this helper to choose A or B; this chat chose A, search allocation.
B covers independent correctness review. A includes the allocation/learning-frontier
selector proposal in [the main helper report](../reports/stu-rollout-helper-allocation-2026-11-14.md).
H02/H03–H05 implementation/design ownership remains with
codex-stu-harvest and execution with the owners recorded in the coordination board.

This appendix supports [R02–R04 in PR #38](https://github.com/maxschireson/Single-Dummy-Bridge/pull/38),
under the integrated [P/H/R plan, #35](https://github.com/maxschireson/Single-Dummy-Bridge/pull/35).
It does not replace [the harvesting plan, #37](https://github.com/maxschireson/Single-Dummy-Bridge/pull/37).
No Azure allocation, runtime, model, frozen record or leader-owned source was changed.

## Recommendation

Keep the bounded one-depth prototype, fix the three reproduced scheduling/counting
issues before interpreting R03, and separate three questions:

1. Does adding child search improve decisions at a fixed outer-layout budget?
2. At the same measured cost, is that better than spending the resource on breadth?
3. At the same cost and child solver, does selection improve on a random opportunity
   schedule, beyond the benefit of simply doing fewer child searches?

The current flat-32 / recursive-32 / selective-32 versus flat-128 screen is useful
for feasibility. It does not by itself isolate these three effects. In particular,
the arm named `uniform` is earliest-eligible scheduling, not a uniform sample of
opportunities across the eight-ply window.

## Evidence and scope

Inspected pins:

| Material | Revision |
| --- | --- |
| Experiment implementation | [`7c79acfaa138a29d140dfef3d50f9a52216a24aa`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/7c79acfaa138a29d140dfef3d50f9a52216a24aa) |
| Local external Stu runtime | [`5addd826af8b10d7343df51ada528a7327d059b6`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/5addd826af8b10d7343df51ada528a7327d059b6) |
| Azure baseline named by leader | `30e30af88ea196b8189ff39491c83cf531797868`; not independently executed by this helper |
| R4c model identity in leader's protocol | SHA256 `e4b689c87db2f56b98221a491757dbf348ddaea066e016f06a9331fc671197f2`; no real-model strength evaluation here |

The leader's four smoke tests were rerun locally: **4 passed**. Three additional
synthetic regression assertions below **all fail on the inspected experiment**.
Isolated temporary positive-control edits make all three pass; those edits are
not a proposed production implementation. The fixtures mock seat policy and row
observation construction to isolate allocation bookkeeping. They do not test
posterior quality, neural inference, playing strength or incidence in real games.

Reproducer: [`scripts/review_stu_search_allocation.py`](../scripts/review_stu_search_allocation.py).
It intentionally exits nonzero on the reviewed revision and is outside automatic
test discovery. It can become a regression gate after the leader's changes.

```bash
STU_RUNTIME=/path/to/pinned/stu \
STU_EXPERIMENT_SOURCE=/path/to/experiment-checkout \
python scripts/review_stu_search_allocation.py
```

## Findings to resolve before ranking R03

All three are in [ReplanningSeats.cards at the reviewed revision](https://github.com/maxschireson/Single-Dummy-Bridge/blob/7c79acfaa138a29d140dfef3d50f9a52216a24aa/scripts/stu_rollout_experiments/engine.py).

| Finding | Reproduction and consequence | Acceptance requirement |
| --- | --- | --- |
| A1: path consumed before uncertainty acceptance | First own decision has log-probability gap 5; a later own decision on the same path has gap 0, within the window and with budget available. Calls remain 0, expected 1. R03 currently gates only the first opportunity. | Distinguish considered, rejected, expanded and cache-served paths. Rejecting a confident node must leave later nodes eligible. Define explicitly whether a serviced cache hit consumes that path's one-expansion allowance. |
| A2: capacity check interrupts cache reuse | At the new-call cap, an uncached observation sorts before a cached one. The cached row keeps its base card, expected cached child card. | Apply eligible cached actions regardless of remaining new-call capacity and unrelated uncached rows. Exhaustion must prevent new work, not prevent cache lookup. |
| A3: action-change count uses wrong reference | Base rollout samples card 3; policy argmax is card 2; child returns card 3. `changed` becomes 1, expected 0. The inspected R4c actor uses `seat='draw'`. | Compare replacements with pre-override `out[i]`. Record argmax disagreement separately if wanted; count replacements on cache-served rows too. |

Do not fix A1 merely by moving `seen_paths.add` past the confidence test without
defining what happens to opportunities rejected by capacity. Bookkeeping should
record the actual scheduling policy. No effect size is claimed for these bugs.

## Additional safeguards and measurement gaps

**Candidate exposure.** The new-call budget is shared across all outer
candidate/layout paths, with early-ply priority and hash ordering within a ply.
Four child calls can all go to a subset of root candidates. That is not inherently
invalid, but it can rank candidates under differently improved continuation
policies. Report expansions and affected posterior mass per root candidate.
Include a candidate-balanced allocation control before attributing gains to
better child selection. Log number of candidates and eligibility; opening leads
and low-choice late decisions need separate summaries.

**Dilution.** With 32 layouts and four root candidates there are 128 simulated
paths before deduplication. Four new child searches can directly service only four
distinct child observations, with possible extra cache reuse. Measure the weighted
fraction of paths actually affected. A null result with negligible exposure is
evidence about this budget, not a rejection of deeper continuation search.

**Runtime versus implementation.** Keep the one-depth, own-partnership,
fresh-posterior boundary. Test input/seed/card invariance when hidden allocations
or row order change while the child's visible observation stays the same. Also
test budget/window boundaries, duplicate views, cap zero, forced moves, and
exception restoration of the global Seats factory. Allocation may legitimately
change with the declared scheduler, but hidden data must not enter child values
or priority features. Hash priority is a reproducible tie-break, not a learned
value-of-search measure. Document its observation-serialization version.

**Telemetry.** `recursive` details survive in episodes, but the inspected
`x8_match.summarise_actions` does not aggregate them. Parent `x8.net_rows` counts
outer seat inference, not the nested player's work. Keep those counts separate
and add child calls/cache hits/replacements/net rows, child posterior time,
claim/solver time, wall time and peak RSS to the allocation report. A child
`x8.net_rows` count is itself only rollout inference, not every model operation.
Use actual decision time as the primary inclusive cost measurement.

## Minimal experiment matrix

Run A1–A3 and identity/observation gates first. Then use the leader's 16-board
smoke and 128-board development screen; these are cost and mechanism screens.
Do not expand the grid into every possible breadth/depth/budget combination.

| Arm | Fixed settings | Question |
| --- | --- | --- |
| F32 | 32 outer layouts, no children | Cost/strength of the narrower root |
| E32 | 32 outer layouts, earliest eligible child policy | Effect of the present prototype after correctness fixes |
| Q32 | 32 outer layouts, budgeted random opportunity schedule | Control for opportunity selection across phase and candidate |
| S32 | Same child solver as Q32, uncertainty/value-selected schedule | Benefit of selective allocation |
| F-time | Flat breadth calibrated to the measured cost of the selected child arm | Breadth versus depth at equal cost |
| F128 | Frozen baseline including its racing settings | Anchor and practical candidate-to-baseline comparison |

Keep child solver at eight fresh layouts and two candidate representatives for
the first screen. Keep reader identities, guarantees, root candidate rules,
numerical mode, bidder, claims, capture and opponent constant. R01 changes stay
separate until adopted as a common baseline. Log racing rounds: 128 layouts is a
maximum, not necessarily actual spend. Disabling racing only for one comparator
would change more than nominal breadth.

Q32 must have a written sampling rule. For example, assign eligible own decisions
in the window predeclared random admission probabilities by ply, with a hard
per-root cap and candidate-stratified capacity. Choose the probabilities using
cost-only development data to match S32's actual spend. Log every admission
probability and rejection reason. Do not call this exact uniform sampling of a
future opportunity set, which is unknown online. A fixed baseline-trace replay
can compare exact uniform samples as an offline diagnostic; count its trace and
replay costs and confirm the winner with live, history-changing continuations.

Compare E32 versus F32 to identify the effect of added child work; compare S32
versus Q32 directly to identify allocation value. Use the same family list and
both seat assignments. Differences between each arm's results against a common
opponent are useful paired diagnostics, but are not equivalent to playing the
two arms against each other. Finalists require a direct paired match as well as
the external blind gate retained by loop.

## Equal cost means candidate cost

The inspected `summary.cpu_per_board` includes both actors, bidding and board
overhead. If equal-cost baseline players each cost C, a candidate costing 1.2C
still makes the whole match only 10% slower (2.2C versus 2C). A 10% total-match
band therefore does not establish a 10% per-bot band.

Measure candidate and opponent separately from action `seconds`, including
opening leads and all child work. Add per-actor CPU accounting where available;
state thread counts and whether CPU totals include native worker threads. Use
isolated or interleaved runs on the same box, same worker occupancy and warmed
models. Report process startup separately, plus cold-first-move and steady-state
latency, median/p95/p99/max decision time, aggregate candidate CPU, throughput and
RSS. Net rows and configured calls are diagnostic costs, not substitutes for time.

Calibrate budgets on development families **without selecting on their IMPs**.
Freeze either a mean candidate-time target within 10% of F128 with a declared
tail constraint, or a fixed per-decision deadline with a documented legal fallback.
These are different experiments. If selective search is cheaper, compare with
a cheaper random arm and a flat arm at that cost; also test reinvesting saved
time in root breadth if the intended product is a fixed-time bot. Unspent budget
is a valid outcome, but not proof that uncertainty targeting is superior.

## R04: learn the value of a computation, not entropy alone

At a development root, record the baseline action and candidate value gaps,
paired uncertainty, posterior effective sample size, role/phase/contract and
available time. Randomize a bounded next computation: another root-layout block,
one child replan, or no extra computation. Candidate proposals and downstream
evaluation must be held constant within this diagnostic.

Measure whether the computation changes the **root** action and whether that
change improves a separately evaluated played continuation. Child disagreement
alone is insufficient; its effect can disappear when averaged over layouts.
Use fresh verification samples for actions selected by noisy search and include
random opportunities even where the policy is confident. One observed deal's
result is noisy evaluation evidence, not an oracle single-dummy value.

Fit or calibrate an allocation score from the player's observable information,
estimating expected root-decision improvement per incremental millisecond. Keep
contract utility consistent within the experiment; do not silently exchange
trick gaps, raw scores and IMPs. Keep score predictions separate from eventual
training priorities. Helper A proposes the selector interface in the linked report;
codex-stu-harvest retains H03–H05 design and loop retains training execution.

## Confirmation and reporting contract

- Freeze source/config/model/capture digests, allocation rule, time calibration,
  exclusions, opponent, primary contrast and sample budget before confirmation.
  The leader's development seed `2026111401`, seed 131 and the reserved squeeze
  suite remain outside training, including every descendant. Use new family-
  disjoint confirmation data checked against actual training provenance, not
  just a different seed label.
- Choose one finalist on development data. Primary confirmation is its paired
  played IMP/board gain over the predeclared flat comparator at matched cost.
  Keep role/phase, random-scheduler comparison and common-opponent attribution
  secondary. If multiple co-primary candidates/contrasts are tested, adjust the
  error rate explicitly; do not certify whichever first crosses a threshold.
- Use one paired outcome per deal family, joining by family and condition.
  Rotations, rooms, auctions, descendants and decision rows are not independent.
  Report family count, mean, SD of paired deltas, SE and interval. Where multiple
  records survive per family, use a defined family aggregation or cluster method.
- Set precision using development variance and the smallest worthwhile gain.
  For illustration, a fixed two-sided 5% test at 80% power needs approximately
  `(1.96 + 0.84)^2 * SD(delta)^2 / gain^2` families under a normal approximation.
  With SD 3 IMPs and gain 0.10, that is about 7,056 families. This is not an
  observed variance estimate or authorization to launch that run. The proposed
  1,000-board start cannot promise to resolve a modest gain.
- Declare the maximum cost and stopping rule. A fixed final analysis is simplest;
  repeated looks require a sequential design. If the budget cannot establish the
  desired precision, report inconclusive. A nonsignificant loss does not establish
  noninferiority, and a lower latency does not establish stronger play.
- Report every planned and completed family, timeout/failure, retry and fallback.
  Do not rank arms after independently dropping hard failed boards. Treat
  implementation failures as a gate; any repaired rerun uses a new immutable
  run and a common complete comparison set. Passed-out deals follow one declared
  inclusion policy across arms.

## Handoff to codex-rollout

1. Fix A1–A3 in the leader's experiment branch and turn the reproducer into a
   passing acceptance check; retain the existing observation tests.
2. Publish per-candidate expansion exposure and inclusive per-bot timing from
   the next small screen. Report random scheduling and earliest scheduling
   distinctly; retain child budget zero as the baseline-parity check.
3. Run the cost-matched Q32/S32 and breadth comparison only after the allocation
   policy and fresh family set are frozen. Coordinate compute within the leader's
   existing allocation; this review claims no box.
4. Give codex-stu-harvest a root/child opportunity ledger with family identity, observable
   features, random admission probability, action change, independently verified
   value and cost. Data extraction/training execution stay with their named owners.

No strength result, production fix, additional box reservation or training
recipe approval is implied by this review.
