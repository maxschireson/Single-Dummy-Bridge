# Current arena: Gen6 BEN followups

Status: running. The previous primary medium/BEN16 run drained at 1,545 complete deals and is archived.

- Run: `/workspace/work/gen6-ben-followups`
- Source: `/workspace/Single-Dummy-Bridge-gen6-ben-followups`
- Manifest: `73519613aa89547be33a71f460abe090d4bd73b467e44b9395f46774090cdc60`
- Feed: `arena-gen6-codex-ben-followups-feed`
- Active primary mix: 7.5% medium256/BEN32, 7.5% fast32/BEN16; other shares unchanged.
- Gate: overall native-bidding total +0.54054 IMPs/board on 370 deals, 95% interval [0.03181, 1.04927].
- V7 source watcher: `/workspace/work/v7-logging-watch`, GitHub `arena-gen6-codex-v7-watch`.

# Conditional Gen6 BEN followups

Max authorized two new matches after Gen6 medium establishes a lead over BEN16:
**medium (256) versus BEN32**, and **fast (32) versus BEN16**. The staged plan
splits the existing 15% BEN share evenly between them. Other shares stay at 40%
fast/Gen5, 15% fast/medium, and 10% each fast/Gen3, fast/Gen2 and fast/Gen1.

The operational trigger is the combined, deduplicated **native-bidding total**
result for medium/BEN16: at least 200 independent deal families and the existing
dashboard's paired Student-t 95% interval entirely above zero. These are the
dashboard's exploratory intervals, not an always-valid confidence sequence.
Common-auction play results are recorded separately and do not trigger this job.

## While waiting

- Source: `/workspace/Single-Dummy-Bridge-gen6-ben-followups`.
- Branch: `codex/gen6-ben-followups-20261111`.
- Plan: `configs/round6-ben-followups.json`.
- Gate state: `/workspace/work/gen6-ben-gate`.
- GitHub status, observations and trigger: `arena-gen6-codex-ben-gate`.
- Current run remains `/workspace/work/gen6-codex` under its original source
  `/workspace/Single-Dummy-Bridge-gen6` and original watchdog.
- BEN16 remains on port 8087, with its existing neural-only bidder and 16 lead
  and play samples. BEN32 uses port 8088 and `configs/ben-gen6-32.conf`.

The watcher polls every five minutes. Each input pins an immutable producer
commit, verifies replay-index SHA256 and native score totals, checks actor
identities, and deduplicates whole deal families. Observed records are retained
in `ledger.json`, so a producer's later cohort rollover does not erase evidence.
Missing or mismatched required inputs block activation. Nothing drains before
`trigger.json` exists and has been pushed to the gate status branch.

From the followup source checkout, resume a missing gate watcher with:

```sh
BRIDGE_ARENA_PYTHON=/workspace/work/ben-venv/bin/python \
  /workspace/work/ben-venv/bin/python -u ops/watch_gen6_ben_gate.py
```

It holds `.controller.lock`. Do not start another writer against that state.
`CONTROL_STOP` pauses it. Inspect `status.json` and `controller.log` for any
blocked retry. A source-code change requires an inspected restart. The plan,
observations, status and one-shot trigger are backed up on GitHub.

## V7 logging and forking source watch

The separate `ops/watch_v7_logging_updates.py` observer polls GitHub every ten
minutes, records relevant changed commits and files, and stages them in detached
checkouts under `/workspace/work/v7-logging-watch/staged/`. It does not change
the current immutable arena. Read the candidate's instructions and run its
validation before a new logging/runtime cohort is prepared.

Its status and exact candidate commits are backed up on
`arena-gen6-codex-v7-watch`. Resume it from the followup source checkout with
`/workspace/work/ben-venv/bin/python -u ops/watch_v7_logging_updates.py`.
It holds `.observer.lock`; `CONTROL_STOP` in its state directory pauses it.
This watch remains independent of the BEN gate and continues after BEN
activation. The BEN gate's source-control file hashes prevent an unreviewed
runtime edit from changing an already armed transition.

## Automatic transition

On qualification the watcher preserves the exact evidence, drains the primary
collector and watchdog, stops its publisher after in-flight deals finish,
archives the final baseline, and freezes the unused source families into:

- Run: `/workspace/work/gen6-ben-followups`.
- Publication: `/workspace/work/gen6-ben-followups-publication`.
- GitHub feed: `arena-gen6-codex-ben-followups-feed`.

If the old corpus is exhausted, it generates a fresh independently seeded
cohort excluding the source corpus. All Gen6 networks and play settings stay
unchanged. Both common Gen6 and native partnership bidding, swapped rooms,
raw PIMC estimates, final trick counts and decision timing are preserved.
The new BEN configuration changes only the five opening-lead/play sampling
counts from 16 to 32. Bidding remains neural-only.

Both BEN sample budgets are supervised independently; readiness and the actual
process config hash are checked. The new cohort passes actual game preflight
for both requested pairings before collection. It has its own writer,
publisher and complete recovery archive. The dashboard registry adds its
immutable manifest and pins the retired primary snapshot. The 13 original
accidental fast/BEN records stay archived; newly authorized fast/BEN records
are counted because they belong to a distinct cohort.

## Once active

The current `handoff.json`, `environment.json`, `gate-trigger.json` and
`ben-recovery.json` in the new run give the precise manifest, source and model
hashes, both BEN process/config identities, gate inputs and launch controls.
The publisher saves these under `recovery/` together with source runtime,
native library, dependencies, original corpus, episodes, receipts and assets.

Resume the production watchdog from the followup checkout:

```sh
BRIDGE_ARENA_PYTHON=/workspace/work/ben-venv/bin/python \
  /workspace/work/ben-venv/bin/python -u ops/watch_gen5.py \
  --run /workspace/work/gen6-ben-followups \
  --publication /workspace/work/gen6-ben-followups-publication
```

Do not resume the retired primary collector or remove intentional stop markers.
Do not edit the frozen manifest, artifacts, runtime or completed records.
If activation is blocked before the new collector starts, preserve the state
and inspect the published error; the watcher retries from the saved step.
