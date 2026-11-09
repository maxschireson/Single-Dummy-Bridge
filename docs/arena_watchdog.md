# Local arena watchdog

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u ops/watch_direct_arena.py --pointer /workspace/scratch/a1f2b806f0ac/bridge-arena/runs/mixed-fork-25k/current.json --workers 2` from the direct arena checkout.

It checks every 300 seconds, follows the shared current pointer, and writes
`watchdog/status.json`, `watchdog/history.jsonl`, and 12 report views in
`watchdog/reports/`: AB/AC/BC crossed with 5/15/30/60-minute windows. Rates count
completed independent pairs over elapsed wall time, including downtime.
Reports are local snapshots, not scheduled chat deliveries. Windows overlap.

The watchdog owns `watchdog/.watchdog.lock`. Never delete lock files. External
monitors should inspect that lock, report freshness, both arena locks, failures,
and committed progress. If the watchdog has exited and its lock is free, resume
it with the command above. `watchdog/STOP` intentionally disables it; an arena
`STOP` is also respected. Never resume the old substitution collector.

Recovery requires both arena locks free, unchanged frozen source/models and a
full audit of committed records. Only abrupt BrokenProcessPool failures are
automatically archived/retried. Other failures remain in place for investigation.
All missing indices are retried; no completed record is overwritten. Three
recoveries without advancing the next missing index block further automatic
retry. Progress is checked after restart. A held lock without recent progress
is reported for investigation, never force-killed by this watchdog.

This process cannot survive destruction of its hosting environment. It is a
fallback while durable external compute is being prepared, not a guarantee of
uninterrupted execution. Existing external monitors remain necessary.

## Compute isolation and diagnostic supervision

The user's cleanup directive pauses ancillary bridge/DDS compute and64vs32.
Shared control is `/workspace/scratch/BRIDGE_COMPUTE_CONTROL.json`. Existing
results and checkpoints are preserved. The 64vs32 automation is disabled and
known ancillary run directories carry STOP markers. No other held job locks
were found; process namespaces prevent a definitive host-wide process census.
Disk has ample space, so deleting datasets or clearing warm caches is unwarranted.

The watchdog now launches `ops/diagnostic_supervisor.py supervise --run RUN
--seconds 60 --workers 2`. This wrapper leaves all pinned play and model files
unchanged. Every60seconds plus in-flight drain, a fresh pool replaces the old
workers. Each pool records resource samples every5seconds and exit signals as
soon as observed in `RUN/diagnostics/*.jsonl`. `ops/summarize_arena_health.py RUN`
summarizes recent observations; watchdog/diagnostics-summary.json is refreshed
by the watchdog. Cgroup and PSI metrics are unavailable in this environment.
The shared kernel OOM count does not identify an arena worker as the victim.

Recognized BrokenProcessPool exits trigger an immediate verified supervisor
recovery after5seconds, rather than waiting for the five-minute watchdog. It
requires free production locks, unchanged source/models, a replay audit, preserved
failure history, and at most3retries at the same missing index. Unknown errors
remain blocked. The watchdog is still the fallback if the supervisor itself dies.
Neither can survive full destruction of their hosting environment; the existing
external monitors check their health and can restore them.

The later verified operational handoff uses `ops/independent_supervisor.py` with
three workers. The watchdog's `launch_settings` reads ACTIVE_RUN/telemetry-ramp.json
when its status is running-verified, accepts only the three known diagnostic
launchers, and bounds worker counts. This avoids silently restoring the former
pooled implementation after a failure. Consult the live handoff over older prose.
