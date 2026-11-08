# Validation — 2026-11-08

The implementation was built and exercised on Linux x86_64 using Python 3.12.14. The Mac build path is included but was not executed on Mac hardware. No GPU was used by the harness; the live BEN server used CPU TensorFlow. These timings are observations from this workspace, not predictions for a Mac Studio.

## Completed matches

| Run | Samples per decision | Paired boards | Full games | Failures | Candidate IMP/board | Corpus |
|---|---:|---:|---:|---:|---:|---|
| Broad declarer | 2 | 1000 | 2000 | 0 | 1.999 | 1,000 independent synthetic deals |
| Related defence | 2 | 1000 | 2000 | 0 | 1.214 | 10 families × 100 layouts |
| Broad declarer, larger sample | 32 | 24 | 48 | 0 | 3.167 | 24 synthetic deals |
| Full partnership vs random | 8 | 40 | 80 | 0 | 9.150 | 40 synthetic deals |
| Full partnership vs live BEN | 8 | 4 | 8 | 0 | -3.750 | 4 BEN-generated auctions |

**Total: 2,068 successful paired boards, 4,136 full games, zero recorded failures.** All completed records were replayed from their logged cards and produced the same legal trajectories and final scores.

The broad and related 1,000-pair runs took approximately 233 and 201 seconds respectively, including worker startup and logging. The 40-pair partnership run took 68 seconds; the four-pair live BEN match took 133 seconds after bidding. Some runs overlapped on this machine. These are different workloads, not self-play training throughput estimates.

The two-sample runs primarily test reliability. The 32-sample run is much smaller and uses a different deal subset; differences between their aggregate scores are not an estimate of the benefit from extra samples. Greedy and random are intentionally weak opponents. Four BEN deals are far too few for a playing-strength conclusion. Synthetic-auction results should not be generalized to tournament bridge.

## Observed decision timings

Times include forced decisions (which skip DDS). They exclude fixed opening leads, which are measured separately in the records.

| Run / player | Mean ms | p95 ms | DDS calls |
|---|---:|---:|---:|
| Broad declarer / pimc | 5.44 | 25.62 | 41444 |
| Related defence / pimc | 4.46 | 22.57 | 39178 |
| Broad declarer, larger sample / pimc | 64.75 | 321.99 | 16448 |
| Full partnership vs random / pimc | 31.25 | 163.04 | 13744 |
| Full partnership vs live BEN / ben | 605.41 | 1992.17 | 0 |
| Full partnership vs live BEN / pimc | 30.70 | 118.89 | 1312 |

## Correctness and integration checks

- 23 unit/integration tests passed in the original experiment; the full test log is omitted from this source upload.
- DDS card values checked against an independent exhaustive minimax implementation on 300 late positions, spanning all five strains and every current-trick offset.
- Sampler tested throughout 15 complete games, including voids and opening-lead information; a small constrained state also received a 6,000-draw uniformity check.
- Duplicate scoring examples include doubles, redoubles, vulnerability, undertrick escalations, games, slams, and IMP threshold boundaries.
- Same-player comparisons produce identical decisions and zero paired difference in all three match modes.
- Hidden-layout changes with the same visible information produce identical observations. BEN requests contain only the acting controller’s original hand and legally visible dummy.
- Illegal actions are recorded as errors; the hard subprocess deadline is tested.
- Actual BEN generated all four test auctions through individual `/bid` calls, then participated in eight complete games through `/lead` and `/play`. The exact portable configuration, revision, and compact match report are retained under `reports/ben_live/`. Request/response records and the server log are omitted from this source upload.
- 1,000-board JSONL → PBN → JSONL roundtrip preserved all represented metadata.
- Completed-run resume left the 1,000-board result count unchanged. A branch from ply 12 completed and replayed successfully; the generated branch trace is omitted from this source upload.

## Boundaries

This is a baseline engine and research harness. It does not train models, infer opponent skill, condition sampling on bids or soft play evidence, search information-consistent strategies, reuse proofs across related worlds, or cache small end positions. No solver acceleration claim is made.

BEN was tested at commit `9b5f43104aeac713a80b73513f2f2d6daf9f8769`, with TensorFlow 2.21.0 / Keras 3.15.1, and BBA, BGA PIMC, ACE and SuitC disabled. BEN configuration/model changes can change behavior. The local Python package uses only the standard library plus its compiled DDS binding. DDS provenance is in `vendor/DDS_SOURCE.md`; harness source checksums are in `SOURCE_MANIFEST.json`.
