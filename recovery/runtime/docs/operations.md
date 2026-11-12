# Operations

Start with the [Gen6 recovery runbook](gen6-arena-recovery-20261111.md).
It records host-specific paths, manifests, hashes, BEN configuration, lock
discipline and restoration details. Paths under `/workspace/work/` describe
the original deployment host; they are not guaranteed to exist on your machine.

## Read before acting

1. Identify the producer and exact run manifest.
2. Inspect fresh heartbeat, watchdog, publisher and failure status.
3. Inspect the writer/supervisor locks and owning processes.
4. Confirm the source checkout, environment, actor hashes and publication branch.
5. Use that run's recovery instructions.

A `status: running` field in a committed report is a dated observation, not a
current health check. Moving `main` does not upgrade an existing collector.
Never pull new code into a frozen running checkout or rewrite a manifest to make
resume validation pass.

## Ownership boundaries

| Resource | Writer |
| --- | --- |
| Run directory and episodes | One collector for its immutable run |
| Producer feed | That producer's publisher, with a dedicated checkout |
| Aggregate dashboard | Dashboard publisher on `gh-pages` |
| Shared source | Reviewed development changes to `main` |

Preserve completed episodes, receipts, original actor IDs and model artifacts.
Drain in-flight work before a version transition. Diagnose STOP/failure reasons;
do not blindly remove markers. DDS SQLite caches are regenerable memoized answers,
not training labels.

## Restoring data

A producer feed carries `arena/manifest.json`, `arena/data.json`, replay catalogs
and `recovery/`. Read the manifest and environment first, restore the pinned
runtime and models, and verify checksums. A fresh source checkout plus a dashboard
JSON is not a complete run restoration.

The live site is on `gh-pages`; source assets also exist under `web/`.
Do not overwrite the deployed site from an older source copy. Pin feed revisions
and snapshot cutoffs for drill-down links.

## New cohorts

Prepare a new immutable actor/cohort identity for changed code, models, sample
budgets or bidder conditions. Use a separate run and publication checkout.
Run the relevant preflight, replay and record validation before publishing.
For BEN, name its effort profile; the active primary mix is medium Gen6 versus
BEN16. The historical fast-vs-BEN archive must stay excluded from headline metrics.
