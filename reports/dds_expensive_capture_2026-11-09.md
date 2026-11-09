# Retaining expensive DDS searches for later training

The two local Gen4 collectors now have an observer launcher,
`scripts/run_arena_with_dds_capture.py`. It delegates to the original frozen
collector (or the supplemental filtered collector when its cancellation plan
exists). Model weights, manifest, scoring, native DDS library, sample counts,
random streams, and frozen runtime files are not edited.

Keep a native call if any solved world visits at least **100,000 nodes**, or the
whole native batch takes at least **100 milliseconds wall time**. These initial
cost thresholds are configurable through `DDS_CAPTURE_MIN_NODES` and
`DDS_CAPTURE_MIN_SECONDS`. Timing includes host contention; it is not an exact
measure of intrinsic difficulty. Cheap calls and cache hits are not logged.

Each retained call stores its complete ordered native batch, fixed seats,
proof-reuse setting, remaining-card bitmasks, trump, leader, partial trick,
all legal-move DD scores, nodes per world, elapsed/CPU time, solver binary hash,
context configuration, frozen cohort identity, deal-family key and board index.
Capture happens after solving and returns the original result unchanged.
Records are compressed and atomically installed under `RUN/dds-expensive/`.
Every qualifying completed call is retained; there is no oldest-file eviction.

This is **a replayable solver input/output corpus, not the internal search tree**.
The live binary does not export every internal proof decision. Hard positions
can be replayed under an instrumented solver later to obtain proof-ordering
teachers. Exact scores alone do not label the cheapest proof. Batch ordering is
retained because it changes proof-reuse costs. These are sampled perfect-
information worlds, not direct single-dummy position-value targets.

The recorder does not recover historical sampled worlds that were never logged.
Existing full episode checkpoints remain intact. Failed or killed native calls
that never return do not produce a completed solve record.

Use `scripts/archive_dds_capture.py --run RUN --out ARCHIVE.zip` for the first
durable archive, then pass every prior archive with `--previous` to archive only
new files. Archives include exact file hashes, source manifest and selection
metadata. Do not put bulk captures in Git or delete local captures before a
verified durable save. Keep all positions from a deal family in one data split.

Validation: a real two-world DDS batch produced identical all-legal-move scores
before/after enabling capture; deserializing and re-solving the saved batch
matched those scores. Scalar capture and cheap-call exclusion were also checked.
The initial smoke fixture is diagnostic only and is not part of training data.
