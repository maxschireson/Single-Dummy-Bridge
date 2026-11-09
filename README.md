# V4 second worker — STANDBY ONLY

This is a verified copy of the exact frozen runtime, compiled DDS binary, all four
play models, both bidders, and all 25,000 hand sets with precomputed auctions.
No credentials, caches, logs or live processes are included.

Do not launch collection or remove the supplied STOP marker yet. The primary
collector still owns all missing indices. A second writer needs an explicit,
disjoint allocation and shard-aware launcher from the primary chat first.
The original v4_runtime.py collects ALL missing indices and is NOT safe for
unsynchronized multi-machine collection. Machine-local locks do not coordinate
across boxes. Do not generate fresh hands, rebuild DDS, alter the manifest,
change the model mix, or start bulk DD calculation.

Restore into an empty directory. Requires Linux x86_64, Python 3.12 and a compatible
libstdc++/glibc for the supplied library; the same Codex environment image is best.
Install numpy==2.3.5 and scipy==1.17.0 in a venv. TensorFlow is not needed to play
the already-frozen auctions. Set OPENBLAS_NUM_THREADS=1 and OMP_NUM_THREADS=1;
use four independent workers once an allocation is granted.

From the extracted Single-Dummy-Bridge directory, verify without collecting:

    python worker_preflight.py

Report CPU quota, RAM, native compatibility and manifest identity to the owner.
Wait for the allocation handoff. Proposed split (NOT ACTIVE): primary indices
0..12495, secondary 12496..24999. Each machine keeps its own records; merge by
(manifest_identity,index) and canonical family, never by summed counters.
The existing dashboard/publisher remains the single aggregate publication owner.

Keep the DDS and BEN licenses in the package. Model source is
research/bidding-actual-outcomes commit 1d18faad0a9141c423c2cc1a1bd521b450870c5d.

## Fresh-chat setup (safe while the primary keeps collecting)

Clone this transfer branch into a separate directory, then:

```bash
python3 -m venv /workspace/v4-worker-venv
/workspace/v4-worker-venv/bin/python -m pip install numpy==2.3.5 scipy==1.17.0
python3 restore_worker.py --output /workspace/v4-worker-standby
/workspace/v4-worker-venv/bin/python standby_preflight.py --restored /workspace/v4-worker-standby
```

The preflight wrapper configures writable caches and one-thread math libraries.
No collection or bulk DD calculation runs. Keep the standby STOP file in place.
Report readiness and available CPU/RAM. The owner will arrange the disjoint work
allocation and updated operational launcher. The old one-minute group launcher in
this capsule is not the final distributed-worker launcher.

The primary chat cannot attach to a different chat's box just from its environment
ID. Coordination will use GitHub handoffs and independent writers with disjoint
indices; public aggregate publishing remains owned by the primary environment.
