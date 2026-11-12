# Diagnostic journal V4

This is a separately identified diagnostic storage adapter. Production remains
65a, stopped at 2015 with unresolved failure 003062. Candidate 1bd is not promoted.
There are zero new plays or production commits in this experiment.

Each immutable node has SHA-256 references to its parent, exact compressed
episode, receipt, and post-claim RNG. It includes sequence, record index, kind,
pre-state SHA, and protocol identity. CURRENT is a small atomic head containing
tip, count, RNG and identity. Normal records preserve the BEN RNG. Unreferenced
objects, temporary files and interrupted writes never become accepted records.
No episode scanner participates in recovery.

PROTOCOL binds the adapter, receipt/state/export code, production manifest and
retained inventory, and the prior V3.1 collection/server/executor/semantics source.
Opening or reading a journal checks that descriptor against current files and
runs the frozen generation verifier for source, runtime, bot models and corpus.
Synthetic scaling journals have a distinct bound mode and cannot be exported as
real records. A synthetic append to a real journal is rejected.

A writer validates the full chain once, then holds an exclusive lock and an
accepted-index set. Each append checks its cached head and expected RNG, writes
and fsyncs objects, fsyncs their directory, writes and fsyncs a unique temporary
head, replaces CURRENT, and fsyncs the journal directory. Parent references keep
node storage linear; ongoing append does not reread ancestors. Recovery and
snapshots still read every accepted node and payload. This design assumes no
garbage collection and cooperative writers, and does not provide protection
against malicious rewriting or rollback of a complete valid head.

A snapshot captures CURRENT once and copies only its verified reachable objects.
Concurrent appends can advance the live head but cannot extend the captured view.
The test deliberately pauses a reader after capturing and validating its head,
starts additional writes, then lets copying overlap the remaining writes.

The eight inputs are exact archived, newly-played-in-the-prior-pass V3.1 records
and their recorded RNG sequence. They were not played by V4. Four are appended,
a snapshot races the remaining four, and a fresh process continues the restored
four-record snapshot to eight. The actual frozen exporter is compared for counts,
statistics, identity and allocation, with exact final RNG equality. Existing
V3.1 versus V3 audit-volume differences are unchanged and are not waived.

Sixteen actual SIGKILL tests cover eight write boundaries for BEN and normal
records. Each recovers old or new state, rejects duplicates, and successfully
continues with another record. These are writer-boundary tests using archived
fixtures, not live in-flight collector death or power-loss tests.

The scale test appends 8128 small synthetic records with the actual durable
journal implementation, snapshots a captured 2015-entry head during the
remaining appends, fully verifies recovery, and appends record 8129. It tests
chain size and algorithmic behavior, not storage costs of 8128 full episodes.
The large synthetic object store is reproducible scratch data; source, measurements
and the small real-fixture journals/exports are included in recovery publication.

Reproduce from this diagnostic directory with the production shared Python:
`python probe.py`. The test requires a fresh
`/workspace/scratch/171a0eb26892/journal-v4-tests` output path. `initial-result.json`
records an earlier pass before full frozen-generation verification was added;
`result.json` is authoritative for the final source and protocol.

Remaining adoption gates: wire this version into actual live futures and server
staging; interrupt the collector while work is in flight and verify all owned
children are cleaned up; restore and continue without accepting abandoned work;
exercise full-size game payloads and production exporter integration. Power-loss
durability is untested. Neither isolated-claim protocol nor any journal test
recovers the unavailable original dead-server RNG or proves equivalence to
unchanged production BEN.

Repository oversight also found Gen7 phase 1 authorization at fe382f9. That
handoff says which collectors move and when remains a per-collector instruction.
No local Gen7 cutover was inferred, no other producer was changed, and phase 2
remains closed. Main and the existing Gen6 active mix are unchanged.
