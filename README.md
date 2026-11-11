# Gen7 capture: Gen6 fast self-play only

Independent 25,000-family cohort, three workers, 50% tie audits, gap forks (2/band, CPU share 1.5). No BEN or medium matches.

Recovery: run `python recovery/restore_corpus.py`, install `recovery/runtime-requirements.txt`, and use the frozen `recovery/runtime` with `ops/gen5_runtime.py --run <absolute recovery path> --workers 3`. Verify manifest, model and runtime hashes before starting; never resume concurrently with the owning producer. Gen3 is an audit selector only.

Raw compressed episodes and receipts are in recovery. Dashboard snapshots are under arena. Self-play has null IMP comparisons.
