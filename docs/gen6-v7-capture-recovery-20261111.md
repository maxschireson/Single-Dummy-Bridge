# Gen6 BEN64 and Gen7 capture recovery

Max requested medium256/BEN64 instead of BEN32, retaining the equal split of the 15% BEN allocation.
The trigger was overall/native-partnership total IMPs, not common-auction play: +0.54054 IMP/board
on 370 families, paired exploratory 95% interval [+0.03181, +1.04927]. The frozen trigger remains
on `arena-gen6-codex-ben-gate`. BEN32 raw games remain archived for training and are hidden from
dashboard totals, trends, timing and replay lists.

The primary source is `/workspace/Single-Dummy-Bridge-gen6-v7-capture`, branch
`codex/gen6-v7-capture-20261111`. Run: `/workspace/work/gen6-v7-capture`. Publication:
`/workspace/work/gen6-v7-capture-publication`, branch `arena-gen6-codex-v7-capture-feed`.
The retired preceding cohort is `/workspace/work/gen6-ben-followups`, branch
`arena-gen6-codex-ben-followups-feed`; its stop markers are intentional and must remain.

Exact shuffled block of 40: 16 fast/Gen5, 6 fast/medium, 3 medium/BEN64, 3 fast/BEN16,
4 each fast/Gen3, Gen2 and Gen1. Gen6 fast remains 32 samples to trick7, medium256 to trick6;
all nets, tie-only policy selection, common/native auctions and swapped rooms are preserved.
BEN bidding is neural only; opening lead and play are 64 on port8089 and 16 on port8087.
`ben-recovery.json` pins the BEN source and configurations. The unused BEN32 server can stay idle;
it is not scheduled in this cohort.

Gen7 capture instructions: [gen7_data_capture_2026-11-11.md](gen7_data_capture_2026-11-11.md),
from `transfer/gen7-capture-forks-20261111` at `5e82f769a0e989ee10a6cb911a793a964d1b6ff5`.
Every plan has `gap_fork={per_band:2,bands:[0.125,0.5],max_cpu_share:1.5}`. Existing tie audits
stay at probability0.5, BEN audits remain disabled, and gap forks are disabled on every BEN game.
Root outcomes alone feed arena scores. Gap branches are training records and retain separate
metadata. The real-net on/off equivalence report checks original roots, audit cards, audit events,
auctions and scores. It lives in `capture-equivalence.json`; `preflight.json` exercises the actual
production corpus, and `ben-preflight.json` identifies the separate full-game validation cohort.

The launcher is restartable and refuses another intentional stop reason:

```sh
cd /workspace/Single-Dummy-Bridge-gen6-v7-capture
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3 \
XDG_CACHE_HOME=/workspace/work/gen6-cache \
/workspace/work/ben-venv/bin/python -u ops/launch_gen6_v7_capture.py
```

It archives the drained predecessor, freezes only unused deal families, preflights, publishes the
runtime/models/corpus/raw records, starts the watchdog and report monitor, and updates the dynamic
dashboard registry without replacing other producers. Controller evidence and process information
are on `arena-gen6-codex-v7-cutover` and `/workspace/work/gen6-v7-cutover`.

To resume the active collector, first inspect its `state.json`, `watchdog-status.json`, process files,
failures and any stop reason. Use its pinned source/runtime; never patch a running collector.

```sh
cd /workspace/Single-Dummy-Bridge-gen6-v7-capture
/workspace/work/ben-venv/bin/python -u ops/watch_gen5.py \
  --run /workspace/work/gen6-v7-capture \
  --publication /workspace/work/gen6-v7-capture-publication \
  --ben-dir /workspace/work/ben-next-round --ben-state /workspace/work/round5
```

Only start that command if its watchdog process is absent and `.watchdog.lock` is free. Complete
publication includes `recovery/runtime`, artifacts/assets, manifest, corpus, receipts and clean
episodes; restore `runtime-requirements.txt` into the saved Python environment. No IMP tensor
substitutes for the per-action search estimates or final trick counts.

`ops/report_gen7_capture.py --run /workspace/work/gen6-v7-capture --before /workspace/work/gen6-ben-followups --watch`
writes the first report after 2,000 eligible non-BEN root tables. It verifies episode hashes,
reports fork counts/skips by band, actual added CPU and observed deal rates, cost versus estimated
gap by phase with deal-clustered standard errors, within-table residual correlation and touching
versus non-touching tie audits. The publisher includes progress and the finished report. The
process file is `capture-report-process.json`; restart it only when absent. Archived backfill is
separate work: preserve every episode/receipt, prove five stored tie forks reproduce card for card,
then write sidecars on a separate branch.

The GitHub logging/forking observer remains at `/workspace/work/v7-logging-watch`, publishing to
`arena-gen6-codex-v7-watch` every ten minutes. It stages candidates in detached checkouts before
validation and never patches a running cohort. Additional producers register their immutable
manifests in `gh-pages:arena/gen6-sources.json`; preserve completed cohorts and revision-pinned links.
