Prepare a second, independent cloud machine for the existing v4 bridge arena.
This is standby setup only: DO NOT start collection, a supervisor, a watchdog,
bulk DD calculations or a publisher, and DO NOT remove the standby STOP marker.
The primary collector is still running on another machine.

Use the managed cloud runtime skill and wait for this task's environment to be
ready. Inspect existing files and preserve any pre-existing work. Do not create
a Git worktree. Clone this branch into a new directory:

  git clone --single-branch --branch transfer/v4-worker-standby https://github.com/maxschireson/Single-Dummy-Bridge.git /workspace/v4-worker-transfer

Read its README.md. Restore the verified capsule into the empty directory
/workspace/v4-worker-standby with restore_worker.py. Create a separate Python 3.12
venv, install numpy==2.3.5 and scipy==1.17.0 with TLS/checksum verification intact,
then run standby_preflight.py using that venv. It validates exact frozen source,
models and native DDS compatibility and loads every bot without playing boards.
The wrapper configures writable caches and one-thread BLAS/OpenMP settings.
Do not regenerate hands, auctions or models, rebuild the native library, or edit
the frozen manifest. No credentials from the primary machine are needed.

Report the attached environment ID, CPU quota, available RAM, preflight result
and manifest identity 7559edd31715b71f77a47af22a87cb64b2a72c3da4b0cf262fd76003628f2404.
Wait for a disjoint index-allocation grant and a shard-aware launcher from the
primary chat. The capsule's original v4_runtime.py selects ALL missing indices;
launching it independently would duplicate work. Proposed secondary indices
12496..24999 are NOT granted yet. Machine-local locks do not coordinate boxes.
