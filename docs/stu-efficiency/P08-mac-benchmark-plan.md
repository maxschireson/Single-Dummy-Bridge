# P08: single-Mac benchmark and parity plan

Status: plan only, under [loop's PR #35 approval](https://github.com/maxschireson/Single-Dummy-Bridge/pull/35#issuecomment-6883488008). Owners: proposer and perf. No purchases, installations, backend port or benchmark execution authorized by this plan. Loop must book a machine and execution budget before it runs.

## Decision

Choose whether the first Mac should train Stu with the existing JAX implementation on Metal, use an MLX port, or remain primarily a self-play/data worker while training stays on the current backend. Measure end-to-end time to an equally validated checkpoint, not nominal GPU cores or a matrix-multiply peak. Do not assume inter-machine memory pooling, distributed training speedup, a particular delivered SKU, or support for every current trainer operation.

On arrival record actual model/chip, CPU/GPU core counts, usable unified memory, macOS, storage and network. Freeze repository commit, model/input hashes, Python and dependency versions. Check the current [Apple JAX Metal compatibility guidance](https://developer.apple.com/metal/jax/) before selecting a version pair: it documents a Metal plugin and a compatibility matrix, not proof that Stu works. Keep each backend in its own environment after installation is authorized. Capture the selected device and any unsupported operation or CPU fallback.

## Workloads and correctness gates

Use one pinned bot-only fixture spanning opening lead, early/late play, multiple bot identities, blank IDs, legal-card ties, partly rated candidate gaps and missing labels. Include current model heads only; do not change loss weights, architecture, initialization, replay mix, augmentation or optimizer to make a backend faster. Keep seed 131 and squeeze positions out of all training. Pin train/validation family membership and test it for disjointness. Evaluation-only fixtures stay evaluation-only.

Use the existing CPU JAX trainer as the reference. Export exact input arrays, minibatch order, parameters and any random masks; equal RNG seeds across frameworks alone do not imply equal samples.

| Check | Proposed acceptance before throughput comparison |
| --- | --- |
| Features and labels | Shapes, dtype interpretation, seat/card ordering, bot-vocabulary/alias mapping and masks exactly match; hidden hands remain labels only |
| Forward FP32 | Compare all finite logits and head outputs with `atol=1e-5, rtol=1e-4`; masked legal sets exactly match; report max/mean error |
| Decisions | Exact card agreement except logged near ties within twice the observed logit error; no unexplained disagreement and no illegal card |
| Loss and gradient | Compare each loss component and gradient against reference; proposed FP32 `atol=1e-5, rtol=1e-4`; report outliers rather than silently relaxing tolerance |
| Optimizer | One identical clipped AdamW update and state, including bias correction, epsilon, decay and frozen vectors; proposed same FP32 tolerance, then a short fixed-batch trajectory |
| Epoch and selection | Before/after tables by bot and phase, forgetting guard, checkpoint selection and blank-ID metrics; metrics agree to four decimals on the parity fixture |
| Export and resume | NPZ schema/vocabulary intact; existing runtime can load it; exported prediction parity; resumed next update matches uninterrupted update within tolerance |

These are proposed gates for loop/perf to accept, not measured results. If a tolerance fails, diagnose reduction order, precision or a semantic mismatch first. Mixed precision is a separate candidate after FP32 parity, with its own numerical-error and held-out-quality report; never silently compare a reduced-precision run to an FP32 run as if the recipe were unchanged. Do not promise bitwise parity across hardware.

## Timing matrix

Start with the current adopted width and batch 256, then the approved wider model only if available. Run identical minibatches and effective batch size across backends. Sweep microbatch 64/128/256/512 for capacity and throughput only; if accumulation is needed, preserve effective batch size and number of optimizer steps. Report it explicitly.

For each valid configuration, separate cold compilation, warm forward pass, warm train step, data preparation/load, full validation, checkpoint export and complete epoch time. Warm up to stable compiled shapes, then time at least 200 steps in three repeats with actual completion synchronization. Use JAX readiness barriers and explicitly evaluated MLX outputs/state; [MLX documents lazy evaluation](https://ml-explore.github.io/mlx/build/html/usage/lazy_evaluation.html), so dispatch timing alone is insufficient. Force parameters, optimizer state and metrics to complete at timing boundaries. Include host preprocessing and device transfer in a second, end-to-end timing.

Record median and spread, examples/s, seconds/epoch, RSS, backend allocated/cache memory, system memory pressure and swap growth. Unified allocations can overlap RSS: do not add counters together blindly. Stop a configuration on sustained swap growth or an agreed memory ceiling; record the failure rather than extrapolating an OOM run. Use an operator-agreed reserve for macOS and other jobs.

After correctness and short timings pass, propose a bounded full-epoch comparison on exactly the same frozen shard set. Compare wall time and held-out quality after equal data exposure. Record self-play throughput separately on that machine; propose a second bounded trial with one training job plus controlled self-play only after exclusive baselines establish the contention cost. This determines whether dedicating one Studio to training beats alternating all machines.

## Deliverables and decision rule

Publish the pinned manifest, commands/version lock, parity JSON, timing CSV, memory traces, failure logs and model hashes to an agreed transfer location; publish source changes through an isolated PR. Do not upload private machine credentials or machine-wide environment dumps.

| Candidate | Device verified | Parity | Cold compile | Warm steps/s | Full epoch | Validation | Peak memory / swap | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| JAX CPU reference | pending | reference | pending | pending | pending | pending | pending | baseline |
| JAX Metal FP32 | pending | pending | pending | pending | pending | pending | pending | pending |
| MLX FP32 port | pending | pending | pending | pending | pending | pending | pending | pending |

Prefer the backend with a material repeatable end-to-end gain at equal quality, enough memory headroom and acceptable maintenance cost. If Metal is unsupported or neither candidate wins, retain the existing training backend and use Studios for measured self-play/preparation work. Four-machine scheduling, network transfer and distributed-memory experiments are later decisions based on this single-node result. Any deployment stays with loop's explicit integration scope.
