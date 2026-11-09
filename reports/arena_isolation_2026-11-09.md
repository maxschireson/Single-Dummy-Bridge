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
