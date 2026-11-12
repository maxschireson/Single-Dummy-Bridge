# Independent Gen 7 collector: retired anchors to self-play

Max's 12 November 04:09 UTC instruction in `configs/round7-phase1-selfplay.json` retires Gen 5 and Gen 1 and directs those deals to standard self-play. The capture-preserving source is `feature/gen7-selfplay-20261112` at `7780e5e` (including this collector's `522eda6` capture port). This is a phase 1 allocation update, not permission for the closed phase 2 plan or a model change.

This collector previously assigned weight 1 each to Gen6, BEN16, BEN64, Gen5 and Gen1. `configs/round7-independent-selfplay-ben.json` retains the first three weights and replaces the two retired weights with weight 2 for standard self-play: 40% standard self-play, 20% each Gen6/BEN16/BEN64. Every bot identity, policy v4 hash, tree parameter, sample setting and bidder remains unchanged. Existing gap settings (2 per band, edges0.125/0.5, CPUshare1.5) and tie probability0.5 continue; BEN boards have no forks.

The predecessor `/workspace/work/gen7-phase1-independent` is drained and permanently stopped. Its complete raw records, receipts, immutable manifest and scores remain in `arena-gen7-phase1-independent-feed` under a pinned historical dashboard source. The successor `/workspace/work/gen7-independent-selfplay` uses only its unplayed families; its new feed is `arena-gen7-independent-selfplay-feed`. Preflight records never count as completed arena boards.

Self-play is one physical root per deal family, with null comparison IMPs and no strength estimate. Common/native bidding remains explicit on every cross-match. The successor manifest declares self/common/native conditions; the source helper reuses an existing Gen7 actor only when the newly resolved actor is exactly identical.

Validate all Gen7 tests and gap tests, then real-network comparison and self-play records with nonzero gap forks, guess-size/best-share fields, legal replay and null self-play results. `gen7-independent-cutover.json` records current paths and lineage; recovery follows the successor's environment/handoff/launch metadata and frozen hashes. Never restart historical predecessors, duplicate held workers or modify other collectors.

The historical Gen5/Gen1 evidence stays on the dashboard and no longer enters the active stop rule. The retained Gen6/BEN16/BEN64 comparisons retain their pooled family-deduplicated 2,000-board phase 1 targets. At the remaining comparison boundary, stop this collector and keep the hourly instruction watcher enabled; do not open phase 2 automatically.
