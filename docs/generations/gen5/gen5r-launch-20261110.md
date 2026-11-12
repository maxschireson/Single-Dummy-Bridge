# Gen5R arena handoff — 2026-11-10

Max authorized Gen5R to replace Gen5's ongoing arena allocation. The former
15% 32-versus-192 slot splits equally into the two comparisons below. The live
Codex collector has switched to Gen5R. The original 6,607 completed Gen5 deals
retain their identities and archive; Gen5R uses the remaining 18,393 unplayed
deals. No existing game has been relabeled or overwritten.

| Matchup | Share | Entries per shuffled 40-deal block |
| --- | ---: | ---: |
| 5R32 vs 4b | 40% | 16 |
| 5R32 vs 3 | 20% | 8 |
| 5R32 vs 2 | 15% | 6 |
| 5R32 vs 1 | 5% | 2 |
| 5R192 vs BEN (16) | 5% | 2 |
| 5R32 vs 5R192 | 7.5% | 3 |
| 5R32 vs original 5-32 | 7.5% | 3 |

Each complete block has the exact allocation. The final partial block and
out-of-order completion can differ temporarily. Three ordinary workers and one
BEN worker retain the existing allocation of compute. Both auction conditions,
swapped partnerships and the existing training-fork recipe remain in use.

## Sampling and frozen networks

Only positions with 10–13 tricks remaining use the new selector. 5R32 draws
128 layouts and solves at most 32; 5R192 draws 768 and solves at most 192. Both
use the same cosine shape/honor geometry, average-linkage clustering, actual
medoids, frozen distance tolerance 0.04214601748644102, and nonnegative weights
fitted to exact constrained belief moments with ridge 0.001. The distance
tolerance can produce fewer clusters than the nominal ceiling; zero-weight
representatives are also omitted. Actual pool sizes, solved counts, weights,
calibration residuals and time are recorded at each decision. Below 10 tricks,
ordinary random 32/192 sampling is unchanged. Original 5-32 always retains its
ordinary random sampler and original actor identity.

These are quadrature weights, not exact geometric-cluster probabilities. No
DDS answers are consulted when selecting layouts or weights. The 200-position
screen favored this method over random 32 at its point estimate, with substantial
uncertainty (about 1.2 standard errors); this is an arena experiment.

All three networks are copied from the frozen current Gen5 run:

- Belief: `99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a`.
- Policy: `03e70a6f6021c8bed471dc9de53f462b0e991320ff4ad7734bcc20f54c5aff18`.
- Bidder: `9ee52f3baa79c837001e0cb515c61a9a179cb1bf66cd5503e46331245c014dcc`.

## Launch on the existing collector host

The source run is `/workspace/work/gen5-codex-32`, publication checkout
`/workspace/work/gen5-32-publication`, and code checkout
`/workspace/Single-Dummy-Bridge`. These paths are on the separate Codex host,
not this research environment. Leave the original checkout intact so its frozen
source can still resume or reproduce old records.

1. Fetch branch `codex/launch-gen5r-20261110` and create a separate clean worktree
   at `/workspace/Single-Dummy-Bridge-5r`. Copy the existing native DDS library
   into its `bridge_harness/libbridge_dds.so`; native code is unchanged. Use the
   existing BEN Python environment, with NumPy and SciPy available.
2. Use a clean, up-to-date `gh-pages` worktree. Run the following from the new
   source worktree, replacing `/path/to/gh-pages` with that checkout:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 \
TF_NUM_INTEROP_THREADS=1 BRIDGE_DDS_CACHE='' \
/workspace/work/ben-venv/bin/python -u ops/takeover_gen5r.py \
  --pages /path/to/gh-pages
