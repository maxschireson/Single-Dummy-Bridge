# Owned stream19bbdce5: Gen7.1 recovery

Active manifest: `50f9d04042e9a42b8620183e19c8a631c3803cfb67cfca2479141a3fdeffe461`. Feed: `arena-gen71-19bbdce5-20261112-feed`.
Frozen source: `ops/gen71-19bbdce5-20261112` at `7d96087a3a501909c0441837b95498001e1923de`,
based on adopted Gen7.1 source `56dafd6f9b733372503c4d06c9b37616f45dcc9e`.
Source/run/publication paths and every pinned identity are in `environment.json`.

This transition follows the notice `docs/gen71_2026-11-12.md`: Max explicitly
addressed all general arena collectors, effective2026-11-12 06:00UTC. It replaces
the earlier per-producer Gen7 notices for this delegated stream. The exact released
71s-32 and7s-32 identities are preserved. No model was trained or altered here.

The predecessor is permanently STOP/WATCHDOG_STOP/PUBLISH_STOP at6,775 completed
families. Its final full feed revision is `cb3a31ca58e9f0927a385d3d1ccf8b63d288cd24` on
`arena-gen6-fast-selfplay-20261111-19bbdce5-feed`. Keep that history and never restart the predecessor.
Exactly18,225 previously unplayed families pass to this run; no family is replayed.
Original target accounting remains6,775+18,225=25,000.

Mix: 71s-32~7s-32 weight2, 71s-32~6-32 weight1. Common and native auctions
remain distinct; identical auctions reuse the played tables. Existing50% tie audits,
gap forks, guess capture and tree audits are retained. No BEN service is required.

The comparison-to-selfplay gate is pooled over all producers: at least1,000 boards
of71s-32~7s-32 AND lower end of the95% interval above zero. Check the current
authoritative notice, coordination entry and plan readiness. Do not switch to
71s-32 self-play before that gate and its opened plan. Broad phase2 remains closed.

Restore `recovery/runtime` verbatim as the source and other recovery files as the run;
create empty episodes/receipts/failures folders if an empty folder was omitted by Git.
Restore Python dependencies from `runtime-requirements.txt`. Verify source, runtime,
model and corpus hashes using `verify_generation` from that frozen runtime. Inspect
fresh process ownership, writer/watchdog locks and failures before starting anything.
Use a dedicated publication checkout of this feed branch. Set BRIDGE_ARENA_PYTHON
to the environment's Python and run `ops/watch_gen5.py --run RUN --publication PUB`
from the frozen source. Keep BLAS/OpenMP/MKL/TensorFlow thread counts at1.

To drain, create STOP and WATCHDOG_STOP and wait for in-flight boards and locks.
Stop the publisher with PUBLISH_STOP after a final snapshot. The publisher CLI
does not run with PUBLISH_STOP present; after its process drains call the `publish`
function directly for an intentional final snapshot. Preserve failures and every
completed episode/receipt. DDS caches are recomputable; the watchdog drains before
its2GiB cache rotation and stops collection below3GiB free disk.
