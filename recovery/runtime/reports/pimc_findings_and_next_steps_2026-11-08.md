# PIMC, consistent strategies, and the next learning experiments

8 November 2026 · Research checkpoint and reconstructed experiment report

## Decision

**Keep PIMC as the current playing baseline. Build better beliefs and a learned
selector for PIMC-equal or near-equal plays next. Keep the alpha-mu implementation
as a correctness reference, source of executable strategy examples, and candidate
for selective escalation.** No learned model has yet been trained or evaluated.

We established that strategy fusion causes real valuation and first-move errors,
and built a solver that corrects those errors on specified small information
sets. We did **not** establish that the resulting full-hand players are stronger
for their cost. The larger experiment reversed the small positive pilot results:
the alpha-mu ending hybrid lost slightly, and the rollout planner delivered no
measurable improvement over its matched continuation despite much higher cost.

This is evidence about our Python reference implementation, eight-world samples,
continuations and defender models. It is not a verdict on the alpha-mu algorithm
or a reproduction of the published implementations' performance.

## Publication and recovered state

The experimental source is frozen on
[`research/pimc-study-2026-11-08`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/pimc-study-2026-11-08),
at commit [`6525707e394b7df095ad458cac40835ba8ae5b61`](https://github.com/maxschireson/Single-Dummy-Bridge/commit/6525707e394b7df095ad458cac40835ba8ae5b61).
This report belongs on `main`; the experimental players are not promoted into
`main` by this publication. The existing
[v4 architecture document](../docs/Single_Dummy_Machine_v4.pdf) remains the broader
design, with this report supplying the newer measured checkpoint.

The source snapshot has Git tree
`9a74531d0cd7e5647466cbba4a2533f9eb8194fa`. It preserves the recovered source
and documentation exactly, including the newer cost and partition work that was
not in the initial draft PR. The initial implementation was recorded in
`cb20483`; its historical discussion is in [draft PR #1](https://github.com/maxschireson/Single-Dummy-Bridge/pull/1).
The publication uses a separate branch so continuing work there is independent.
Bulk experiment records, corpora, logs, binaries and weights are excluded.

| Component | Recovered implementation and status |
|---|---|
| PIMC baseline | Uniform sampling subject to card counts and observed voids; DDS evaluates legal cards. No learned auction/play likelihoods. |
| Alpha-mu reference | Related layouts, shared declarer choices, Pareto outcome vectors, executable policy witnesses, validation, memoization and incremental dominance pruning. |
| Ending hybrid | PIMC earlier; attempts terminal alpha-mu search with at most three cards per hand, following the policy while observations remain supported. |
| Rollout planner | Searches a bounded declarer prefix and executes an explicit continuation to the end against fixed, information-limited defender policies. |
| Finite-domain certificates | Complete EW allocation families, retained strategy frontiers, verified outcome partitions, reweighting and policy compression measurements. |
| Measurement | Paired trials, CPU and wall timing, family-aware uncertainty, replay, resumable cost study and symmetry-counting scripts. |
| Not implemented here | Trained belief/selector networks, learning league, universal single-dummy tablebase, cross-family proof generalization, or related-deal DDS proof-cache reuse. |

The last item matters: fixed-NS families were **tested**, but these results do
not measure the separate ongoing work to reuse DDS proofs across those layouts.

## What the strategy solver actually guarantees

PIMC evaluates a different perfect-information continuation in each sampled
world. Those continuations may require incompatible choices before declarer can
tell the worlds apart. A consistent strategy must choose the same action at
indistinguishable histories and may branch only on information actually observed.

The terminal alpha-mu search retains achievable vectors and policy witnesses.
On a completed search it is exact for its **supplied finite layouts, deterministic
declarer strategies and omniscient adversarial defence**. That does not establish
complete belief support, optimal play against ordinary defenders, or an
imperfect-information equilibrium for both partnerships. Depth-limited variants
with DDS leaves still have fusion beyond the horizon and are explicitly marked
non-executable when the selected witness contains such a leaf.

The full-hand rollout planner has a different model: each defender and
continuation player acts through its own permitted observation. It evaluates
actual terminal outcomes of an executable policy, including the fallback, rather
than substituting a DD value at the horizon. It commits to its searched prefix;
the reported value is not silently assigned to an untested replanning policy.

## Tests and measurements

### 1. Exact small endings: fusion is real, but correcting it is expensive

Each family fixes North/South and samples eight EW layouts. Strains cycle through
all four trump suits and NT; half the families use two suits. These are synthetic
tactical tests, not an estimate of fusion frequency in tournament play.

| Cards per hand | Families | PIMC best-value overvaluations | Inferior PIMC first choices | Mean PIMC time | Mean terminal alpha-mu time |
|---|---:|---:|---:|---:|---:|
| 3 | 1,000 | 40 | 8 | 3.94 ms | 52.16 ms |
| 4 | 100 | 9 | 2 | 5.48 ms | 1,705.23 ms |

All selected exact policies were verified against every legal defensive reply
in all 8,800 sampled layouts. First-choice regret gives PIMC optimal consistent
play after its chosen first card, isolating that choice from later mistakes.
The inferior-choice counts include deterministic tie-breaking failures, not
only strictly incorrect DD rankings. The largest first-choice losses were
0.25 and 0.125 expected tricks respectively; the largest value overstatements
were 0.50 and 0.375 tricks.

One preserved three-card example gives both the spade ten and heart queen a
PIMC value of 12.875 final tricks. Their best consistent values are 12.625 and
12.875 respectively. This is a concrete reason to learn selection among PIMC
ties. It is not evidence that all fusion mistakes occur among ties.

Going from three to four cards increased mean reference-search time about
33-fold in these samples. This implementation does not contain all published
alpha-mu cuts or redundant-world optimizations; Python overhead and witness
storage also matter. These timings do not estimate an optimized native solver.

### 2. Full-hand pilots: useful for screening, superseded for direction

Three 100-board paired pilots used fixed opening leads, synthetic contracts and
common greedy defenders, optimizing tricks:

| Candidate and comparator | Gain in tricks/board | Interpretation |
|---|---:|---|
| Two-choice planner with greedy tail vs PIMC-8 | -1.00 | A weak continuation substantially limits this planner. |
| PIMC-8 with alpha-mu endings vs PIMC-8 | +0.02 | Small initial positive result; did not persist. |
| One-choice planner with PIMC-2 tail vs identical continuation | +0.05 | About 14 times the runtime; IMP interval included zero. Did not persist. |

A preliminary uncoupled hybrid comparison was excluded because early PIMC
sampling differences confounded the intervention. The accepted pilot coupled
those streams. A separate 20-board rollout pilot also preceded the fresh
100-board result; it is not additional confirmation.

### 3. Larger cost study: 1,000 boards and five configurations

The study used 500 independent deals plus 50 fixed-NS families of 10 EW layouts:
550 independent resampling clusters. Every configuration played every board,
giving 5,000 completed tables. Opening leads and greedy defenders were shared,
the objective was tricks, PIMC streams were coupled, and execution order rotated.

Intervals below are approximate pointwise 95% intervals from 2,000 paired
cluster-bootstrap replicates. Resampling preserves complete families and the
broad/related cohort mix. These are not multiple-comparison-adjusted promotion
tests or evidence of tournament strength.

| Candidate vs comparator | Tricks/board gain (95% interval) | CPU ratio | Tricks/board per time doubling (95% interval) |
|---|---:|---:|---:|
| Alpha-mu-8 hybrid vs PIMC-8 | -0.012 [-0.023, -0.001] | 1.083× | -0.105 [-0.202, -0.008] |
| PIMC-16 vs PIMC-8 | +0.039 [-0.016, +0.092] | 2.029× | +0.038 [-0.016, +0.089] |
| Planner-8 / PIMC-2 tail vs matched continuation | -0.006 [-0.057, +0.047] | 13.372× | -0.002 [-0.015, +0.013] |
| Planner-8 / PIMC-2 tail vs PIMC-8 | -0.308 [-0.378, -0.236] | 3.478× | -0.171 [-0.211, -0.130] |

| Configuration | Declarer-policy CPU seconds per board |
|---|---:|
| PIMC-8 | 0.537 |
| Alpha-mu-8 hybrid | 0.581 |
| PIMC-16 | 1.089 |
| Matched PIMC-2 continuation | 0.140 |
| Planner-8 / PIMC-2 tail | 1.867 |

The requested efficiency grade is
`gain in tricks/board / log2(candidate CPU / comparator CPU)`, using ratios of
aggregate CPU totals. It is a finite-difference slope, not a forecast of gain
from future doublings. In particular, the hybrid's -0.105 grade rescales a
small -0.012 absolute loss over just 0.1145 time doublings. Near-equal costs can
make this ratio misleading; always retain absolute gains and costs, and use
dominance/tradeoff comparisons when the denominator is unstable or nonpositive.

CPU includes declarer planning and continuation actions, but excludes player
construction, common defenders and opening-lead selection. Six worker processes
shared the machine; wall-time ratios were similar. This measures incremental
policy cost, not complete application latency. Future learned-player trials must
also report total elapsed cost, including belief and selector inference.

The hybrid won 7 boards, lost 17 and tied 976. It formed 1,158 exact plans and
executed 4,393 later policy actions, with 362 out-of-support observations on 356
boards and no search-budget fallbacks. Its point estimates were negative in
both independent (-0.014) and related (-0.010) cohorts. The planner likewise
showed no convincing advantage in either cohort. Doubling PIMC samples had a
positive point estimate, but its interval includes zero.

Eight sampled worlds are not the full information set. The study does not
separate incomplete-support effects, pessimistic omniscient defence, and changed
tie-breaking as explanations for the hybrid's loss. Nor does it isolate which
of the rollout planner's sample size, prefix, continuation or defender model is
the main limitation. Those are hypotheses for subsequent ablations.

### 4. Memorization and semantic partitions

There are two different storage problems. DD tables store values of complete
positions. Single-dummy reuse must preserve knowledge, legal observation branches
and a common executable strategy, with explicit defender-model assumptions.

Our independent counting script gives these **DD trick-boundary** counts after
relative-rank normalization, leader rotation and the appropriate suit symmetries:

| Cards per hand | Combined NT + canonical-trump states | Ideal values-only storage |
|---|---:|---:|
| 3 | 39,552,072 | 9.43 MiB at 2 bits/value |
| 4 | 12,881,180,760 | 4.50 GiB at 3 bits/value |

These counts exclude indices, actions, metadata and mid-trick states, and are
not a minimal representation. Stone, Sturtevant and Schaeffer's published
Setrograde work reports roughly 0.001 GiB for 12 total cards and 0.05 GiB for
16 total cards using additional DD set representations [3]. Those are their
results, not a database built or reproduced here.

With fixed declaring hands and unseen pool, three-card defenders have up to 20
allocations; four-card defenders have 70. Arbitrary support subsets number
2^20 and 2^70, although not all need be reachable knowledge states. Histories,
beliefs and defensive knowledge add distinctions. A complete policy frontier
for a fixed domain/model can be reweighted instead of enumerating all probability
vectors; an eight-world sample is not such a complete domain.

We tested a finite semantic-partition prototype on 100 fresh three-card families,
enumerating all 20 EW allocations per family:

| Measurement | Result |
|---|---:|
| Verified layouts | 2,000 |
| Retained strategies | 247; mean 2.47, maximum 64 per family |
| Families with one retained strategy | 78/100 |
| Outcome cells per strategy | Mean 5.60, maximum 14 |
| Policy nodes before/after identical-suffix sharing | Mean 703.42 / 236.86 per family |
| Compressed policy witnesses | Mean 1,145 bytes, maximum 3,611 per family |
| Mean search time | 0.148 seconds per family, excluding certificate checks/encoding |

Every retained strategy and every decoded compressed witness was executed
against all permitted defensive replies throughout its finite domain. The
compressed sizes omit domain keys, outcome vectors, models, proof metadata and
indices: they are not complete cache-entry sizes or global storage projections.
Twenty two-bit outcome values require only five bytes per strategy, so predicate
cells alone are not yet a demonstrated byte saving.

The promising direction is reusable strategy structure and verified regions.
The prototype proves only enumerated domains; no cross-family generalization
or cache hit-rate improvement has been established. A predicate such as "West
holds the queen" may classify a policy's success region, but it cannot control
an action until play reveals enough information. Equal DD values do not certify
a shared strategy. The distinction is between "each world has some winning
line" and "one observation-consistent strategy works across those worlds."

## Approach going forward

### First: freeze the experiment boundary and collect useful learning data

Retain PIMC-8, PIMC-16, the matched continuation and the archived strategy players
as immutable references. Add versioned actor observations, candidate actions,
per-world PIMC differences, sampled-layout provenance, actual continuation
outcomes, opponent versions and exploration propensities to the learning records.
Separate public actor inputs from full-state labels/critics. Preserve historical
bots and frozen evaluation panels as described in the v4 league architecture.

Split by original deal or fixed-NS family, never by decision row. The recovered
1,000-board suite is now development evidence, not a fresh promotion set. Generate
new held-out families and use stronger, varied defender policies. Auction-aware
models need realistic auctions, frozen engine auctions or curated deals; the
existing synthetic auctions are unsuitable evidence for auction inference.

### Second: a small, calibrated belief model

Start by scoring or resampling existing constraint-valid **joint layouts** from
the actor's auction/play history and known agreements. A modest mixture over
opponent skill/style is a useful latent variable; evaluate it separately rather
than assuming one opponent type. Independent card marginals alone neither capture
important correlations nor guarantee legal complete hands.

Keep a broad-support sampling component and test calibration, joint-layout
likelihood, important-honour/shape probabilities and effective sample size.
Distinguish a deliberately tempered posterior from an importance-sampling
proposal; carry weights correctly and do not apply likelihood evidence twice.
Scoring a fixed proposal pool cannot recover layouts that never entered it.

Start with a compact model and profile it. Its practical gate is better decisions
after charging inference and sampling time. Better likelihood is a diagnostic,
not a substitute for playing-strength evidence. Keep probability calibration
separate from any end-to-end action heuristic that changes weights just to win.

### Third: a learned selector among PIMC candidates

Use your proposed exact-tie selector as the first clean ablation. Then test a
near-tie gate using paired per-world action differences and a margin selected
only on development data. Measure how often each gate excludes the better
consistent move on reference endings. A falsely optimistic uniquely best PIMC
move can defeat a tie-only gate; sampling confidence does not cover fusion bias.

Inputs are the permitted actor view, candidate cards, belief summaries and
aggregate PIMC features. Targets are realized self-play continuation outcomes or
paired, information-correct continuation rollouts from the same state. Do not
label the selector simply by playing double dummy after each candidate. Every
simulated continuation actor receives only its own information; full state may
serve as a training label or critic input, never as a deployed actor input.

Train against retained opponent/partner generations, not one co-adapting pair.
Log exploration so unchosen actions are not treated as observed failures.
Use paired candidate rollouts on common hidden layouts/opponent versions when
worth their cost. The aim is to learn entries, information gathering and coherent
continuation choices that DD-equal values miss. A learned selector remains an
approximation; it does not eliminate fusion by construction.

### Fourth: separate the sources of improvement before combining them

| Arena candidate | Question |
|---|---|
| PIMC-8 and PIMC-16 | What does spending more on ordinary samples buy? |
| Belief + PIMC-8 | Do improved layout populations improve play at their actual cost? |
| Selector + PIMC-8 | Does learned choice improve equal/near-equal decisions? |
| Belief + selector + PIMC-8 | Do the benefits combine, or interfere? |
| Optional selective alpha-mu | Is escalation useful on a predeclared decision subset? |

Keep exact-tie and near-tie selectors separate. Test overriding a clear PIMC
preference only as a further ablation. Freeze model and opponent versions for
each evaluation and use multiple training seeds when judging a training method.
Choose promotion sample sizes from paired variance and a predeclared meaningful
gain; do not repeatedly inspect an ordinary interval until it turns positive.

Report tricks/board and the quality-cost curve, including equal elapsed-time
comparisons, gain per meaningful time doubling, decision-latency tails, failures,
and protected slices such as related layouts. Track training and data-generation
compute separately, with an amortized view at declared deployment volumes.

### Continue strategy and solver research behind those interfaces

Alpha-mu remains useful for fusion regressions, verified witnesses and selected
teacher calls under its stated defence model. Semantic work should propose a
weaker domain condition, verify the common strategy and observation transitions,
retain counterexamples, and refine only the distinctions needed. Keep exhaustive
certificates separate from sampled checks or learned approximations.

Related-layout DDS reuse can make PIMC, rollouts and teachers cheaper. Measure it
independently and then jointly with learning, including small-batch overhead.
Do not reuse a DD proof as a single-dummy strategy certificate. Promotion requires
measured benefit after validation and lookup costs, not just higher reuse counts.

The likely strong bot combines joint beliefs, fast learned policy/value estimates,
PIMC tactical evaluation, selective consistent-strategy search and efficient
related-world solving. The immediate milestone is a repeatable belief-only /
selector-only / combined experiment, not a larger always-on exact planner.

## Reproduction and publication audit

Check out the pinned code commit, then run:

```sh
git clone https://github.com/maxschireson/Single-Dummy-Bridge.git
cd Single-Dummy-Bridge
git checkout 6525707e394b7df095ad458cac40835ba8ae5b61
python3 scripts/build_dds.py
python3 -m unittest discover -s tests -v
python3 scripts/benchmark_cost_curve.py --count 1000 --workers 6 --seed 860001 --family-size 10 --out results/cost_curve_1000.jsonl
python3 scripts/benchmark_partitions.py --count 100 --out results/partitions_100.jsonl
python3 scripts/count_ending_symmetries.py
```

The cost script supports `--resume` with the same output/configuration. Pilot and
ending commands are in the pinned
[strategy design](https://github.com/maxschireson/Single-Dummy-Bridge/blob/6525707e394b7df095ad458cac40835ba8ae5b61/docs/consistent_strategies.md).
Detailed tables and model qualifications are in the pinned
[pilot report](https://github.com/maxschireson/Single-Dummy-Bridge/blob/6525707e394b7df095ad458cac40835ba8ae5b61/reports/consistent_strategies.md),
[cost/partition report](https://github.com/maxschireson/Single-Dummy-Bridge/blob/6525707e394b7df095ad458cac40835ba8ae5b61/reports/strategy_cost_and_partitions.md),
and [information-state design](https://github.com/maxschireson/Single-Dummy-Bridge/blob/6525707e394b7df095ad458cac40835ba8ae5b61/docs/information_strategies_partitions.md).

The original larger study used Python 3.12.14 on x86_64 with six processes and
DDS revision `0f969b86a4841f438fd0cdff2924c4f2404abf6a`. It did not preserve a
controlled hardware benchmark record, so absolute timings are exploratory.

For this publication we independently checked the recovered evidence:

- All 40 unit/system tests passed in the isolated snapshot.
- Recomputing the larger study's bootstrap summaries from all 1,000 saved rows
  matched the saved summaries exactly; IDs were unique and cohort counts correct.
- All 5,000 saved larger-study tables replayed legally to their recorded trick
  totals; all 600 tables from the three reported 100-board pilots replayed with
  matching scores.
- DDS rebuilt from the included sources. Fresh execution of all five variants
  on four selected boards (two broad, two related) reproduced every recorded card,
  trick total, event count and DDS-call count exactly. Timing was not compared.
- The published code tree equals the recovered source tree. No experimental
  player logic was changed during reconstruction.

This is an audit and small deterministic reproduction of the earlier runs, not
a newly generated 1,000-board strength trial. Raw-run SHA-256 identifiers are:

```text
cost_curve_1000.jsonl  48b956672942261d97e84bd3ef103c71c32db2c14f360977ff8c54f369dd337b
partitions_100.jsonl  08d9f97f16557037765bcce1cb3e09b99741614de3a63762de751072ff164874
```

These identify the recovered bytes. Reruns have different timings and potentially
different parallel completion order, so byte-identical raw hashes are not expected.

## Credit and source provenance

Max Schireson initiated and directed the work, proposed the consistent-strategy,
semantic-partition and learned-belief/selector directions, and required grading
by tricks per board per time doubling. OpenAI ChatGPT/Codex assisted with design,
implementation, tests, experiments, reconstruction and this report.

1. Tristan Cazenave and Véronique Ventos, [*The αμ Search Algorithm for the Game
   of Bridge*](https://arxiv.org/abs/1911.07960), 2019. The shared-decision,
   strategy-fusion and non-locality work is theirs, not a new invention here.
2. Tristan Cazenave, Swann Legras and Véronique Ventos,
   [*Optimizing αμ*](https://arxiv.org/abs/2101.12639), 2021. Their Pareto-front
   optimizations informed this reference implementation; not all are implemented.
3. Isaac Stone, Nathan R. Sturtevant and Jonathan Schaeffer,
   [*Set-Based Retrograde Analysis: Precomputing the Solution to 28-card Bridge
   Double Dummy Deals*](https://www.ijcai.org/proceedings/2025/0995.pdf), IJCAI 2025.
   Its DD results motivate set compression without establishing single-dummy reuse.
4. [DDS](https://github.com/dds-bridge/dds), created by Bo Haglund and developed
   by Soren Hein and the DDS contributors, supplies the native tactical solver.
   Its pinned sources, notices and Apache-2.0 license are retained unchanged.
5. The background also builds on earlier work by Ian Frank, David Basin and
   Matthew L. Ginsberg on imperfect-information bridge and partition search.
   The existing [BEN](https://github.com/lorserker/ben) adapter credits its
   contributors; these new trials did not benchmark playing strength against BEN.

The recovered alpha-mu code is independently written from the algorithmic ideas;
no upstream alpha-mu software was imported. The earlier source review did not
locate an Apache-licensed alpha-mu release. The papers' publication licenses do
not establish a software license. Our additions use this repository's Apache-2.0
license, separately from DDS's upstream license. Full attribution, additional
background references and provenance are preserved in the pinned
[CREDITS.md](https://github.com/maxschireson/Single-Dummy-Bridge/blob/6525707e394b7df095ad458cac40835ba8ae5b61/CREDITS.md).
No endorsement by the cited authors or projects is implied.
