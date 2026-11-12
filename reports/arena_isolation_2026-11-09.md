# Arena isolation and failure diagnostics — 9 November 2026

The measured last two hours at07:32:55UTC produced416paired boards,208/hour,
including downtime. The most recent hour produced325; the preceding hour91.
A short earlier peak near4000/hour did not represent sustained throughput.

The user requested pausing all ancillary compute and diagnosing failures before
further scaling.64vs32 was already inactive at238completed boards; its automation
is now disabled and its run has a STOP marker. Known DDS research runs and
separate model-training runs also have STOP markers. No held job locks outside
the arena/watchdog were found. Unlocked jobs in other process namespaces cannot
be conclusively ruled out. The latest DDS1500 training report says that job ended.

The direct arena continues with two workers and unchanged frozen models, corpus,
32sample PIMC, pair schedule and scoring. A diagnostic operational wrapper creates
fresh pools on60second slices, records RSS/high-water memory, CPU ticks, exit codes,
signals and shared kernel counters, and safely retries recognized process loss.
It preserves failures, validates committed records and retries missing indices.

Initial instrumented workers peaked below185MB each. Two observed worker exits
were clean(exit0) at a normal slice boundary. The shared kernel OOM counter rose
by52over the early sample, but it is not scoped to this arena and is not proof
that its workers were killed by OOM. Resource evidence must be correlated with
actual failure timestamps and exit codes. Disk was24%used with46GBfree; no disk
purge or dataset deletion was justified. There is no claim yet of sustained
stability or recovered throughput.

A local watchdog maintains12rolling report views(three matchups x four windows).
All four existing external monitors know the isolation directive and new launcher.
External GitHub execution was investigated but not launched; migration is deferred
while this isolated baseline is measured. No new external compute jobs were started.

## Captured failure and independent-worker fix

At07:48:23UTC, worker13 exited with SIGKILL. The process-pool manager then
requested terminate() on peers; workers10 and14 exited with SIGTERM. The
signal-sender log identifies the manager's cleanup signals. It does not identify
the original SIGKILL sender. This establishes that the old pool amplified one
worker death into loss of healthy peers and a stopped collection slice.

A concurrent authorized monitor deployed independent spawned board workers,
three at a time, using `ops/independent_supervisor.py`. A killed worker retries
only its missing board while healthy peers continue; ordinary application errors
still stop for investigation. Worker self-telemetry samples each second. A crash
injection check was implemented in `tests/manual_independent_worker_crash.py`.
The watchdog now reads verified `telemetry-ramp.json` settings, preserving this
launcher and worker count on recovery. All four external monitors received the
updated operational handoff. Models, deal identities, PIMC budgets and scoring
remain unchanged. At07:52UTC the arena had297direct pairs, with73completed in
the preceding five minutes(876/hour). This is an early observation, not a claim
of long-term stability or recovery to4000/hour.
