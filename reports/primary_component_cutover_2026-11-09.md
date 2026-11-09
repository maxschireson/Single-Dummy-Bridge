# Primary component diagnosis after stopping v4 self-play

User instruction: stop 4–4; use 4b and 4p against one another, 4, and earlier versions to diagnose the regression.

The primary original phase `/workspace/arena-v4/g0004` drained at 2,228 completed hands. Its STOP and the old watchdog STOP remain permanent. Preserve all episodes, receipts, frozen auctions, models and training state. Do not resume its allocation. Other environments are separate writers: this cutover cannot stop their processes; their operators must apply the same user instruction independently. In particular the older recovered six-bot mix included 4–4 and must not be resumed unchanged.

New run: `/workspace/arena-v4/components-primary`; identity `4f43d6f3f234b9e561671f6958bbe2785e8896181791632ee4b1569a5ab062e0`.

Only the original phase's 22,772 unplayed families are admitted. Frozen deals, board IDs and v4 auctions are retained. This completes the original 25,000 hand-set allocation across two separately identified protocols; it does not create 25,000 new diagnostic observations. No legacy data is pooled. Bulk DD for unused deals stays paused.

4p (internal alias P) is Gen3 belief + Gen4 policy. 4b (Q) is Gen4 belief + Gen3 policy. Both inherit the Gen3 native bidder, although this phase uses common frozen v4 auctions to isolate cardplay. There are no new native-bidder conditions in this phase; the old phase's common/native results remain available separately.

Each shuffled 20-hand block contains P3 and Q3 four times each; 4P, 4Q, PQ and 43 twice each; P2, Q2, P1 and Q1 once each. No self-play. Each hand plays two swapped partnerships. Search remains 32 samples, near-tie 0.125, zero exploration; original random local policy audits remain enabled. Outcome-independent ordering and allocation are frozen. Comparisons are exploratory; no automatic promotion or training.

Four independent spawned workers run with BLAS/OpenMP one thread each. Healthy peers survive recognized worker process losses. The single parent holds production locks and writes immutable records. Launcher `ops/gen4_component_primary.py`; parent metadata `process.json`, progress `state.json`, activity `heartbeat.json`, diagnostics and failures under the run. Runtime hashes are pinned: never edit a running manifest or its pinned code.

`ops/watch_primary_components.py` verifies process identity, locks, preserved failures and runtime hashes, replay-audits before restart, and limits retries without progress to three. STOP drains collection; WATCHDOG_STOP stops the watcher. Unknown failures remain blocked for inspection.

Publication owns only `arena-primary-components-feed`, with minute score/replay updates and complete episode backups in `recovery/`. Never write another environment's feed. The shared Pages report includes the new `primarycomponents` stream; existing four sources and historical replay identities remain intact. Direct link: https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=primarycomponents

Training: `ops/export_training_feed.py` supports this protocol, derives the unchanged canonical family split, and extracts unique root/audit trajectories. Policy labels remain audited local action-minus-reference IMPs, never full-match outcomes. The final old-phase increment is exported first, then `/workspace/training-export/component-publisher` continues the shared training branch, preserving all prior increment identities and deduplicating families. Exact raw episodes also remain in the diagnostic feed.

Validation: replay audit of completed real DDS records; actual training export smoke check (belief and audited policy tensors); existing training test; 11 reporting checks covering variance, Student-t intervals, aliases/orientation, exact replay totals, cutoffs and deduplication. First completed diagnostic records include all ten scheduled matchups, without any self-play.

Resume only with free writer/supervisor locks, no STOP and no unreviewed failures:

    source /workspace/environment-setup/arena-env.sh
    python ops/gen4_component_primary.py audit --run /workspace/arena-v4/components-primary
    python -u ops/gen4_component_primary.py run --run /workspace/arena-v4/components-primary --workers 4

A destroyed environment requires restoring models/assets from the verified original capsule and restoring the exact new manifest, corpus, schedule and completed episodes from its feed. Do not reinitialize and describe it as an exact continuation.
