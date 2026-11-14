# Stu helper A: allocation and learning-frontier selectors

14 November 2026. codex-rollout-helper-a, workspace e66e1dc51f48.
Deliverable for [issue #39, track A](https://github.com/maxschireson/Single-Dummy-Bridge/issues/39).
Proposal for the coordinator, not an experiment launch or adoption decision.

**First experiment:** after B's correctness gate, compare a fixed four-call
random allocator with a four-call selective allocator on the same 32-layout
roots, then match their measured per-bot cost and compare directly. Keep flat32
and flat128 anchors. The recommendation is falsified as a useful allocation
improvement if selection offers no verified root-action advantage over random
allocation at equal cost, or a small mechanism gain fails to improve held-out
full-bot play. A null low-exposure screen is inconclusive about deeper search in
general. Reproducible scheduling findings and the detailed cost/statistical
contract are in [the review appendix](../docs/stu-search-allocation-review-2026-11-14.md).

## Ownership and evidence

This proposal extends R02–R05 in [#38](https://github.com/maxschireson/Single-Dummy-Bridge/pull/38)
under [the integrated plan #35](https://github.com/maxschireson/Single-Dummy-Bridge/pull/35).
Helper B owns the independent correctness audit; codex-rollout integrates and
runs the search experiments. [#37](https://github.com/maxschireson/Single-Dummy-Bridge/pull/37)
retains H02 extraction and H03–H05 design with codex-stu-harvest, with loop
executing the approved experiments. This report supplies selector choices and
interfaces for that work, not another extractor or training campaign.

Design is based on experiment `7c79acfaa138a29d140dfef3d50f9a52216a24aa` and local
runtime `5addd826af8b10d7343df51ada528a7327d059b6`. Four existing smoke tests pass;
three allocation assertions reproduce bugs on that revision (see appendix).
No real-model gains or frontier location have been measured by this helper.
The initial mistaken description of B as the frontier helper is superseded by
this report and the corrected ownership claim in #39.

## 1. Playing selector S1: bounded, observable and auditable

The scheduling unit is a **unique child Observation**, including controller,
legal actions, own hand, public dummy, auction and ordered public history. Group
equal observations; a chosen child action must be propagated consistently to
all occurrences covered by the search policy. A hidden-world path key must not
decide whether equal observations receive different cached actions. The child
solver receives only its Observation and fresh posterior randomness. B's cache/
information-set checks are a prerequisite, not something a selector can repair.

For the first controlled comparison keep 32 outer layouts, four new child calls,
eight child layouts, two child candidates, one extra depth, own partnership and
eight plies. Reserve two calls for plies 1–4 and two for plies 5–8; unused early
capacity may roll forward. Within each window consider currently available
unique observations. This explicitly tests a two-window online schedule; it
does not pretend to rank future states that have not yet been reached.

Use candidate-stratified capacity where possible: first offer one call to each
root candidate with an eligible observation, in a root-observation-seeded
permutation; then allocate leftovers globally. A shared observation uses one
call and may benefit several candidates. Log unmet quotas and exposure. Apply
the same rule to the random and selective arms so this is not another confound.

For each available child group g, compute this **initial heuristic**, not a
calibrated probability or proven value-of-information estimate:

`priority(g) = W(g) * L(g) * [0.1 + U(g) + D(g) + A(g)] / max(cost_ms(g), 1)`

| Feature | Definition and reason |
| --- | --- |
| W | Sum of normalized outer posterior weights of occurrences, averaged across the relevant root candidates. Larger exposure gives a child decision more influence on root estimates. This is root planner bookkeeping, never a private hand supplied to the child. |
| U | `1 / (1 + top_two_logp_gap)` from the child-view net. Cheap uncertainty screen, bounded 0–1. It may prioritize equivalent cards; random and consequence controls test that failure. |
| D | Fraction of two independent child search panels that choose the same non-net alternative, set to zero unless both agree. Initially unavailable; enable only when those panels were actually computed, with their full cost charged. Persistent disagreement can find confident net errors. |
| A | Paired-sign ambiguity `2 * Phi(-abs(mean_delta)/SE_delta)` from those panels' per-layout action differences, in 0–1. Use a missing flag and zero term when absent; deterministic zero-SE cases have ambiguity 0 for a nonzero gap and 1 for exact ties. Avoid subtracting independent action SEs. |
| L | Estimated one-trick score sensitivity: mean absolute score change over an available child-view outcome distribution divided by 100 score points, clipped to [0.25, 3]. Default 1 with missing flag when no child-view distribution exists. Captures contract relevance without access to actual hidden cards or the true future result. Keep claiming/floor semantics fixed. |
| cost_ms | Median observed incremental child time for role, cards remaining, legal candidate count and current solver settings, from cost-only calibration; include posterior construction and claims. Back off to a pooled median for sparse cells. |

U, W and cost exist or can be measured cheaply; D, A and L are **not free
features in the current prototype**. Start S1 with U, W and calibrated cost,
L=1, D=A=0. Do not silently treat root-conditioned fork outcomes as child-view
panels. A next S2 arm can split its eight child layouts into two independently
drawn panels of four, then decide whether another block is worth buying. Charge
every pilot, including rejected ones. Compare S2 with random pilots of identical
cost; add it only if the first screen leaves budget and a credible mechanism.

The full score is a specified starting hypothesis; its equal weights and clamps
are not fitted claims. Freeze them for the first screen rather than sweeping
thresholds. Record confidence-versus-consequence ablations offline. Ultimately
replace the heuristic with a calibrated estimate of **verified root-action gain
per millisecond**, fitted on randomized development opportunities with family-
disjoint calibration. Child action changes alone are not the target.

For random allocation use the same eligibility, grouping, candidate quotas,
window reservations and call cap; substitute seeded random priority for the
score. Preserve a predeclared 20% exploration allocation when collecting data
for a learned selector. A hard budget makes inclusion probabilities conditional
on prior admissions; log the actual randomization mechanism rather than invent
unconditional weights. Random priority is fair within an observed opportunity
set, not uniform over every counterfactual future decision.

## 2. Label selector L1: reliable, useful and learnable

Playing priority and training priority have different targets. A costly rare
position may be worth solving at the table yet teach little reusable behavior.
Coordinate L1 with H05's approved approximately 2,000-pair / two-box-hour
reliability study; do not create an additional run or enlarge its budget here.

Partition by controller role (declarer/defense), strain (NT/trump), contract
class and trick band. Start with lead, 2–4, 5–7, 8–10, 11–13; split into individual
tricks only where family counts permit. Keep net action, proposed alternative
and candidate coverage explicit. Regret relative to a searched candidate subset
is **restricted regret**, not proof of the optimal legal action.

On separate diagnostic families, re-evaluate both actions from the child's own
posterior on independent panels. Preserve signed differences and uncertainties;
do not turn one winning sampled continuation into the target. Measure raw tricks
and claim-floored targets separately. Proposal/development outcomes choose a
position; independent verification estimates its advantage to reduce selection
bias. Unknown inclusion probabilities remain unknown.

Operational frontier rule, proposed for the first diagnostic report:

- In a cell, call the net competent **for the evaluated candidate set** only if
  the upper family-clustered 95% confidence limit of mean restricted regret is
  below 0.05 tricks/decision, evaluated-candidate coverage is reported, and at
  least 50 independent parent families contribute. These are declared exploratory
  thresholds, not observed facts or multiplicity-adjusted strength guarantees.
- The frontier is an earlier failing/uncertain band adjacent to a later competent
  band in the same role/contract stratum. If the profile is nonmonotone, retain
  multiple bands; if coverage/precision is inadequate, mark frontier unknown.
- Select actual ancestor observations one and two tricks before verified frontier
  mistakes when reconstruction exists on that same trajectory. Verify them from
  their own information too: a later loss does not establish an earlier decision
  error. Missing ancestor states are unavailable, not invented extra examples.
- Move the frontier earlier only after a subsequent trained net improves the
  current band on fresh diagnostic families at the same verification budget, with
  no material broad regression. Keep boundaries fixed during each training arm.

For the **extra** label budget, initially retain #37's 60% frontier/ancestors,
20% consequential disagreements elsewhere, 20% broad random coverage. Ordinary
root data remains broad. Within targeted cells rank by:

`cell_frequency * verified_advantage * reliability * learnability / total_label_cost`

Estimate frequency on a broad held-out diagnostic sample, not the enriched set.
Reliability records independent-panel sign agreement and uncertainty; avoid
discarding negative/tied evidence from the underlying dataset. Learnability is
the held-out reduction in restricted regret after a small compute-matched
training pilot on that cell; before such a pilot it is unknown, so use equal
cell quotas instead of claiming to have measured it. Include extraction,
verification and training time in cost. Cap per-family contributions and retain
source strata; 200 descendants of one deal are not 200 independent labels.

H03/H04's root-only / broad-extra / targeted-extra arms remain the training test.
Match base-data mix, pair weight, actual pair presentations and optimization
compute; loop chooses architecture after P10. A low-label-reliability result
stops the targeted training proposal until label quality is addressed. A reliable
but unlearnable cell loses priority; high error alone is not a curriculum.

## 3. Small experiment and stopping contract

| Stage | Arms / endpoint | Stop or extend |
| --- | --- | --- |
| Correctness | B's independent gate, existing smoke and A's three regressions | Do not interpret recursive/selective strength before corrected immutable source passes |
| Cost/mechanism | 16 smoke then 128 development families: F32, random32, S1-32 and F128; retain earliest32 only as the old-prototype diagnostic | Stop on invariant/failed-board issues; inspect actual expansion mass and paired root-action changes. No modest-gain claim |
| Allocation | S1 versus random, matched actual per-bot time; direct paired play plus fixed-opponent paired diagnostics | If call usage/time differs, calibrate random admission or reinvest savings and freeze a new comparison. Do not credit an extra-compute advantage to selection |
| Breadth/depth | Shortlisted child allocator versus flat breadth at matched candidate cost | Freeze one finalist, utility, time/tail limits and family set before confirmation |
| Gain transfer | Net-version × search factorial below | Estimate interaction with a paired family interval, not a retained-percentage ratio |
| Learning | H05 reliability, then H03/H04 matched training arms | Existing ownership/budget/gates apply; judge later held-out full-bot improvement per total compute |

Use development variance to budget confirmation; start with the leader's 1,000
fresh families only if its achievable interval is useful. Declare the maximum
families/box-hours and analysis time in advance. Extend once for a predeclared
precision target within the coordinator's budget, not repeatedly until favorable.
If any candidate is advanced from repeated looks, use a valid sequential rule or
an independent final holdout. Report inconclusive when precision is insufficient.
The appendix gives the clustering, failure, cost and power details.

## 4. Does search preserve more of a better net's gain?

After cheap screening, choose old/new nets from pinned provenance and hold the
opponent pool, common bidder, family list and numerical mode fixed. Both nets
must be untrained on confirmation families. No training-data overlap is repaired
merely by using a new seed.

| Net | Flat search | Candidate allocation |
| --- | --- | --- |
| Old | Y(old, flat) | Y(old, candidate) |
| New | Y(new, flat) | Y(new, candidate) |

For each family i, all Y values are same-oriented played IMPs against the fixed
opponent pool, aggregated with prespecified equal opponent weights. Estimate:

`interaction_i = [Y_i(new,candidate) - Y_i(old,candidate)]`
`              - [Y_i(new,flat) - Y_i(old,flat)]`

Cluster all cells, opponents, rooms and rotations within family when forming
the interaction SE/interval. Report both net gains, absolute candidate strength,
the interaction and all four costs. A positive interaction without competitive
absolute play is not an adoption result. The product comparison matches per-bot
time across cells; a fixed-work secondary analysis can distinguish allocation
changes from the newer net's inference cost. Net-only old/new comparisons are a
separate diagnostic; avoid dividing by their small/noisy gain.

If the interaction is promising, isolate table-net-only and continuation-net-only
upgrades as the next mechanistic ablations, including their joint setting if
needed. Do not change posterior reader, proposal net and continuation net without
recording which components differ. This is conditional follow-up, not an initial
eight-way sweep. BEN blind release testing remains loop's protected gate.

## 5. Logging and handoff

One ledger row per unique observable opportunity, linked to parent family and
episode/source/model/config hashes, should contain:

- root/child ply, controller/actor, role, contract class, Observation key/schema,
  candidate-set coverage and ancestor links; hidden hands stay label-only;
- W/U/D/A/L, missing flags, paired-panel sizes/SEs, predicted/actual cost,
  scheduler seed, admission rule, window/quota/budget state and rejection reason;
- new search/cache service, actual pre-override and child cards, root card
  before/after the computation, affected candidate/layout weight and legality;
- raw and claim-floored labels, independent verification stream/provenance,
  signed outcomes, posterior effective size, failures and measured wall/CPU/RSS;
- train/development/calibration/confirmation family assignment and inclusion
  probability when actually known, with descendants inheriting exclusions.

Post the ledger schema/selector settings to #37 for codex-stu-harvest to reconcile
with H05; no change to their extractor is assumed. Evaluation seed 2026111401,
seed 131 and the squeeze suite and all descendants remain excluded from training.
No human-table training, production promotion or box action is part of this
deliverable.
