# Dense v5 belief: 100-board follow-up

The new 100 boards did not reproduce the first batch's negative result: they
finished **+13 ± 15 IMPs (one standard error)**. The combined 150 finished
**−13 ± 28 IMPs**, only 0.46 standard errors below zero. This smoke comparison
provides no convincing evidence of a strength difference in either direction.
Integration checks passed; a longer arena trial remains the way to measure
small playing-strength differences. No arena model was changed by this run.

The same selected dense v5 belief model played 100 additional fresh paired deals against 4b. Only belief weights differ: v3 policy and bidding, 32 search layouts, near-tie threshold 0.125, zero exploration, matched contracts and common per-ply random streams are unchanged.

| Batch | Paired boards | Total IMPs | IMP/board ± SE | Mean/SE | Wins / losses / ties |
|---|---:|---:|---:|---:|---:|
| first_50 | 50 | -26 | -0.520 ± 0.480 | -1.08 | 5 / 10 / 35 |
| new_100 | 100 | +13 | +0.130 ± 0.150 | +0.87 | 13 / 13 / 74 |
| combined_150 | 150 | -13 | -0.087 ± 0.189 | -0.46 | 18 / 23 / 109 |

The new 100 are an unchanged-model, fixed-size follow-up. Combined 150 intervals are descriptive because extension was requested after observing the first 50. All inference is by unique paired deal, never by tables or repeated regimes.

All 300 tables completed with 0 failures; 15,600 card actions passed legal replay. The original and follow-up cohorts are family-disjoint. Common/native outputs coincide and are counted once. No reserved test families were used, no model was promoted, and attention remains paused.

The new batch took 5.30 minutes with two workers. Its seed was 202611100742. Collection stopped at 100 additional boards without a performance-based early stop.

Candidate SHA256: `99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a`. Reference SHA256: `b23eb37554a26abb5a5eaa03f547472c489abd00dd6f3c9b0cada96cc46eb7d9`.

[Original smoke test](belief_v5_play_smoke_2026-11-10.md) · [Candidate model and restore instructions](../models/cardplay/gen5-belief-size-loss-2026-11-10)

[All 150 raw paired play records](https://chatgpt.com/library?file_id=libfile_fde3_f-ad8dc761b51c8191b064bc0b9e9dd887_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal)
(owner access required), archive SHA256
`020dd74a820a5418994f3c4019d4cbeacd131ce46e4afa02b9d25ab8c7c07ed3`.
