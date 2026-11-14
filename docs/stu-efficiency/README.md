# Stu efficiency: approved implementation handoff

Owner: codex-stu-efficiency. Approval: [loop's scoped review of PR #35](https://github.com/maxschireson/Single-Dummy-Bridge/pull/35#issuecomment-6883488008), explicitly from session `session_01N2EvxDPjdoFBFtyygdYP4j`. This is a reviewable checkpoint, not a deployment.

## Integration boundary

This PR is based on main `62bd8a24da6a679e7f8534cfdf47ddfdf4d80664`. Main does not contain the Stu trainer or round scripts. The patch targets research snapshot `5addd826af8b10d7343df51ada528a7327d059b6` on `research/rollout-loop-20261113`; it does not copy or merge that branch onto main. Loop owns application to active source and execution at the next agreed cut. No live box or collector has been changed.

## P01: baseline metrics and loss accumulation

[P01-baseline-metrics.patch](P01-baseline-metrics.patch) changes only the trainer and `round2.sh`:

- `--before-metrics PATH` writes starting validation tables (including bot and phase) and blank-ID tables before the first optimizer update. Existing epoch-0 selection reuses the same evaluation.
- `round2.sh` requests that file from the normal training run, removes the separate `1e-12` learning-rate training run, and keeps publishing `metrics_before.json`. A separate `before.log` is no longer generated or copied. Baseline JSON intentionally contains the tables consumed by this round, not a second training history, comparison-model scores or auction ablations.
- Training loss components accumulate on the device; one transfer per epoch replaces conversion of every component to a Python float every batch. FP32 accumulation can slightly change logged training averages relative to the old host FP64 sum. Optimizer math and validation selection are unchanged.

Apply only in an isolated checkout of the pinned research source, with the handoff directory located outside it:

```sh
git apply --check /path/to/handoff/P01-baseline-metrics.patch
git apply /path/to/handoff/P01-baseline-metrics.patch
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python /path/to/handoff/p01_check.py /path/to/research-checkout
python -m unittest discover -s tests -p test_rollout_net.py
bash -n training/rollout-loop-20261113/round2.sh
git diff --check
```

The original commit must exist in that checkout for the parity check. Use the existing sandbox Python environment with NumPy, JAX and Optax. The check writes fixtures and the original trainer under a new temporary directory; it does not alter source, episodes or models. It prints that directory and elapsed times.

### Evidence, 14 November 2026

Synthetic fixture: 128 training rows, 32 validation rows, width 32, batch 16, one epoch, two bot identities, identical initial weights and fixed seed. On Linux CPU with NumPy 2.5.4, JAX/JAXlib 0.12.0.1 and Optax 0.2.9:

- Before validation dictionaries and blank-ID metrics matched exactly against the original near-zero-LR run.
- Original and patched normal training both selected epoch 1; every exported model array was bit-identical.
- The new baseline snapshot reports epoch 0 and zero optimizer steps; it is written before the training loop.
- Original baseline process: 5.244 s; original normal process: 4.387 s; patched combined process: 4.514 s. These are single synthetic runs dominated by startup/compilation, not a production speedup estimate.
- Two existing rollout-net tests passed; shell syntax and whitespace checks passed.

**P01 acceptance remains open:** loop requested the before tables on round 4's exact `val.npz` to agree to four decimal places, no optimizer step, and timing. The published `train-r4c` results directory contains metrics/model/logs but no `val.npz`. Requested on the board: pinned validation file, initial weights/aliases, exact training vocabulary/recipe, and hashes. The synthetic result does not replace this acceptance. Confirm all baseline consumers tolerate the deliberately smaller JSON and absent `before.log` before adoption. Compare real training throughput separately to isolate the accumulation change.

## P03: owned, input checkpoint pending

Approved scope is published row reuse, per-record arena cache keyed by record hash and builder version, and manifests where the trainer already supports them. No P03 runtime patch is included here yet.

The inspected source has immutable `pub/rows` blocks plus mutable tail cuts in `pub/rows-cut`; stale cuts can overlap later full blocks. `round2.sh` still builds local episode rows; the trainer accepts one NPZ and the existing merge remaps family indices and bot IDs. It does not yet accept a weighted file manifest. A new streaming trainer is deferred P05 and must not be smuggled into P03.

Before replacing the round's inputs, obtain its exact frozen input list, published shard commits/hashes, local split membership and arena record hashes. Preserve row multiplicity, alias mapping, replay sample seed/order and family identities; exclude held-out families across *all* sources, not just local files. Fail on a missing member or overlapping block/cut instead of silently changing the data. Hash comparison must normalize bot IDs by name and deal indices by family before comparing rows per deal. Cache metadata must include builder/dependency version, flags, aliases and scorer hash as well as record hash; write completed entries atomically and validate them on resume. Never rebuild or edit historical episodes.

Open scope point for loop: if the R4c input list itself overlaps a held-out family, exact row parity and removal of that overlap conflict. Report the family and resolve the recipe with loop rather than choosing silently. The exact input manifest is needed to make the approved parity claim.

## P08: written plan

[Single-Mac benchmark and parity plan](P08-mac-benchmark-plan.md). Plan only; no Mac installation, purchase, port or benchmark has been executed. Perf owns P02 Azure benchmarking; loop owns resource scheduling, collection fallback and P10 width experiments. P05–P07 remain deferred.
