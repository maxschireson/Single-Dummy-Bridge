# Gen6 fast self-play stream recovery

Manifest: `19bbdce5dc29e40817e313ecf11ebb5e057364dc28ad5fc1a8d3ae0bfdff8936`. Publication branch: `arena-gen6-fast-selfplay-20261111-19bbdce5-feed`.
Target: 25,000 fresh families; only `6-32~6-32` is scheduled. Gen3 is only the
tie-audit reference. Self-play IMP comparisons are null. Gen7 capture, gap forks,
50% tie audits and the published fast actor are preserved.

Current source: `/workspace/work/bridge-feed-snapshot/recovery/runtime`. Current run: `/workspace/work/bridge-gen6-fast-selfplay-new`.
Current publication checkout: `/workspace/work/bridge-gen6-new-publication`. Python: `/workspace/work/bridge-venv/bin/python`.

The source is restored exactly from published feed revision
`13e0fc7b884ecfa546f693a9bac0d92b520f1247`. Actor hashes and source hash were checked.
`exclusions.json` records 90,737 excluded families from five published active
cohorts and the available Gen5 training family list. The new corpus has zero overlap.

To recover on another host, clone only this feed branch. Restore `recovery/runtime`
as the source and the other recovery files as the run. Create a Python environment
with `runtime-requirements.txt`. Run `verify_generation` from that source before
launching. Refresh heartbeat, process ownership and both locks first; do not launch
a second writer against a living collector. Give the publisher its own checkout
of the same feed branch. Set `BRIDGE_ARENA_PYTHON` to the chosen Python executable
and run `ops/watch_gen5.py --run RUN --publication PUBLICATION` from the frozen
runtime. No BEN server is required by this schedule.

To drain, create `STOP` and `WATCHDOG_STOP` in the run and let in-flight work finish.
Stop publication with `PUBLISH_STOP` after the final snapshot. Preserve all episodes,
receipts, failures and immutable manifests. The DDS cache is recomputable.
