# Gen 4 collection from the ChatGPT environment

This independent 10,000-deal cohort supplements the existing `g0004` arena.
It uses 32 sampled worlds, frozen Gen 4 bidder/belief/policy artifacts, two
root tables, both common-v4 and native-bidder conditions, and independent
random policy audits. Matching auction/assignment/seed trajectories are reused.
The schedule in each shuffled 16-board block is 8 × 4–4, 4 × 4–3, 2 × 4–2,
1 × 4–1 and 1 × 3–2. There is no competitive self-play score.

The seed is `797611091314`. Manifest identity:
`b1e339d361600d6ba1fb7ad8058ae9fead50b247a0dd7c12f806a2293f06370d`.
All 10,000 rotation-canonical families are distinct. None matched the 44,974
legacy exclusion families or the first 356 published live Gen 4 families.
These are new deals; results are not appended to the existing cohort identity.

The public dashboard shows collection totals across environments and lets the
reader choose the source for statistics and card-by-card replays. IMP evidence
is kept separate by cohort. We have not established identical runtime settings
for the external collector, and this collector does not compute the external
dashboard's optional DD auction-change metric.

## Runtime

The local checkout is `/workspace/scratch/79c1d8b49652/bridge-gen4-local`.
The run is `runs/gen4-supplement-20261109`. Python with TensorFlow is
`/workspace/scratch/bf0fa8ac2d09/.venv/bin/python`.

```sh
OPENBLAS_NUM_THREADS=1 /workspace/scratch/bf0fa8ac2d09/.venv/bin/python \
  scripts/run_supplemental_arena.py --run runs/gen4-supplement-20261109 \
  --workers 8 --seconds 86400
```

Only one collector may hold `writer.lock`. A `STOP` file drains existing boards;
remove it only for an authorized resume. Completed episodes are atomically
committed and skipped on restart. The manifest pins runtime and model hashes.
Keep all original training/validation family assignments. Never mutate a
running manifest or use the existing arena's writer/feed branch.

Four workers completed 56 boards in 352 seconds including startup and drain,
about 572 boards/hour. Eight-worker measurements are recorded in live status.
These are short throughput measurements on different fresh boards, not a
controlled speed benchmark against the external environment.

## Feed publication

`scripts/export_supplemental_feed.py` validates complete episodes, exports the
root games, and creates score/replay snapshots under `publication/arena`.
The first export verifies every trajectory; later exports reuse only records
whose immutable episode checksum still matches. Replay and index chunks are
bounded to 100 boards. Statistics use one board as one observation and keep
auction regimes separate.

Run `scripts/publish_supplemental_feed.js` in the `functions.exec` runtime,
where its authenticated `tools` object is available. It repeatedly exports,
uploads only changed JSON blobs, and commits through compare-and-swap updates
to `arena-local-feed`. It never writes `arena-feed`. It publishes approximately
once a minute, stops at 10,000 completed boards, and leaves a local publisher
heartbeat. A separate hourly recovery task checks collection and publication.

The dashboard changes are deployed to `gh-pages`. Preserve `arena/supplemental.js`
and its script tag when rebuilding the page. `arena/replays/common.js` discovers
both feed catalogs and expands chunked replay indexes.

## Validation

Six focused tests cover the original arena behaviors, exact supplemental
mixture, self-play score suppression, room reuse and statistical signs/windows.
The Python exporter replays committed root/audit trajectories before first
publication. The browser's pure replay engine independently accepted all 168
root-table condition views in the first published 42-board snapshot. Public
browser checks cover the source selector, snapshot-matched board links, and
the card-by-card viewer.
