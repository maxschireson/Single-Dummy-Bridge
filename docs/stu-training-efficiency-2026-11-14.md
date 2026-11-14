# Stu integrated improvement plan: training, rollout search and gain transfer

Date: 14 November 2026. Prepared for Max and the Stu loop lead.

Status: integrated plan. The original efficiency observations below are historical; current ownership and execution updates are summarized here. Approved implementation, experimental execution, and production adoption remain distinct.
Max requested publication to GitHub, then asked: "I would like Stu leader to review; if he approves you can go ahead with some of these changes as agreed."

The reviewer is **loop**, owner of the Stu training loop, identified on the [coordination board](https://github.com/maxschireson/Single-Dummy-Bridge/blob/box/coordination/BOARD.md) as [session_01N2EvxDPjdoFBFtyygdYP4j](https://claude.ai/code/session_01N2EvxDPjdoFBFtyygdYP4j). The separate **perf** session owns the existing batching work. Review should specify approved action IDs, scope, implementation owner, and any box/time allocation. Publication or a general endorsement is not approval to launch every experiment.

## Recommendation

Improve the current Azure fleet first. Remove redundant training work, evaluate the existing batching improvements on the actual Azure CPU, and reuse prepared data. Build bounded-memory training before buying larger-memory machines. Use the incoming four Macs continuously, with collection overlapping training and occasional Azure bursts for BEN evaluation.

Use three separate milestones: a training checkpoint, a model accepted for collection, and a release with substantial full-bot evaluation. This preserves frequent learning without requiring an expensive strength claim for every small update.


## Integrated priority and execution update — 14 November, 20:46 UTC

Keep one decision document: this plan combines the existing P-series workflow work,
H-series data work and new R-series rollout study. Detailed extraction and runnable
search protocols are linked appendices, not competing recommendation lists.

The objective is **full-bot strength gained per compute hour**, with two explicit
components: improve the net faster, and transfer more of that improvement through
the search into actual play. More layouts alone primarily address sampling noise;
they do not fix biased continuations or a mismatch between simulated and table play.

| Workstream | Current owner and scope | How it connects |
| --- | --- | --- |
| P01/P03/P08; P04 code | codex-stu-efficiency, per [loop's review](https://github.com/maxschireson/Single-Dummy-Bridge/pull/35#issuecomment-6883836024); implementation in #36 | Recover time and measure learning/compute efficiency |
| P02; P10 post-run report | perf; P10 reporting transferred at 20:58 UTC; P02 gets up to 3 box-hours on azure3 (azure7 is assigned to P10) | Cheaper inference can fund more useful search or data |
| P09 and P10 experiments/adoption | loop; azure5 width run and azure7 compute control | Separate larger-net value from extra training compute |
| H01–H05 | H01 loop; H02 and H03–H05 design codex-stu-harvest; [review and protocol in #37](https://github.com/maxschireson/Single-Dummy-Bridge/pull/37) | Harvest existing pairs, then selectively reanalyze from the child's own information |
| R00–R06 | codex-rollout; Max explicitly authorized execution and one Azure collector reassignment | Study mechanisms that retain net gains in full-bot play; [runnable appendix and implementation #38](https://github.com/maxschireson/Single-Dummy-Bridge/pull/38) |

P05/P06/P07 and H06 remain deferred under the prior review. The new R-series
authorization does not silently approve those recipe changes or promote a bot.

### Rollout exploration sequence

1. **Cheap mechanism checks:** role-correct history-reader identity and generic
   opponent contract-preservation behavior, independently, at 128 layouts.
2. **Breadth versus depth:** flat 128, flat 32, then 32 outer layouts with a bounded
   8-layout child search at future own-partnership decisions. Each child sees only
   its own information and samples its own posterior. Never let a child optimize
   using the enclosing complete deal.
3. **Dynamic allocation:** compare uniform and uncertainty-triggered replanning,
   then improve the trigger using repeatable net/search disagreement, paired action
   uncertainty and contract leverage. Match measured move cost before strength claims.
4. **Learning frontier:** use stronger reanalysis where the net can learn a useful
   decision, at the competence boundary and one/two tricks before it. Preserve
   random coverage and family-disjoint confirmation. Coordinate this with H03–H05,
   rather than creating a second pair-extraction/training project.
5. **Further mechanisms:** score/IMP objective, calibrated net/search blending and
   learned cutoffs after the first screen; keep objective-dependent thresholds explicit.

**Gain-transfer confirmation:** after screening, compare old/new net × baseline/candidate search on the same held-out families and fixed opponent pool. Report the paired difference-in-differences and uncertainty, alongside absolute strength and compute. Table-net-only and continuation-net-only ablations can locate the interaction. Avoid unstable retained-gain percentages when the net-only gain is small or noisy.

At the table, optimize IMPs at fixed move time. For training, optimize subsequent
held-out full-bot IMP improvement per labeling/training hour. These are different
measurements; a difficult or uncertain position is not automatically valuable for
either. A single imagined-layout fork is not a strong posterior-search label.

### Current rollout decisions — 22:20 UTC

Max has explicitly requested larger recursion tests despite the extra cost, against **both R4c128 and BEN**. Measure the strength/time curve before discarding expensive search. Equal-time comparisons remain necessary for deployment choices; they are not a reason to skip the unconstrained strength experiment.

- Azure6: corrected d82f9a7 engine,8workers,512 fresh paired families against R4c128, followed by flat32 on the same families (seed2026111401,indices6000–6511). At22:18:32,62 completed boards gave **−0.0323 ±0.4953 IMP/board**, with recursion at2.18× the control's action wall time. Zero failed attempts. This is an interim development estimate, not a positive result.
- The corrected16-board smoke had recursion minus flat32 **+1.5625 ±1.2648**, at about4.17× flat32's time. The2.31× figure used **R4c128** as its timing denominator; it does not describe the flat32 comparison. This tiny panel cannot establish a large effect.
- Azure2: finish guarantee512 unchanged, defer combined, then dedicated BEN64 lanes. Source4951fb0 adds endpoint isolation and explicit external-server CPU scope;27tests pass locally and AzureBF16. Runner is active waiting for clean handoff.8-board pilots precede256 fresh matched families in alternating32-board flat128/recursive32 blocks against identical BEN settings and common bidding. No BEN score exists yet.
- Initial box deadlines remain ~02:52/02:59UTC. Third-box capacity is requested from the next released slot in#44, without interrupting existing assignments. No new production actor or training recipe is promoted.

**Opponent information roadmap.** Max's explanation is plausible: generic continuation behavior may discard useful distinctions learned by the net. It is not yet established as the cause of lost full-bot gain. PR42 adds randomized populations and public identity/disclosure hooks; randomization itself does not train the missing population embedding or make the history reader consume disclosed style. Its variable identifiers still need an explicit neural-vocabulary mapping; unknown identifiers otherwise fall back to the generic embedding. Loop reports identity dropout was zero after v2, so that unknown embedding was not refreshed in later rounds, although shared network weights were.

Build one integrated experiment with loop/sidplay: current generic fallback; generic fallback retrained on diversified styles; trained population conditioning; and public-disclosure/history-conditioned style. Hold out styles/populations as well as deal families. Retain legally available population information and sample a latent persona consistently through a trajectory (including partnership correlation); do not reveal an opponent's private sampled persona or enclosing hidden layout to a child. Compare these at fixed search and then old/new net × flat/recursive search to measure transfer. Freeze current search panels before introducing identity/style changes.

**Learning frontier update.** Loop's H05 reports reliability of single-layout pair labels rising from0.07/0.09 at tricks1–2/3–4 to0.63/0.87 at tricks9–10/11–13. This supports measuring label quality explicitly: an early difficult decision can be valuable for search while its single-layout training label is mostly noise. Use uncertainty/random allocation controls and posterior-panel reanalysis in H03/H04; preserve raw labels and separate label reliability from inferred search value. H02/H03 ownership remains in#37.

**Historical execution checkpoint — 21:49 UTC:** Max authorized Azure6 and Azure2, initially
six hours each, and assigned helpers A/B through [#39](https://github.com/maxschireson/Single-Dummy-Bridge/issues/39).
A's [#41](https://github.com/maxschireson/Single-Dummy-Bridge/pull/41) and B's
[#43](https://github.com/maxschireson/Single-Dummy-Bridge/pull/43) exposed genuine
cache/scheduling/counting and experimental-accounting defects in the first depth
prototype. **Azure6's old batch stopped at 21:23:14; its recursive/selective scores
are invalid for inference.** Preserved results are not overwritten or pooled.

Corrected source `d82f9a7` in #38 passes 25 local regression tests. It groups by
child Observation, removes private-layout path gating, applies cached moves before
budget/eligibility, and counts actual sampled-action replacements. A fresh-only
driver rejects nonempty output directories, retains a first-attempt failure ledger
without automatic retry, isolates claim solvers per actor/room/child decision, and
records per-actor inclusive wall/worker/native CPU, cache/timeouts and actual
precision. Old whole-match Python CPU excludes native solver work and is not an
equal-time measure. Real R4c/BF16/native-SURE acceptance passed at 21:46 UTC: baseline/null/zero action,
value and RNG parity on four views plus a real child search. The 25 new tests pass
on Azure BF16; all 34 existing X8 tests pass in their intended FP32 mode with native
SURE. Three original fixtures that assume FP32 failed under forced BF16; those
logs remain preserved. Fresh `rx2-*` correctness smokes started at 21:48:37 UTC
(unit stu-rollout-v2-smokes, source d82f9a7); no larger depth screen automatically follows.

A is implementing the matched random-versus-S1 allocation control with common
window/candidate quotas. B independently re-reviews the corrected source.
Azure2's separate sham/reader/guarantee/combined mechanism screens continue as
development diagnostics; reader completed 512 boards at +0.115 ±0.167 IMP/board, inconclusive.
The 32-board sham is all ties. No adoption claim is made.

[Azure6 progress](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/stu-rollout-experiments-azure6-20261114)
and [Azure2 progress](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/stu-rollout-experiments-azure2-20261114)
retain manifests, provenance, summaries, records and episode locations; v2 acceptance
is under Azure6's `v2/`; current smoke output is `v2/runs-v2-d82f9a7/`. Collections drained cleanly (2,551 Azure6 and 4,000
Azure2 rows/episodes preserved); publishing/row export stayed alive. Frozen runtime
and R4c model remain separate from main-based #38. The original six-hour deadlines
remain approximately 02:52 and 02:59 UTC; fixes do not reset the budget.

Evaluation seed2026111401 families and descendants, seed131 and the squeeze suite
remain excluded from training; generated native-acceptance seeds2026111401–1404
are also excluded. Cross-stream dashboard/traffic coordination is [#44](https://github.com/maxschireson/Single-Dummy-Bridge/issues/44).

## Evidence and its limits

The source snapshot is research/rollout-loop-20261113 at c006d22a3a0d81dd608085c6b9c8852ad8e863e5; performance work is at 3d353dfbebece7b8dc5951799ddf763d64e407a5. Both contain work newer than main's Gen 7 documentation. A branch snapshot is not evidence that a particular box deployed it. Source changes should follow the repository contribution workflow; integration into an active Stu runtime must be coordinated with loop.

| Observation | Evidence | Interpretation |
| --- | --- | --- |
| R4c has 1,742,850 parameters; four epochs on 6,366,157 examples; trainer reports 967 seconds | [R4c metrics][metrics] | The model itself is small. This is a particular round's subset, not the entire historical pool. |
| The before-score run performs one epoch at learning rate 1e-12; its epoch took 228 seconds | [Round script][round], [before log][before] | Replace it with evaluation. Approximately one of five training passes disappears for a four-epoch round; total pipeline savings are smaller. |
| Pool before the loop: about 30.4M rows. Reported row sizes: 756 bytes expanded on disk, 51 compressed, 465 resident in the trainer | [Loop report][loop] | Loading and copying data creates a memory/storage limit before model weights do. Ratios depend on schema and data mix. |
| BF16 padding plus fork batching: 26.0 to 9.4 CPU-seconds/board in six-board sandbox runs | [Performance report][perf] | Promising, not an Azure forecast: Intel Sapphire Rapids/AMX sandbox versus AMD Zen 4 Azure CPUs. |
| Existing arena rows: 17.6M; round 4 used 1.7M | [Loop report][loop] | Improve access and sampling of existing data before generating equivalent replacements. Check overlap and provenance first. |
| A collection job list ended and a box was idle for 54 minutes | [Loop report][loop] | A persistent fallback collection queue can recover useful capacity. |
| Roughly 2,048 BEN deals cost 5.3 reference-box hours; R3 absolute-score SE was about 0.09 IMP/board | [Loop report][loop] | A small per-round gain is too small for a decisive gate of that size. Paired candidate differences need their own variance estimate. |

Reported numbers above were inspected in code/logs; they were not independently rerun here. All speedups below are hypotheses unless explicitly identified as measured evidence.

## Reviewable implementation plan

IDs remain stable so approval can name a small subset.

| ID | Priority and suggested owner | Proposed deliverable | Acceptance condition |
| --- | --- | --- | --- |
| P01 | Now; Codex after loop approval | Replace the artificial before-training epoch with an evaluation-only path, reusing the existing scorer where possible | Same starting weights, vocabulary mapping, validation rows, blank-ID scores, and required before/after metrics; no optimizer updates; no training-set scan just to score the baseline; timed comparison |
| P02 | Now; perf implementation, loop integration | Measure existing BF16 padding, fork batching, feature construction and legal-suit decoding on Azure | Fixed actor/data/configuration, repeated controls, per-change and combined results; completed boards/hour, CPU, RSS growth and failures; numerical/card comparisons interpreted against baseline nondeterminism |
| P03 | Now; Codex after scope agreement | Reuse completed local row chunks; replace repeated history rebuilds and per-round merged copies with a dataset manifest | Each episode/feature-version conversion occurs once; same selected rows and sampling weights; bounded transient memory; identical family exclusion checks; resumable construction |
| P04 | Now; loop/operator | Persistent default collection work plus resource reservations | Normal queue exhaustion returns to the approved collection recipe; no second owner/duplicate worker; alerts on idle capacity, failed publication and low disk; no automatic restart of quarantined failures |
| P05 | Next; Codex after loop approval | Stream training and evaluation through bounded caches and incremental metrics | Large input does not make RSS grow linearly with the entire dataset; deterministic sampling and replay mix; loss/gradient parity on fixed batches; held-out scores and learning curve compared at equal updates |
| P06 | Experiment; loop | Compare continued training plus controlled replay with the existing R1-initialized recipe | Same new-data cutoff, fixed held-out families, comparable compute; track forgetting, calibration and full-bot regression; choose by useful gain per hour |
| P07 | Experiment; loop with data-mix work owner | Compare fork-rich arena data, stronger-bot self-play and current Stu self-play at equal collection cost | Stable bot-only source mixtures; unique families/positions and duplicated prefixes reported; raw row count never presented as independent sample count |
| P08 | Mac arrival; Codex/perf after allocation | Single-Mac GPU backend and batch-size benchmark; then local shared inference service | Feature/loss/output/export parity, stable memory, measured end-to-end train and board throughput; CPU fallback threshold measured; no assumption that existing CPU BF16 uses Metal |
| P09 | Workflow; loop/operator | Tiered validation and reproducible Azure BEN jobs | Separate collection adoption from release claims; immutable actor manifests, paired deals, blind opponent mode, independent release holdout; results exported before deallocation |
| P10 | Research; loop | Model-size/data-size study, followed by distillation if useful | Compare approximately 1.7M, 7M, then 25–30M parameters on identical splits; include inference cost and full-bot gain; scale further only when the previous step earns its cost |

Suggested first approval: **P01**, a narrow first version of **P03**, and a bounded **P02** Azure measurement led by perf. P04 can be handled by the existing operator. P05 and P08 are the next substantial engineering work. P06, P07 and P10 change the learning recipe and should remain explicit experiments.

No item is currently marked approved. Record the decision in the PR or coordination board using: action ID; approve/defer/reject; agreed scope; owner; resource budget; acceptance criteria; deployment scope if any. A completed implementation can be reviewed without changing collectors.

## Collection: improve learning per machine-hour

The loop report measures the following raw rates:

| Source | Rows per CPU-second | Sampling basis |
| --- | ---: | --- |
| Stu self-play | 2.1 | 150 records |
| Gen 8 self-play | 3.3 | 150 records |
| Arena with audit/gap forks | 9.0 | 250 records |

These are CPU-time measurements, not whole-machine throughput forecasts. Fork rows share a deal and often much of a trajectory. The apparent 4.3x row-rate advantage over Stu is not a measured 4.3x learning advantage. Porting arena-style forks into the loop runner is additional work, not an existing flag assumed available.

For P07, keep a fixed evaluation population and compare source mixtures at equal collection CPU budget, with an additional accounting of preparation/training cost. Report unique deal families, root/fork positions, duplicate prefixes, teacher identity, stage, and rated-card coverage. Preserve meaningful alternative continuations while avoiding accidental copies of the same observations.

Continue using bot-only training. Include current Stu data to represent its own state distribution and stronger-bot data to teach behavior it has not acquired. Do not replace the approved fleet mix merely because the raw-rate table favors one source.

Do not begin by cutting rollout budgets. Existing label experiments found that fewer layouts weakened labels without proportional time savings, and the tested comparison was near saturation at 128 layouts. The measured label ablation reuses trajectories from the larger-budget actor; it does not establish the behavior of a newly collected low-budget population. Selective additional computation on consequential uncertain decisions is a later experiment.

For P02, preserve the difference between semantic and bitwise equivalence. Fork batching gives forks their own random stream, changing trajectories relative to the old shared-stream implementation. BF16 and matrix shape changes may change numerical results. Use new run identities where behavior changes; preserve frozen records. Keep worker recycling until longer runs demonstrate bounded memory.

## Preparation and training: avoid repeated work and resident datasets

The intended path is completed episodes to immutable row chunks to a versioned manifest to prefetched minibatches. A manifest references data and mixture weights rather than copying the entire pool.

P03/P05 should provide:

- Content and schema/version keys for episode conversion. Model-derived features also key on the relevant scorer/model hash.
- Stable exclusion by canonical deal family across feeds, rooms, forks and reprocessing. Existing all-train calls plus separate validation files need an explicit global disjointness check; their presence alone does not establish a leak.
- Compressed storage/transfer and a bounded decoded training cache. Start with chunk shuffle plus within-chunk shuffle rather than many random reads from compressed archives.
- Fixed mixture weights and exposure accounting. A streaming loader must not silently favor small files, fast producers, recent data or the node with more rows.
- A resumable checkpoint containing optimizer/scheduler state, sampling/RNG state, dataset manifest and model identity.
- Incremental validation aggregates, retaining small per-family summaries for uncertainty rather than every logit.

The current trainer has useful memory mapping and bit packing, but subsequently allocates resident packed/copied arrays for the dataset. Its evaluator accumulates and concatenates predictions. It is not yet bounded-memory training. The existing merge utility streams arrays while writing, but still creates another full expanded dataset. [Trainer][trainer], [merge utility][merge]

Additional training improvements to measure:

1. Accumulate loss summaries on the device and read them periodically. The current conversion of each batch's losses to Python floats synchronizes execution. JAX's [asynchronous dispatch documentation](https://docs.jax.dev/en/latest/async_dispatch.html) explains this behavior.
2. Benchmark batch sizes and CPU thread counts independently. Increasing worker count while each numerical library also uses many threads can oversubscribe the machine.
3. Prefetch minibatches and avoid shape-triggered recompilation. Report compilation separately from steady-state work.
4. Keep high-volume inference policy-only where appropriate; training retains the auxiliary heads it needs.
5. Compare P06 against the existing recipe before adopting it. Current later rounds default to R1 initialization, not the preceding accepted net.
6. Evaluate soft policy targets from recorded action probabilities as a separate learning experiment. Keep unrated actions masked; do not turn missing labels into poor-action labels.

## Validation and release testing

| Stage | Frequency | What it decides |
| --- | --- | --- |
| Offline validation | Every candidate/checkpoint under comparison | Numerical correctness, loss/regret, calibration, forgetting, legal-card behavior, rated-card coverage and inference cost |
| Cheap playing checks | Each proposed collection update | Net-only comparisons plus a modest full-bot regression sample and critical bridge cases; sufficient to consider collection adoption, not to claim a tiny strength gain |
| Blind BEN evaluation | Major release, mechanism change or material accumulated improvement | Actual played cardplay strength at pinned settings and, separately, strength at a comparable time budget |
| End-to-end evaluation | When bidding changes or periodically for releases | Native-auction performance, kept separate from common-auction cardplay |

The current offline regret metric excludes unrated chosen cards; report that coverage beside regret so apparent progress cannot come from choosing unscored actions. Cluster uncertainty by canonical deal family across rooms/forks, not by individual correlated rows.

Keep one reusable development comparison suite and a separate untouched release population. Repeated comparisons influence development even if those boards never enter gradient training. Keep blind opponent identities for the official gate. Baseline results can be reused only when their actor, conditions and scoring match exactly.

At fixed variance, sample size for a fixed-confidence effect estimate scales approximately as 1/effect². R3's absolute-score SE of about 0.09 at 2,048 deals corresponds to a roughly ±0.18 95% interval, not ±0.10. Paired new-minus-old results may have lower variance; measure that variance rather than borrowing the absolute-score SE. Choose the minimum worthwhile effect and stopping rule before looking. Use a fixed endpoint or valid sequential procedure for a formal claim.

The testing fraction can shrink as learning cycles grow if evaluation targets a fixed practical effect or accumulated gains every few releases. It need not shrink if every progressively smaller increment must be proved independently.

For BEN efficiency, shard independent deals across Azure boxes, preserve completed baseline comparisons, and measure how often requests repeat before candidate trajectories diverge. A request cache must include all behavior-affecting inputs, configuration, history and randomness/state; do not assume the visible request alone makes BEN deterministic. Start with a read-only overlap measurement coordinated with perf.

## Four-Mac workflow and Azure bursts

Planning uses the user's stated per-machine configuration: 18 CPU cores, 20 GPU cores, 64 GB unified memory. This is four GPU devices with 80 GPU cores total, not 80 independent GPUs. Confirm the delivered model, OS, network and port topology before setting throughput expectations.

| Phase | Four Macs | Azure |
| --- | --- | --- |
| Accumulation | All collect; incremental preparation runs alongside | Usually deallocated |
| Small training round | One trains, three continue collection | Usually deallocated |
| Recipe/size comparison | Independent candidates on available Macs | Usually deallocated |
| Large training round | Borrow two or four nodes if measured scaling justifies lost collection | Optional overflow only when justified |
| Release evaluation | Continue collection or resume it immediately after training | Independent BEN shards |
| Adoption | New jobs use the approved version; in-flight boards finish under their original identity | Export and verify results, then deallocate |

Start with one-node correctness and throughput. Current inference is NumPy or PyTorch CPU BF16, and training is JAX/Optax. Neither the CUDA ecosystem nor CPU oneDNN tuning automatically transfers to Apple GPU execution. Compare the existing JAX model on [Apple's Metal backend](https://developer.apple.com/metal/jax/) with an MLX implementation if warranted. Avoid maintaining two divergent feature definitions.

For local inference, board workers should batch requests through one service per Mac, with model-version routing, bounded waiting, cancellation and backpressure. Measure the batch/latency threshold where GPU inference beats CPU; small calls may stay on CPU. CPU workers and GPU training share bandwidth, memory and power, so scheduling must use measured combined throughput.

For distributed training, first use [data parallelism](https://ml-explore.github.io/mlx/build/html/examples/data_parallelism.html): replicate the small model, process different data and combine gradients. Compare time to a target held-out score as well as examples/second; a larger global batch changes optimization. Independent experiments may be more useful than synchronizing a small model.

The aggregate 256 GB is usable through explicit dataset or model partitioning, not automatic shared RAM. MLX's [JACCL documentation](https://ml-explore.github.io/mlx/build/html/usage/distributed.html) describes Thunderbolt RDMA and a fully connected topology: four nodes require six direct connections. Verify installed-version requirements. Independent jobs need much less interconnect bandwidth and can start before tightly coupled distributed training is ready.

Use Azure's measured cost per completed evaluation, not its CPU count alone. Preserve artifacts/checkpoints and arrange deallocation after successful publication, with resumable handling of interruption. [Azure billing states](https://learn.microsoft.com/en-us/azure/virtual-machines/states-billing) distinguish deallocated VMs from stopped-but-allocated VMs; disks and some network resources can still incur charges. No Azure provisioning or resize is authorized by this recommendation document alone.

## Doubling cycles and capacity

Define each doubling against a versioned training population with source mix and exposure accounting. The full historical pool, the newest Stu data and the sampled round are different denominators. Raw rows are not a universal measure of effective data; do not extrapolate the reported Gen 7 scaling exponent as a proven law for every Stu mixture/model.

If the selected pool is N rows and comparable new collection adds R rows/day, collecting enough for the next doubling takes approximately N/R days. For illustration only, at 10M usable new rows/day, growing 30M to 60M, then 120M, then 240M requires about 3, 6 and 12 collection days respectively. Preparation and training add work, some of which can overlap. This is not a Mac throughput forecast.

A snapshot freezes the current training cutoff while collectors keep producing. Intermediate checkpoints need not trigger a new full BEN gate. Keep the accepted actor serving collection until the next candidate meets the agreed adoption criteria.

### Dataset memory

Extrapolations from the loop report's approximate row sizes, in decimal GB:

| Rows | Resident dataset at 465 bytes/row | Compressed rows at 51 bytes/row | Expanded disk rows at 756 bytes/row |
| --- | ---: | ---: | ---: |
| 30M | 14.0 | 1.5 | 22.7 |
| 60M | 27.9 | 3.1 | 45.4 |
| 120M | 55.8 | 6.1 | 90.7 |
| 240M | 111.6 | 12.2 | 181.4 |
| 480M | 223.2 | 24.5 | 362.9 |
| 1B | 465.0 | 51.0 | 756.0 |

Exclude raw episodes, filesystem/metadata overhead, copies, caches, OS, workers, model activations and framework workspaces from those estimates. Compression is data-dependent. A 120M-row fully loaded dataset is uncomfortable on 64 GB; streaming can process a billion-row population with bounded memory. That makes time and I/O the constraints, not a requirement to hold every row at once.

### Model memory and when to buy larger boxes

A simple FP32 Adam estimate is 16 bytes/parameter for parameters, gradients and two optimizer moments, before activations, temporary buffers and implementation overhead.

| Parameters | Basic training state |
| --- | ---: |
| 1.74M | 28 MB |
| 7M | 112 MB |
| 30M | 480 MB |
| 100M | 1.6 GB |
| 1B | 16 GB |

Thus 7–100M-parameter candidates are plausible from a 64 GB capacity perspective. This is not a guarantee of useful learning, speed or maximum batch size. A billion-parameter model can be a compute/inference problem well before it is a memory problem.

Test a model-size by data-size grid. At fixed data, larger models improving training and held-out scores suggest useful capacity; training-only improvement suggests overfitting; neither improving suggests optimization, representation or label limits. At fixed model, a continuing held-out gain from more independent data supports collection. A small training/validation gap alone does not establish capacity saturation.

Since every rollout repeatedly invokes the net, compare full-bot strength at equal time. Consider a larger teacher distilled into a smaller rollout net if capacity helps training but makes collection expensive.

Before model sharding or more RAM, try bounded data streaming, smaller microbatches, gradient accumulation and activation checkpointing where activation memory matters. On unified-memory Macs, CPU offload is not a separate physical RAM pool. Partition optimizer/model state only when the working set itself needs it and the backend supports it.

Consider 256/512 GB nodes when a demonstrably useful model's active working set exceeds practical per-node capacity despite these changes, or measured throughput/cost favors them. Dataset size by itself is not that trigger.

## Execution and review record

The proposed first work is small and reviewable. After approval, implement only the named scope on isolated source branches, run the relevant acceptance checks, and publish results/PRs. Coordinate with perf to avoid duplicating its patches and with loop before consuming box resources or transitioning collectors. Frozen model/runtime identities and quarantined failures remain governed by their existing rules.

Review status at publication: **awaiting loop**. No boxes were restarted, resized or provisioned; no actor, training recipe or running job changed during this review.

[loop]: https://github.com/maxschireson/Single-Dummy-Bridge/blob/c006d22a3a0d81dd608085c6b9c8852ad8e863e5/training/rollout-loop-20261113/README.md
[round]: https://github.com/maxschireson/Single-Dummy-Bridge/blob/c006d22a3a0d81dd608085c6b9c8852ad8e863e5/training/rollout-loop-20261113/round2.sh
[trainer]: https://github.com/maxschireson/Single-Dummy-Bridge/blob/c006d22a3a0d81dd608085c6b9c8852ad8e863e5/scripts/train_rollout_net.py
[merge]: https://github.com/maxschireson/Single-Dummy-Bridge/blob/c006d22a3a0d81dd608085c6b9c8852ad8e863e5/training/rollout-net-v2-20261113/merge_sets.py
[perf]: https://github.com/maxschireson/Single-Dummy-Bridge/blob/3d353dfbebece7b8dc5951799ddf763d64e407a5/training/perf-20261114/README.md
[metrics]: https://github.com/maxschireson/Single-Dummy-Bridge/blob/2f969fe919159f53e536d8c8dfbc8746b1ec63fa/train-r4c/metrics.json
[before]: https://github.com/maxschireson/Single-Dummy-Bridge/blob/2f969fe919159f53e536d8c8dfbc8746b1ec63fa/train-r4c/before.log
