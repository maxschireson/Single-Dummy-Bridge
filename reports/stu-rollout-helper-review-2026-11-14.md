# Stu rollout helper B: independent correctness review

14 November 2026. Owner: **codex-rollout-review**, workspace `81238be0d723`.
Assignment: [issue #39, B](https://github.com/maxschireson/Single-Dummy-Bridge/issues/39).
Implementation: [#38](https://github.com/maxschireson/Single-Dummy-Bridge/pull/38).
Allocation/frontier design: [helper A / #41](https://github.com/maxschireson/Single-Dummy-Bridge/pull/41).

## Decision

**No-go for interpreting or extending the pinned recursive/selective screen as an
information-set-consistent search comparison.** Two adversarial tests reproduce
cache/scheduling inconsistencies. Publish a corrected implementation under a new
identity and rerun its correctness smoke before comparing scores. Preserve the old
episodes as development evidence. This is not evidence of a direct hidden-hand
input leak into the child posterior, or of any measured strength loss.

**Conditional go for the flat, reader and guarantee arms as development screens**:
these scheduling defects do not affect them. Do not claim equal total compute
from the present `cpu_per_board`, or infer a modest strength gain from 16/128
boards. Keep all failed attempts, use new output paths when behavior changes, and
verify the real-model/claim-solver checks below. The initial pause recommendation
was posted [immediately on #39](https://github.com/maxschireson/Single-Dummy-Bridge/issues/39#issuecomment-6884132293).

No shared engine, running batch, frozen episode, model, or Azure service was edited.
This is a main-based test/report handoff; integration and box operation remain with
codex-rollout. H02 extraction and training experiments remain with their owners.

## Scope and exact evidence

| Item | Pin / scope |
| --- | --- |
| Reviewed prototype | `7c79acfaa138a29d140dfef3d50f9a52216a24aa` |
| Local Stu runtime | `5addd826af8b10d7343df51ada528a7327d059b6` |
| Azure runtime | `30e30af88ea196b8189ff39491c83cf531797868` |
| Experiment engine SHA256 | `ed6b791debf4a672c7736dc29d0d0a5ad6bc54c50f0062fde545f9102388a3b5` |
| Reported Azure R4c model SHA256 | `e4b689c87db2f56b98221a491757dbf348ddaea066e016f06a9331fc671197f2` |
| Local execution | Synthetic legal bridge positions, random small fixture networks, FP32, native DDS available |
| Not locally executed | R4c production weights, BF16 parity, native SURE claim solver, Azure jobs |

The [Azure provenance file](https://github.com/maxschireson/Single-Dummy-Bridge/blob/transfer/stu-rollout-experiments-azure6-20261114/provenance.json)
was read through the published transfer branch; its observed Git blob SHA is
`589179cfe9c25ba2ab4a427a730e57cac4e13789`. It records BF16 enabled and the runtime/implementation/model pins.
Local SHA256s of `x8_player.py`, `x8_rollout.py`, and `gen7.py` exactly match its
three runtime-source hashes. The forward GitHub comparison from Azure to local
shows six commits affecting training documentation/jobs/bench scripts, not the
reviewed player/match source. These checks support source parity; they do not
establish FP32/BF16 or native-solver behavioral parity.

The inspected reader-smoke manifest has identity
`6c43e5d87776e400f6a74bc983bc73d53f837861dac6317b0c7b21dbc39f4399`,
seed `2026111401`, indices 0–15, and `common_only=true`. It sets neither
`independent_room_seeds` nor `two_self_rooms`. All seed-2026111401 families and
imagined descendants stay excluded from training, as do seed 131 and the squeeze
suite. No dataset was harvested or trained for this review.

## Findings that invalidate the intended comparison

### B01 — A known child action can be dropped at the new-search budget limit

**High; recursive and selective arms.** In pinned `engine.py:69–75`, opportunities
are sorted by the child-observation hash. At `max_calls`, the first uncached entry
causes `break`, so later cached observations do not receive their already-computed
cards. This violates the promised reuse of identical child observations, despite
requiring no extra search.

Reproduction: `test_cached_card_is_independent_of_other_uncached_rows_at_budget_limit`.
Using legal rows and a deterministic legal policy stub, a cached observation
chooses card **49 alone, 15 with an earlier-hash uncached neighbor**. The test
preloads an exhausted budget and cache to isolate the branch; this is an
adversarial unit witness, not a count of occurrences in Azure episodes.

Process cache applications independently of the new-search budget; skip an
unaffordable new search rather than stopping cache processing. Helper A found
this independently first; this review confirms it with separate fixtures.

### B02 — Hidden-layout path eligibility can override observation-consistent reuse

**High; recursive and selective arms.** At `engine.py:55–60`, the full original
layout plus root card keys `seen_paths`, and a seen path is skipped **before** the
observation cache is consulted. Two indistinguishable child observations can
therefore execute different continuation policies depending on which hidden
world/path was previously marked considered. Sorting by an observable hash later
does not repair this earlier eligibility decision.

Reproduction: `test_equal_observations_with_different_hidden_path_marks_use_same_cached_card`.
Two legal rows differ only by a same-suit exchange between the child's hidden
hands; their full `Observation` values and seeds are equal. With one path marked
seen and that observation cached, they choose **19 versus 47**. Same-suit exchange
preserves hand sizes and observed void constraints. The marked state is injected
to test the invariant; a live incidence rate has not been measured.

Consult an observation-keyed policy decision before private path bookkeeping.
Separate **whether a new expansion may be purchased** from **which established
policy applies at this information set**. Merely replacing B01's `break` with
`continue` leaves B02. Audit selection/fallback across equivalent observations as
well as successful child calls. If stochastic fallbacks are retained, require an
observation-consistent policy distribution and document the random coupling;
every independent random draw need not realize the same card.

An isolated temporary positive control moves cache lookup ahead of `seen_paths`
and changes the exhausted-budget `break` to `continue`: both strict witnesses
pass. No positive-control engine was deployed. This establishes that the tests
detect the reported branches, not that those two changes fully solve allocation.

### B03 — Changed-run resume can silently mix identities (conditional blocker)

**High if an output directory is reused with changed settings.** The inherited
`gen8_match.main` overwrites `manifest.json`, then accepts all existing
`results.jsonl` rows and skips their indices without comparing the old manifest.
`test_resume_rejects_different_manifest_before_relabelling_old_rows` demonstrates
an old-spec row retained under a new-spec manifest without an exception.

There is **no evidence the live run has been mixed**. A fresh output path per
behavior/runtime/model/numerical-mode revision avoids this failure. For resumable
experiments, validate an immutable run identity and result-family/index coverage
before any manifest write; refuse mismatches and duplicates. Hash-check the
imported implementation, not only the digest recorded when generating config.

## Biases and confounds to disclose or fix

| ID | Finding and consequence | Required treatment |
| --- | --- | --- |
| B04 | `seen_paths.add` precedes the uncertainty gate. A confident first eligible own decision excludes later uncertain decisions within the window. Reproduced by `test_first_rejected_selective_opportunity_consumes_the_path`. | Current R03 is a gate on the first eligible decision per path, not a moving frontier selector. Separate considered from expanded; coordinate the selector fix with A. |
| B05 | Four calls are shared across root candidates/layouts, allocated by earliest eligible ply and then observation-hash order. Calls may find a claim or only one candidate and perform no rollout. Shared observations get broad reuse; other candidates may get none. `first=32` also means the nominal flat128 races candidates and need not spend 128 on each. | Record new calls, cache applications, candidate/layout probability mass receiving replanning, claim-only/no-roll outcomes and gate/budget rejection by ply. “Uniform” means first eligible, not uniform-random allocation. Use A's randomized budget control and actual-cost comparison. |
| B06 | `gen8_match.play` times the Python worker with `time.process_time()`. External SURE solver processes are excluded. Child/guarantee arms alter solver work. Successful-board CPU also excludes failed attempts and process initialization; a whole-match mean includes both actors. | Do not time-match actors using this number alone. Measure per-actor action wall time, worker **plus solver** CPU, solver calls/hits/timeouts, initialization and retry overhead. Synchronous action wall time includes child and solver waits. Serialized child timings are not a lower bound for a future batched tree. |
| B07 | `recursive.net_rows` counts the child's reported rollout rows only. It omits child posterior/history policy work and claim queries. `x8_match.summarise_actions` ignores the entire recursive note; its `x8.net_rows` remains outer work. | Episodes preserve the recursive note and action times; extract it explicitly. Add inclusive/differential counters per actor and phase. `test_rollout_summary_omits_child_work_retained_on_action` reproduces the omission. Do not add parent roll wall time and child wall time: the former already includes the latter. |
| B08 | `changed` compares child card to argmax, although R4c's continuation seat is `draw`; cache-hit replacements are not counted. | A already reproduced this in #41. Compare against the actual pre-override sampled card, separately count policy-argmax disagreement and cache replacements. |
| B09 | `x8_claims.shared(binary)` shares one Finder/two solver subprocesses across actors and child players within a worker. Claim calls have wall-time allowances and caches; additional child work can warm answers used by the opponent or second room. `Finder.each` is also mutable globally, though cloned current settings agree. | This is a source-level coupling risk, not a measured score effect. Log cold/warm hits, timeouts and answer coverage; compare fresh solver/order controls. Before strength confirmation, use actor-scoped solver state or demonstrate that shared state cannot change returned answers for the evaluated positions. |
| B10 | A failed board is retried once; successful retry leaves final `failures=0`. The stdout still records the attempt, but summary counts alone hide it. Twice-failed boards remain absent and counted. Both cases reproduced. | Preserve an attempt ledger and failed work/time; stop on invariant failures. Batch's completion check catches terminal missing boards, not resolved invariant failures. Compare arms on predeclared family coverage; do not silently select different successful subsets. |
| B11 | Engine hash is embedded in generated specs but not verified on import. Numerical mode lives in external provenance, not the run identity; local verification is FP32 while Azure provenance says BF16. | Keep runtime/driver/config/model/solver hashes, actual `PolicyNet.precision`, library versions and thread settings with each immutable run. Validate source digests before launch/resume. Source parity is verified here; BF16 and native-claim parity remain a coordinator gate. |

The four-by-eight child budget is **not** 32 interchangeable extra outer samples:
children perform their own posterior generation, may examine a 512-layout early
pool, search two candidates, and retain root/leaf claim logic. On cheap or forced
positions they can spend much less. These are reasons to measure executed work,
not reasons to infer benefit or harm from nominal sample counts.

## Positive results and remaining coverage

| Property | Evidence / limit |
| --- | --- |
| Controller, actor/dummy, legal cards, full history, trick leader, auction/vulnerability/dealer and tricks won | `row_view` equals `Game.observation()` at all 51 post-opening-lead positions in each of 12 seat-rotated legal games; public void reconstruction agrees. Original smoke also permutes hidden allocations. The unseen-dummy root is not a valid child call; actual evaluate applies the root card first. |
| Fresh posterior instead of root determinization | Instrumented real fixture child calls `read_layouts` with its own `Observation` and requested child count; returned worlds preserve known hands. Parent worlds are not supplied as child arguments. This checks plumbing, not learned-posterior calibration. |
| Depth and exception cleanup | Child continuations use plain `Seats`; child has recursion disabled. Parent and child `try/finally` restore the global factory on exceptions. Null and zero-call arms match base actions, values and RNG state on eight fixtures. |
| Reader identities | Original smoke covers own/opponent routes through plain and pooled readers. Added exception tests restore `net.who` for both paths. Current blind actor suppresses opponent identity. A future nonblind `meet` change would also need propagation to an already-created child and cache invalidation. |
| Scores/common bidder | Added tests verify the first-named-actor sign when internal candidate order reverses and that every spec reuses the common bidder. Runtime `worth` uses declarer-positive/defender-negative trick utility and scoring by declarer's vulnerability. Existing X8 tests cover trick/IMP signs. |
| Pairing and independence | The inherited collector keys play streams by board/ply/controller, not actor label; duplicate rooms use swapped partnerships. Common/native tables can be reused and are not extra independent samples. Published smoke manifest uses common bidding. Evaluate uncertainty over unique deal families, never child calls/rows. |
| Global factory/shared state | Current process workers execute choices serially, so factory swaps are not a demonstrated concurrency bug. The implementation is not thread-safe/reentrant. Reader caches key public prefixes/held-hand representations; no new cache-key leak was reproduced. Native claim shared state remains B09. |

## Reproduce and hand off

Tests live in
[`test_review_boundaries.py`](../scripts/stu_rollout_experiments/test_review_boundaries.py)
and [`test_review_protocol.py`](../scripts/stu_rollout_experiments/test_review_protocol.py).
They add no engine implementation and consume no training data.

Use a checkout of the pinned prototype for `STU_EXPERIMENT_SOURCE` and a separately
built pinned runtime for `STU_RUNTIME` (DDS build: `python scripts/build_dds.py`).
The source directory must contain `engine.py` from **7c79acf**, not an unrecorded
newer version:

```bash
export STU_RUNTIME=/path/to/runtime
export STU_EXPERIMENT_SOURCE=/path/to/prototype/scripts/stu_rollout_experiments
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 BRIDGE_NET_BF16=0
python scripts/stu_rollout_experiments/test_review_boundaries.py -v
python scripts/stu_rollout_experiments/test_review_protocol.py -v
# Expose the three known defects as ordinary failures:
python scripts/stu_rollout_experiments/test_review_boundaries.py --strict-known -v
python scripts/stu_rollout_experiments/test_review_protocol.py --strict-known -v
```

The boundary suite runs **9 tests: 7 pass, 2 expected failures**. Protocol suite:
**6 tests: 5 pass, 1 expected failure**. Strict mode fails only the named two
scheduling invariants and resume guard. Original smoke: **4 pass**. Expected
failures are findings, not acceptance; remove/review the markers when adopting a
fix. Existing X8 suite: **34 tests, 27 pass and 7 native-claim skips**, no failures.
The temporary cache positive control passes both strict scheduling witnesses.
[Machine-readable evidence](stu-rollout-helper-review-2026-11-14/evidence.json)
and [strict boundary output](stu-rollout-helper-review-2026-11-14/known-boundaries.log)
retain exact results; other suite logs are in the same directory.

Before starting corrected recursive screens, codex-rollout should run the strict
cache invariants, zero-budget/null parity and hidden-world invariance with the
real R4c BF16 setup and claim solver; verify new provenance/output identities;
publish actual candidate allocation and inclusive cost/attempt accounting; then
run the bounded paired smoke. Reader/guarantee claims need their native-solver
answer/timeout check too. A owns random-budget/direct-comparison/frontier design.
Only after these gates should a fresh held-out strength and net-version-by-search
interaction experiment be interpreted. No promotion is recommended by this review.