```

The command preflights four native games before stopping collection. It then
sets STOP and WATCHDOG_STOP, waits for the old writer and watchdog to drain,
stops only the verified old publisher PID, and verifies every completed receipt
and episode checksum. It creates a new immutable manifest and corpus from only
the old run's unplayed indices. This retains the original exclusions and total
remaining deal budget, rather than replaying finished games or adding another
25,000 deals. Old manifests and episode bytes are never changed.

It publishes the final original-Gen5 snapshot with retirement metadata, starts
the replacement watchdog/collector/publisher in `/workspace/work/gen5r`, and
publishes to `arena-gen5r-feed`. After the first completed Gen5R game is
published, it registers that exact manifest identity in `gh-pages`. The
dashboard then defaults to Gen5R; original Gen5 stays available under Older.
R32/R192 and original 5-32 remain distinct in scores, timing and replay links.
The existing BEN server and settings are retained.

The script refuses an existing destination, dirty source/pages worktrees,
source STOP flags, or preserved failures. If it stops after draining, inspect
the exception and the new run before retrying; it intentionally refuses to
overwrite a partially prepared run. A successfully completed handoff writes
`/workspace/work/gen5r/takeover.json`. There is no automatic next generation.

For manual recovery, `prepare_gen5r.py --source ... --run ...` creates the
frozen replacement after draining, `watch_gen5.py --run ... --publication ...`
starts the existing collector/publisher machinery, and
`register_gen5r_report.py --pages ... --manifest ...` registers the exact
published cohort. The last command edits the checkout; commit/push it afterward.
To roll back, drain and stop Gen5R, retain its records, then resume the original
run using its original unchanged checkout and manifest after removing its
operator stop files and retirement statistics policy. Do not run both cohorts
against the same unplayed source families as independent evidence.

## Validation completed here

- 7 Gen5/Gen5R tests: requested allocation, every actor/effort pairing, common
  bidder IDs, partnership swaps, auction reuse, preserving old records and
  excluding completed source deals.
- 9 geometry/reduction tests: honor-swap similarity, draw multiplicity, exact
  moment computation, constrained weights, stage gating, weighted values and
  identical small-position behavior/RNG.
- 3 existing timing/round tests.
- 12 existing dashboard reporting checks, weighted timing check, and a Gen5R
  check for isolation, matchup signs, exact replay rows and retained Gen5 history.
- Four full native DDS games (208 legal actions), both new matchups with swapped
  partnerships, using the actual promoted Gen5 policy and belief. All 40 large
  representative decisions calibrated successfully. Smaller nonforced decisions
  used exactly their original 32/192 budget. See
  `reports/gen5r-native-smoke-20261110.json`.

The live handoff and browser display have now been verified on the collector
host. The default dashboard isolates Gen5R, while Older retains original Gen5.
Actual published root games include all seven matchups. Snapshot-linked hand
counts, native/common bidding, timing attribution and full replay were checked.
See `reports/gen5r-live-handoff-20261110.json` for the frozen identity, sampled
runtime evidence and progress at validation.

The immutable Gen5R manifest is
`cdd9bbb2359f172f69cb19708e8ec8efd2ce4dbb784113a5c3a7b58a347d49a3`.
Tag `gen5-before-5r-20261110` preserves the final original Gen5 publication;
its archived runtime still matches the original manifest's source checksum.
The publisher preserves that runtime when finalizing a different cohort.

The initial restart reached BEN before its listener was ready. That one
connection failure produced no completed episode and is preserved under
`resolved-failures/`, with its resolution. The watchdog now starts BEN first
and gates worker startup on listener readiness. The unchanged frozen cohort
then resumed; no failed or incomplete episode was counted as completed.

The collector-host native preflight is preserved in
`reports/gen5r-collector-preflight-20261110.json`.

## Live dashboard refresh

The collector publishes approximately every minute; the dashboard checks every
30 seconds and refreshes when a tab regains focus or visibility. The default
URL uses `source=latest`, currently Gen5R. Previous source-only bookmarks also
open the current round. Clicking Older adds `older=1`, preserving deliberate
historical selections across reloads.

Index pages can change when games complete out of order, even after containing
100 records. Published replay indices now include each page's SHA256. The
browser caches only checksum-verified content and re-fetches changed pages;
feeds without those hashes are re-fetched. A delayed CDN response cannot be
retained under a newer page revision. Regression coverage includes inserted
late completions, unchanged/changed pages, and recovery after stale responses.

Published index page URLs also include their content hash, so existing browser
tabs using the previous URL-based cache recover on their next update.

The current round resolves the feed branch to one published Git revision and
loads both scores and hand indices using that immutable revision. This avoids
mixed metadata versions in GitHub's branch cache. Revision checks are shared
across browser tabs and cached for 90 seconds to limit public API traffic; the
30-second display checks normally pick up a new snapshot within about two
minutes. Score links carry the displayed revision through hand lists, replays
and back links, keeping their exact board counts intact. Historical views keep
their explicit Older selection.

Refresh regressions cover out-of-order completions, content hashes, changed
page URLs, stale CDN payloads, unique metadata requests, coherent revisions,
API request reuse and exact snapshot drill-downs. A browser using the live
public feed advanced automatically from 1,221 to 1,253 deals during validation.
