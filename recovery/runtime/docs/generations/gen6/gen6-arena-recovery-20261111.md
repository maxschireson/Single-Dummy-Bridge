# Gen6 primary arena: recovery and shared results

Max authorized the Gen6 transition on 11 November 2026. The latest correction
assigns the **15% BEN16 share to Gen6 medium (256)**. This supersedes the
earlier fast-versus-BEN screenshot row. The authoritative plan is
`configs/round6-codex.json`; `configs/gen6-active-mix.json` is the compact
coordination record for other collectors.

| Match | Share |
| --- | ---: |
| Gen6 fast vs Gen5 (the frozen 5RZ32 actor) | 40% |
| Gen6 fast vs Gen6 medium | 15% |
| Gen6 medium vs BEN16 | 15% |
| Gen6 fast vs Gen3 | 10% |
| Gen6 fast vs Gen2 | 10% |
| Gen6 fast vs Gen1 | 10% |

Both Gen6 actors use the same new bidder, lead-belief net, hand-fit scorer and
Gen5 policy. Fast uses 32 samples before full compatible-layout listing starts
at trick 7. Medium uses 256 before listing starts at trick 6. Both retain the
launch package's late-list solve ceiling of 256. The automatic 64-sample middle
phase is disabled. The policy only breaks PIMC maximum ties. Common auctions
use the Gen6 bidder for all four seats; native auctions use each partnership's
bidder. Both conditions and swapped partnerships are retained.

| Artifact | SHA256 |
| --- | --- |
| Gen6 bidder | `5b7ea2558581df39d6517f86f459000ed1ef3a2fb1e8120563c70b343b95e7ff` |
| Lead belief | `72fc7c3ef1e6e8299c63a7d6b7b1b7e165bacca54ba5efac04b8a86a7e9e6291` |
| Hand-fit scorer | `56e6444079d1451ada7730e7d4fa5764caee766102af0386831ed73c42245e73` |
| Retained policy | `03e70a6f6021c8bed471dc9de53f462b0e991320ff4ad7734bcc20f54c5aff18` |

## Frozen source and records

- Source checkout: `/workspace/Single-Dummy-Bridge-gen6`.
- Source branch: `codex/launch-gen6-20261111`.
- Frozen launch source commit: `23e2590` (full value in `environment.json`).
- Engine baseline: `717cd87d57b61d7f7d3a41fa48228d849c9544bf`.
- Run: `/workspace/work/gen6-codex`.
- Manifest: `168ad0fbbb39c4f54d86a1efc396da50244abc13ad9fd56eef9a14a414cd8dea`.
- Target: 7,318 unplayed families from the drained source run.
- Publication checkout: `/workspace/work/gen6-codex-publication`.
- Publication branch: `arena-gen6-codex-feed`.
- Other Codex collector: `arena-gen6-medium-ben-feed`; its earlier phase is
  archived on `arena-gen6-independent-feed`. Compatible earlier games remain
  included; accidental fast-versus-BEN games are filtered from every report.
- ChatGPT producer: `arena-gen6-chatgpt-feed`; its producer controls its own
  lifecycle. Its compatible published results are combined with the Codex feeds.
- Dashboard: https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=latest

The previous run `/workspace/work/gen5rz-ben` drained cleanly at **8,372**
complete paired records. Its source remains unchanged at
`/workspace/Single-Dummy-Bridge-5rz-ben` (`4969fc2`). Its final archive stays on
`arena-gen5rz-ben-feed`, tagged `gen5rz-before-gen6-20261111` at
`a559ccb59e9d3ff09d8c759c016534b4efcef254`. Keep its STOP, WATCHDOG_STOP and
PUBLISH_STOP markers.
The first, empty Gen6 preparation with fast versus BEN is preserved separately
at `/workspace/work/gen6-codex-staging-fast-ben-20261111`; it produced no games.

## Resume on this host

Use `/workspace/work/ben-venv/bin/python` for the supervisor, collectors and
publisher. System Python lacks the arena's TensorFlow dependencies. The
watchdog holds a singleton lock and collectors hold a separate single-writer
lock; never start another collector against the same run while its writer is
alive.

From the source checkout:

```sh
BRIDGE_ARENA_PYTHON=/workspace/work/ben-venv/bin/python \
  /workspace/work/ben-venv/bin/python -u ops/watch_gen5.py \
  --run /workspace/work/gen6-codex \
  --publication /workspace/work/gen6-codex-publication
```

The watchdog restores the collector and publisher, checks BEN readiness,
rotates the recomputable DDS cache after draining, and stops collection if disk
space is low. It pins subprocesses to the same Python executable. Verify
`watchdog-status.json`, `heartbeat.json`, `state.json` and
`publisher-status.json`; process JSON files record PIDs for inspection.
Diagnose any preserved failure or STOP reason before restarting.

To drain, write STOP and WATCHDOG_STOP and wait for the writer and watchdog
locks to become free. Let in-flight deals finish. Stop publication with
PUBLISH_STOP after the final snapshot. Preserve every completed episode and
receipt. Never edit the manifest, pinned runtime, model files or completed
records to make a resume pass.

BEN is the neural-bidding, 16-lead-sample, 16-play-sample engine on
localhost:8087. Its source is `/workspace/work/ben-next-round`, process record
`/workspace/work/round5/ben-process.json`. `ben-recovery.json` pins its source
revision, config, bidder hash, command and environment.

## Restore after losing this workspace

Clone `arena-gen6-codex-feed` and preserve its `recovery/` directory as the run.
It contains the original manifest, corpus, source indices, all clean compressed
episodes and receipts, all actor artifacts and assets, requirements, preflight
reports, environment and launch metadata, and this handoff. The frozen runtime
is under `recovery/runtime/`; alternatively check out the full source commit
from `environment.json`. Restore the Python dependencies and pinned BEN source
and models before starting the watchdog. Use `BRIDGE_ARENA_PYTHON` and the
watchdog's `--ben-dir` and `--ben-state` arguments for different local paths.
The compiled native library is archived for this Linux runtime; rebuild it
only when intentionally preparing a new runtime, not to change this run's
pinned source identity.

DDS SQLite caches are memoized solver answers and can be regenerated. They are
not training labels. Retired caches were discarded to free space for Gen6;
raw episodes, receipts, model snapshots and manifests were preserved.

## Producer and aggregation contract

Publish each producer's single-writer run on its own `arena-gen6-*-feed` branch.
Keep `arena/manifest.json`, `arena/data.json`, replay catalogs and indexes, and
the full `recovery/` archive. Never share a publication checkout between hosts.
New runs require distinct immutable manifest identities. Keep the canonical
actor IDs `6-32`, `6-256`, `5RZ32`, `3`, `2`, `1`, `ben`, or publish enough actor
metadata to establish the same configurations before pooling results.

The headline view combines compatible actors and common-bidder conditions,
deduplicating by canonical deal family and matchup independently of outcome.
Keep common play, native total and paired native-minus-common auction effects
separate. Different configurations and earlier fast-versus-BEN records remain
available in provenance/history and training archives. Dashboard drill-downs
must retain exact publication revisions and displayed snapshot cutoffs.

## Accidental fast-versus-BEN archive

The 13 accidental paired records (11 from the early Codex run and 2 from the
ChatGPT run) are preserved separately on `archive/gen6-fast-ben-20261111`,
commit `802f69ad6e1416a5a7200d5e6c29f8beca2a8275`. The archive contains original manifests,
compressed episodes and receipts, with compressed SHA256 and legal replay
checks passed. They are excluded from all dashboard scores, rates and timing.
