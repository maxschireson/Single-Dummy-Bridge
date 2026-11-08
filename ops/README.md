# Bounded collection and stoppage diagnostics

`collection_slices.py` wraps the frozen campaign collector without editing
`bridge_harness/`, `scripts/`, weights, manifests, or settings. Its operational
files live outside the campaign source hash. OpenAI Codex implemented this
launcher for Max Schireson; all existing BEN/DDS attribution still applies.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u ops/collection_slices.py supervise \
  --root runs/v2-loop-001 --seconds 240 --workers 4
```

The supervisor waits for any existing writer to release its lock. It then runs
successive collection slices, immediately launching another after each clean
yield. Each slice checks the frozen source/dependency hashes and uses the
original campaign's validation and atomic saves. Four workers is a scheduling
cap, not a change to deal seeds, samples, exploration, targets, or model weights.

240 seconds is a **soft submission deadline**. Already submitted boards finish
under their original 300-second board timeout; auction collection and cached
record validation can also extend a slice. Do not hard-kill a difficult board
to enforce the slice deadline. Failed records still block progression.

The event log is `runs/v2-loop-001/slice-events.jsonl`; raw collector output goes
to `worker.log`. Events record child starts/exits, return codes, elapsed time,
saved records, memory availability, system load, and the sum of RSS visible in
the supervisor's process namespace (shared pages can be counted more than once).
The system memory view may not expose a tighter container limit.

An abrupt end of supervisor heartbeats without a child-exit event is consistent
with loss of the whole execution session, not proof of an OOM or time limit.
Neither a supervisor nor a child can restart itself after the whole runtime is
destroyed. In that case an external agent must launch a fresh exec session;
the existing hourly automation is the fallback, not a 15-minute scheduler.

When collection finishes (or the state has advanced beyond collection), the
supervisor emits `ready_for_campaign_runner` and exits. Resume the normal
campaign command for fitting, screening, and confirmation:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u -m bridge_harness.improvement \
  run --root runs/v2-loop-001 --generations 1
```

Before launching any writer, check both `.slice-supervisor.lock` and
`.writer.lock` using nonblocking flock. Never remove either lock file.
If a supervisor is alive, do not compete for the gaps between its slices.

Tests: `python -m unittest discover -s ops -p 'test_*.py' -v`.
