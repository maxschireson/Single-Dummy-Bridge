# Owned stream19bbdce5: Gen8 recovery

Manifest `507374949f82b9f19e9166d734a140a6b89d7a8b476379ffd383832a8f8f495d`, feed `arena-gen8-19bbdce5-20261112-feed`.
Frozen source `ops/gen8-19bbdce5-20261112` at `c8a138f21d5b60bf56c30a5f59bad92e728c3bac`, based on authorized
Gen8 `792c4cb3f647ec71273f0cc57d95be1d0a0a5954`. Never pull into this running checkout.
The preparation-only extension restores missing requested frozen actors from an archived catalog;
it never overrides retained actors, changes player/model settings or imports another pool's deals.

Authority: Max16:11UTC and the operator16:24UTC on12November2026 explicitly instruct all
collectors, including19bbdce5, to switch. The five matchups and exact released models are
from the open `configs/round8-candidate.json`. Three normal workers; no BEN service.
Common/native auctions,50% tie audits, gap forks and guess capture remain enabled.
Every declared system is carried in the records; `systems:NS|EW` is the auction source.

Both predecessors are permanently STOP/WATCHDOG_STOP/PUBLISH_STOP. Gen6 ended at6775;
Gen7.1 ended at2189 on `d7d6f7b84106b7fb508b7f828a19867bb314c083`. Their full feeds, immutable manifests,
models, runtimes and every completed episode/receipt are pinned in `history-index.json`.
Never restart them. Accounting:6775+2189+16036=25000 original fresh families.
The Gen8 corpus is precisely the unplayed Gen7.1 families; no fresh top-up or other producer pool.
The34092-family union at transfer/v41-training-families-union-20261112:fccbbd8 is excluded
and retained with SHA256 `0b8ac2b7f41b91915f518c42f76701728097b4151acb5d0e964051c261eca0e2`.

For recovery restore `runtime` verbatim as source and recovery metadata/artifacts/episodes/receipts
as the run; create empty failures/episodes/receipts directories when Git omitted an empty folder.
Verify the generation, source, runtime and model hashes before considering restart. Inspect fresh
processes, locks, heartbeat, preserved failures and this stream's descriptor first; dated reports
are not liveness evidence. Use the environment's Python, set BRIDGE_ARENA_PYTHON and BLAS/OpenMP/
TensorFlow thread counts to1 and XDG_CACHE_HOME to a writable workspace cache. Use one publisher
checkout and buffered Git HTTP transport (`http.postBuffer524288000`). No credentials in logs.

Drain with STOP and WATCHDOG_STOP; wait for in-flight work and both locks. Preserve every
episode and receipt, stop the publisher with PUBLISH_STOP, then call its publish function directly
for the last snapshot after its process exits. A diagnosed failure blocks unchanged restart.
Code/models/settings changes need another immutable, validated successor with retained history.
The watchdog rotates only the disposable DDS memoization cache after a graceful drain.
