Current primary manifest: `4e60d9cd921b2ea25d800be0d91cc9678f8ab86aca86636549d41ff9c1158b6e`. Source commit: `57d3633a07fafa30121667d7618fc2d3c337ad1f`.

# Collector health and feed freshness

The dashboard checks active publications every 30 seconds. Each collector publisher exports and
pushes its data every 60 seconds. A webpage refresh cannot restart a paused host or a failed
publisher. The most recent committed snapshot is evidence at that time, not a live process check.

The health table distinguishes a fresh publication, an overdue update, an overdue collector
heartbeat, an intentional drain/stop and an archived run. It shows the last heartbeat and last
publication separately. Archived snapshots retain their fixed revisions and replay links; they
are fetched once and are never expected to advance. Active feeds are never silently retired
because their updates are late.

On the owning host, `ops/watch_gen5.py` supervises the collector, BEN and publisher independently.
`ops/export_gen5.py` checks the writer lock and rereads the heartbeat when constructing health
metadata. This avoids equating a running publisher with a running collector, or treating an old
heartbeat read at the beginning of an export as current. The publisher retries failures every
minute; Git operations time out after 180 seconds rather than hanging indefinitely. Intentional
STOP/PUBLISH_STOP markers and preserved failures remain authoritative.

To operate continuously, run the collector watchdog on an always-on host, supervised by its
service manager. A process in a paused workspace cannot keep pushing or restart itself; the
workspace must be resumed first. On each owning host, inspect the current manifest, heartbeat,
writer/watchdog locks, publisher status/logs and stop markers before recovery. Never take over a
different worker just because a report is old. Recovery commands and process files belong to
the specific immutable run. The `recovery/` capsule includes its runtime, model artifacts,
corpus, episodes and receipts. Publisher problems do not justify editing archived records.

The primary collector transitioned from the historical mixed Gen6/BEN64 cohort to
`configs/round6-fast-selfplay.json`: 37 fast-self-play deals and 3 fast/BEN16 deals per shuffled
block of 40. The unchanged fast actor and its Gen3 tie-audit reference remain pinned; neither
medium nor old opponents receive new work. Gap capture and 50% tie audits remain enabled,
BEN forks remain disabled, and self-play has null strength IMPs. Remaining unused source
families continue in a new immutable cohort. Existing historical results stay in the arena,
with BEN32 hidden.

The new source starts from `main` at `b0909bb`. It ports reviewed gap-capture files from
`4212444` and the already-deployed self-play validation/export path from `b89d8d58a438` as
individual files; no feed or transfer branch was merged. The owned primary run is
`/workspace/work/gen6-fast-selfplay-primary`, source `/workspace/Single-Dummy-Bridge-feed-health`,
publication `/workspace/work/gen6-fast-selfplay-primary-publication`, branch
`arena-gen6-fast-selfplay-primary-feed`.

To resume that run, inspect its saved state and stop reasons, then use its pinned checkout:

```sh
cd /workspace/Single-Dummy-Bridge-feed-health
/workspace/work/ben-venv/bin/python -u ops/watch_gen5.py \
  --run /workspace/work/gen6-fast-selfplay-primary \
  --publication /workspace/work/gen6-fast-selfplay-primary-publication \
  --ben-dir /workspace/work/ben-next-round --ben-state /workspace/work/round5
```

Start only if the watchdog process is absent and `.watchdog.lock` is free. Keep the retired
mixed cohort's stop markers. The first 2,000-root-table capture report remains in that cohort's
recovery publication as `gen7-capture-report.json`. Do not relaunch its superseded mix.

Retired mixed snapshot: `84c8213ad4076d38b4ef81dc2a0ccde9dcd3ce98`, 1134 deals; first 2,000-root capture report is preserved there.
