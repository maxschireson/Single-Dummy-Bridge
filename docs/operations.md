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

## Independent cloud fast-only Gen7 capture (2026-11-11)

Source branch: `ops/gen7-fast-selfplay-cloud-20261111`. Feed: `arena-gen6-fast-selfplay-cloud-feed`, registered as `gen6cloudselfplay` in the dashboard source registry. This additional producer is 100% `6-32~6-32`, with 25,000 fresh seeded families, three workers, 50% tie audits and gap forks (2/band, 1.5 root CPU budget). Frozen models and capture engine are adopted from independent self-play feed revision `989d498484e4eff706342d4c767ebeba2c9154cb`.

Owner workspace: `/workspace/scratch/f846a051cf69`; run: `gen7-selfplay-run`; source: `bridge`; Python: `arena-venv/bin/python`. Manifest: `7ce4bf4a07ee08d6bd89fb25a927fc119ef79cd77217b0960f980b01a7dec0c9`. Gen3 is solely the existing tie-audit selector, never a scheduled opponent.

The owning host uses `ops/supervise_cloud_selfplay.py` for collection. STOP/WATCHDOG_STOP drain and prevent restart. Inspect fresh heartbeat, failures and writer locks before any recovery. Preflight: 28 tests; two real-model boards; root and tie-audit card sequences and bidding identical with gap capture on/off.

Git transport here has no push credentials. `ops/publish_cloud_capture.js` runs through the GitHub connector (AsyncFunction arguments `tools,text`) to export, upload new blobs, and update only the dedicated feed with an expected-head lease. It preserves full raw episodes, receipts, actor artifacts and runtime. Corpus is compressed into parts; `recovery/restore_corpus.py` reconstructs it and verifies SHA256. Scheduled publication is hourly; collectors continue between snapshots. The file contains this producer's paths and must only run on its owning host.
