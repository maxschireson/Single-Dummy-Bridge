# Gen 4 component diagnosis and recovery

The primary arena remained alive when its supervising chat stopped responding.
At 16:16 UTC its feed contained 1,308 committed hands, about 322 hands/hour over
the preceding hour. The supplemental feed was older. No original worker, feed,
manifest, allocation, or STOP file was changed by this takeover.

The verified capsule on `transfer/v4-worker-standby` restored successfully in
the new environment. Its original manifest is
`7559edd31715b71f77a47af22a87cb64b2a72c3da4b0cf262fd76003628f2404`.
Native DDS and all original bots loaded. Available resources: four CPU cores
and 16 GiB RAM. The original capsule STOP remains present.

The new diagnostic manifest is
`41bbca519323eaca0eea06688454f3d74a25778eea27ddc82efb4e9d732c8b5e`.
Its 200 families are selected by a fixed hash of the original frozen cohort,
without looking at scores or completion times. These are explicitly reused
evaluation deals, not new independent evidence to add to the original results.

| Bot | Belief | Cardplay policy |
| --- | --- | --- |
| 3 | Gen 3 | Gen 3 |
| 4p | Gen 3 | Gen 4 |
| 4b | Gen 4 | Gen 3 |
| 4 | Gen 4 | Gen 4 |

For each family all three variants play Gen 3 in both partnership orientations,
using the same precomputed Gen 4 auction and decision seed. Six complete games
are replay-validated before committing the family. Search stays at 32 samples,
near-tie 0.125 and zero exploration. There are no policy forks or historical
bidder conditions in this diagnostic. Differences between variant scores are
paired within family. Report ordinary descriptive intervals, without promotion
or claims based on the first few observations.

## Current environment

- Restored source: `/workspace/work/v4-recovery/Single-Dummy-Bridge`
- Untouched original capsule run: `/workspace/work/v4-recovery/arena-v4/g0004`
- Diagnostic run: `/workspace/work/gen4-components`
- Launcher: `ops/gen4_ablation.py`
- Four workers, parent process recorded in `process.json`.
- State: `state.json`; activity: `heartbeat.json`; log: `supervisor.log`.
- Episodes contain full replayable games, model identities, and per-family scores.

To resume **in this same environment**, first verify that the writer lock is
free using nonblocking flock and inspect any failure in the log. Do not delete
the lock or launch a second writer.

```sh
cd /workspace/work/v4-recovery/Single-Dummy-Bridge
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u ops/gen4_ablation.py run \
  --run /workspace/work/gen4-components --workers 4
python ops/gen4_ablation.py status --run /workspace/work/gen4-components
```

Creating `STOP` in the diagnostic directory drains current families. Completed
episodes are preserved and validated on resume. The process runs to 200 families
and exits; it cannot survive deletion of its environment. GitHub preserves the
launcher and this handoff, not unexported live episode files.

For a replacement environment, restore and preflight the transfer capsule, then
copy this launcher into its `ops/` directory. Initialize a **separate** directory
with `init --source RESTORED/arena-v4/g0004 --run NEW_RUN --count 200`.
Do not run the original capsule collector: it would duplicate the live primary's
allocation. A fresh diagnostic initialization is not an exact continuation of
completed diagnostic records unless those records and manifest are recovered.

Validation: all four exact model combinations loaded; two tests cover full toy
bridge replay, swapped-seat assignments, score corruption rejection, and paired
component/interaction statistics. First real-DDS families committed successfully.

## Active recovered six-bot mix

Following the user's request to insert both bots into the mix and publish it,
the initial matched diagnostic drained at 35 complete families. Its full games
are retained. A new 10,000-hand six-bot mix is running with four workers in
`/workspace/work/gen4-hybrid-mix`. The primary external workers remain alive;
this takeover controls the recovered environment, not those inaccessible hosts.

The frozen manifest identity is
`7729472d36914fd1dce8ecfcc2d520cfc1c03ce737ac99511093e94ebce33a4c`.
It includes 4, 4p, 4b, 3, 2, and 1. In each shuffled 26-board block allocation is:

| Matchup | Hands |
| --- | ---: |
| 4–4, 4–3, 4p–3, 4b–3 | 4 each |
| 4–4p, 4–4b, 4p–4b, 4–2 | 2 each |
| 4–1, 3–2 | 1 each |

Each hand supplies two swapped-seat root games on its frozen Gen4 auction.
Original random policy audits are enabled for the first partnership when it
uses the Gen4 policy. Models, sample budget, zero exploration, and near-tie
window remain frozen. Bidding is common, so this run measures cardplay rather
than native-bidder whole-system changes. The 10,000 source-cohort families are
selected by outcome-independent hashes; cross-cohort overlap is explicit.

The other ChatGPT environment concurrently created a fresh component cohort
on `research/gen4-components` and `arena-components-feed`. That branch is a
different writer and must never be overwritten by this run.

This environment's publisher owns **`arena-recovery-feed`**. It exports validated
root-game replays, dashboard statistics, exact manifests and schedule, and full
compressed episodes including audit forks every minute. The initial 35-family
diagnostic is backed up under `recovery/initial-diagnostic`. Public root replays
and complete episode backups are already pushed; local caches are not uploaded.

The shared webpage is deployed on `gh-pages` and exposes all sources separately:
<https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=recovery>.
Counts are run observations, not claimed distinct families across sources.
Model matrix, hand lists and replays display 4p and 4b labels. Selecting a
source preserves its manifest and snapshot cutoff in hand links.

Resume the mixed run only with a free supervisor/writer lock and no STOP:

```sh
cd /workspace/work/v4-recovery/Single-Dummy-Bridge
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u ops/gen4_mix.py run \
  --run /workspace/work/gen4-hybrid-mix --workers 4
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ops/gen4_mix.py audit \
  --run /workspace/work/gen4-hybrid-mix
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u ops/publish_component_mix.py \
  --run /workspace/work/gen4-hybrid-mix \
  --publication /workspace/work/gen4-diagnostic-publication \
  --diagnostic /workspace/work/gen4-components
```

The publication checkout is a dedicated repository on `arena-recovery-feed`.
Never point it at the primary, supplemental, or ChatGPT component feed branch.
For full environment recovery, restore the original capsule, overlay the new
`ops/` scripts, copy the backed-up manifest/corpus/schedule/episodes into a new
run directory and restore `artifacts/` and `assets/` from the capsule. Preserve
the exact manifest; the collector derives receipts and replay-validates them.
Do not treat a reinitialization as continuation. The collector and publisher
still require a surviving environment; GitHub holds recovery artifacts.

`ops/watch_component_mix.py` is also running locally and records
`watchdog-status.json`. It checks the collector's known PID, production locks,
STOP marker, preserved failures and frozen hashes before a replay-audited
restart. It caps restarts without progress at three and recovers the dedicated
publisher if its known process exits. `WATCHDOG_STOP` stops the watchdog;
`STOP` drains collection. The watchdog cannot survive destruction of this
environment, so the feed's full episode backups remain necessary.

Verification: three focused tests passed; all ten matchups replayed in tests,
and 41 real-DDS mix records passed a full replay audit. Browser checks passed
for all-source visibility, the six-bot matrix, hidden unavailable bidding
condition, snapshot-matched 4p hand lists, and a complete 4p board replay.
