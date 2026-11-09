# Shared bidding beliefs and cached cardplay solves — 9 November 2026

## Belief update

Imported 40,000 committed bidding-training deal pairs (80,000 room auctions). Deduplicating identical room auctions leaves 58,002 auctions. The export required zero additional DDS solves, bidder inference calls, or played games.

| Belief split | Deal families | Observations |
|---|---:|---:|
| train | 32,057 | 372,104 |
| validation | 3,983 | 45,936 |
| test | 3,960 | 0 |

Each distinct exported auction supplies one pre-call and one completed-auction observation for each seat. These views are correlated; observations are not independent deals. New belief validation/test families came from upstream bidding TRAIN data, so they are not independent end-to-end bidding tests. No official bidding development/confirmation data was imported.

The 46,582-parameter incumbent was warm-started for eight epochs, with equal replay from the original greedy-BEN training corpus. Training and validation took 132.6 seconds with one TensorFlow compute thread. Epoch eight was selected; no bot was promoted.

| Complete-auction validation | Parent NLL | Updated NLL | Parent ownership accuracy | Updated accuracy |
|---|---:|---:|---:|---:|
| Bidding training distribution | 1.053569 | 1.052307 | 43.759% | 43.911% |
| Original greedy BEN | 1.053766 | 1.052653 | 43.681% | 43.889% |

These are modest predictive improvements, not evidence of higher IMP performance. An equal-update legacy-only control has not been run, so the gain cannot yet be attributed solely to the added bidding data. Existing BEN validation has also been used for previous model selection. Test labels remain unopened. Exported NumPy logits match TensorFlow within 6.34e-7.

All 40,000 deal identities and contracts were verified against regenerated cards. No overlap with the original 50,000-auction dataset, its 11,200-deal exclusion list, or 9,330 unique existing play families found in 36 frozen/play corpus files.

## Exact DDS cache

Every sampled position stores all legal-card DD results. New PIMC/combined players on this branch enable the shared cache by default. Solver fingerprints, full-position keys, validation before cache access, process-safe SQLite transactions, and explicit actual-search counters protect correctness. Both training and evaluation can populate it.

Four complete deals at eight worlds per decision, with the same move and value traces verified against uncached runs:

| Run | Seconds | Requested worlds | Native solves | Cache hits |
|---|---:|---:|---:|---:|
| uncached | 6.786 | 1,328 | 1,328 | 0 |
| cold_cache | 7.939 | 1,328 | 1,125 | 0 |
| warm_replay | 0.099 | 1,328 | 0 | 1,328 |
| changed_uncached | 6.918 | 1,296 | 1,296 | 0 |
| changed_near_tie | 3.644 | 1,296 | 857 | 256 |

Exact replay: 68.5x faster. Changed near-tie behavior: 1.90x faster; 19.8% of requested worlds hit the pre-existing cache. First-pass persistence was about 17% slower in this small serial measurement. The cache occupied 339,968 bytes after both behaviors. These are illustrative timings, not large-sample throughput or updated-belief results.

Changing the belief network or trajectory may sharply reduce overlap. The implementation never forces new beliefs to use old worlds. Historical logs contain averages and cannot backfill their original individual solves without rerunning. Training boards do not become held-out tests by caching them.

## Deployment

No active frozen experiment was modified. Adopt the cache at the next explicit source/generation boundary and freeze both comparison sides on the same code. The candidate belief requires paired play evaluation before promotion. See [the runbook](../docs/shared_bidding_play_learning.md) for exporter/trainer commands, cache settings, and checkpoint requirements.

## Follow-up prediction test

The frozen epoch-eight candidate has now been evaluated on the reserved prediction test splits. See [the paired, deal-clustered analysis](prediction_test_2026-11-09.md) for cross-entropy significance and separate dummy-visible declarer/defender accuracy. It remains untested for playing strength.
