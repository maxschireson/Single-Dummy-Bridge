# First batch-PIMC self-play data collection — 8 November 2026

The bot now evaluates sampled worlds through an all-legal-moves batch DDS
binding. A self-play collector randomizes near-equal moves and records separate
policy-return and hidden-ownership targets. The first small belief-model training was authorized only after the complete
10,000-deal audit passed. No playing-strength improvement is claimed.

## Implemented and checked

- Compact relative ranks and the related-layout code from Faster-DDS commit
  `2850a1b686e3e865d037488082fac32ffec93beb`, retaining upstream Apache-2.0 notices.
- All-move batching with whole-batch validation, per-decision TT lifetime,
  Pattern transposition tables, and support for both declarer and defender
  information sets. Scalar root certificates are not used as move certificates.
- Uniform exploration within 0.125 estimated tricks of the best PIMC move,
  recording all candidate values, Monte Carlo errors and behavior probabilities.
- Full-game self play with bounded parallelism, process deadlines, replay
  validation, atomic compressed game shards and strict resume checks.
- Observation-only inputs, separate true hidden-owner/suit-count labels and
  outcome-based policy targets, grouped splits, and optional NPZ export.
- All 30 tests passed, including 1,000 batch/cold all-move comparisons covering
  all five strains, all partial-trick offsets and 13/10/7/3/1-card starts;
  seeded serial/batch full-game agreement; hidden-information invariance;
  whole-batch rejection before searching; and training mask/export validation.

## Pilot

24 complete independent deals, four workers, 32 sampled worlds per non-forced
decision, seed 20261108 for deals and 9173 for choices. Every seat used PIMC with
expected-tricks utility. This used synthetic contracts and auctions.

| Quantity | Observed |
|---|---:|
| Complete games / failures | 24 / 0 |
| Pre-action training rows | 1,248 |
| Non-forced decisions | 995 |
| Decisions with multiple eligible choices | 786 |
| Hidden remaining-card ownership labels | 16,528 |
| Sampled-world solves | 31,840 |
| Elapsed wall time | 37.15 s |
| Games per second, aggregate | 0.646 |
| Mean game latency while four ran concurrently | 5.86 s |
| Moves selected below the estimated PIMC maximum | 129 |
| Mean selected PIMC gap, all non-forced moves | 0.00952 tricks |

The last statistic measures exploration under the PIMC estimator, not the true
loss from exploration. Early pilot timing overlapped the test suite; use the
larger completed run for planning. Resume of this completed pilot scheduled no
new games and preserved all 24 records.

## Initial all-moves batch benchmark

141 non-forced observations from ten independently generated deals, at 13, 10,
7 and 4 remaining tricks, all partial-trick offsets. Each used 32 sampled worlds;
two passes alternated serial/batch order, identical seeds, sampling and utility.
Both variants used the compact-rank binary and Pattern table. Timings include
sampling, FFI conversion, validation, search and aggregation. This first pass
overlapped the larger self-play workload, so small differences are noisy.

| Remaining tricks | Serial seconds | Batch seconds | Serial / batch |
|---|---:|---:|---:|
| 13 | 71.596 | 75.113 | 0.953× |
| 10 | 3.977 | 3.469 | 1.146× |
| 7 | 0.667 | 0.605 | 1.103× |
| 4 | 0.333 | 0.329 | 1.010× |
| Total | 76.572 | 79.516 | 0.963× |

All card values and chosen moves agreed. This does **not** establish an overall
batch speedup for all-moves PIMC. The earlier best-score-only batch gains do not
automatically transfer. Opening lead knows only one hand and accounted for
44.70 serial / 47.97 batch seconds; those worlds are less closely related than
the two-visible-hand positions. After the opening lead, reuse reduced node
counts, but lookup/validation overhead and the largest early searches limited
the net timing gain. The cold path remains available with `--serial-dds`.

## Completed 1,000-game checkpoint

The 1,000 independent full games at 32 samples completed with **zero failures**.
Every game was replay-validated. CPU: eight worker processes on the available
AMD EPYC 9V74 virtual CPUs, GCC 14.2, Python stdlib collector, C++20 `-O3` build.
The overall time includes overlap with the explicitly noted profiling work.

| Quantity | Observed |
|---|---:|
| Elapsed wall time | 890.99 s (14.85 minutes) |
| Aggregate throughput | 1.122 games/second |
| Pre-action rows | 52,000 |
| Non-forced policy decisions | 41,044 |
| Multiple-eligible-action selector rows | 32,469 |
| Hidden-card ownership labels | 689,195 |
| Sampled-world DDS solves | 1,313,408 |
| Train / validation / test deals | 800 / 99 / 101 |
| Train / validation / test rows | 41,600 / 5,148 / 5,252 |
| Mean / 95th-percentile concurrent game latency | 6.92 / 13.21 s |
| Mean sampled PIMC gap of chosen non-forced move | 0.00902 tricks |

All three NPZ splits were exported and checked for legal chosen actions,
normalized behavior probabilities and owner-label compatibility with input
support masks. A complete archive, including replay records and input/target
arrays, was saved as `Bridge_Selfplay_1000_2026-11-08.zip`.

## Confirmation timing without concurrent self play

Repeating the identical 141-position, two-pass benchmark after local self play
finished gave serial **61.072 s**, batch **61.805 s**, or **0.988×** overall.
By remaining tricks: 13 → 0.983×, 10 → 1.067×, 7 → 1.137×, 4 → 1.001×.
Again, no move/value differences. The honest conclusion is approximate overall
parity with some later-position gains, not a demonstrated full-game speedup.

An additional eight-full-game comparison of the Large and Pattern native TT
implementations used identical 32-sample self-play choices and agreed on all
values/actions. CPU time was 53.274 vs 53.215 s respectively; this small test
does not justify changing the table choice for the larger collection.

## Completed 10,000-game collection

The full cross-chunk audit passed on 8 November 2026, **before any model fit**.
All ten chunks contain 1,000 independent complete games each, with **zero
failures**, no repeated original deals and no cross-split groups. Exact legal
pre-action observations, complete replay, true hidden-card ownership, behavior
probabilities and outcomes passed `scripts/audit_selfplay.py`.

| Quantity | Audited total |
|---|---:|
| Independent complete deals / failures | 10,000 / 0 |
| Pre-action rows | 520,000 |
| Non-forced policy decisions | 410,228 |
| Multiple-eligible-action selector rows | 324,067 |
| Hidden-card ownership labels | 6,890,593 |
| Train / validation / test deals | 7,993 / 1,008 / 999 |
| Train / validation / test rows | 415,636 / 52,416 / 51,948 |

[GitHub Actions run 42491138682](https://github.com/maxschireson/Single-Dummy-Bridge/actions/runs/42491138682)
completed all nine additional chunks successfully. Individual four-worker
collection chunks took 1,901.57–2,708.33 seconds (0.369–0.526 games/second).
The hosted workflow elapsed 79 minutes 40 seconds including queues, build,
exports and uploads; 9,000 deals over that interval is 1.88 deals/second across
jobs. This is parallel collection throughput, not a DDS kernel speedup.
Chunk 0's separate eight-worker measurement remains documented above.

All games retain batch PIMC, 32 worlds per non-forced decision, expected-tricks
objective and uniform selection within 0.125 estimated tricks. NPZ files remain
sharded with their original grouped splits. Inputs and privileged labels remain
separate. Synthetic contracts/auctions cannot teach real bidding inference, and
10,000 deals remain 10,000 independent units despite 520,000 correlated positions.

The complete `Bridge_Selfplay_10000_2026-11-08.zip` contains every replay/training
episode, 30 split NPZ files, manifests, summaries, audit, schema, source provenance,
workflow job timings and per-file SHA256 checksums. Archive SHA256:
`505635aeb0e53fbfaef87ab785e500d0148153234aca37d651d99b0301598857`.
[Download the complete dataset](https://chatgpt.com/library?file_id=libfile_fde3_f-0d1514d017cc8191b179f535766591ab_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).
No records, logs, binaries or model weights are committed to Git.

Source: implementation `d51679839c451e39efba587c6c329b771d3abd38`, audit source
`74de27d06bdbc43cf149d423b1e5bc8a877f66d4`, collection workflow
`6efcc7cee4b490978812bc63006da7548ce83bd7`; audited against current research
source `7b2c17a6cf0556bc0730b9bbec536ea55b6b58da` (audit code unchanged).

## First learning experiment and hardware planning

At the measured local rate, 10,000 games take about 2.5 hours and 30,000 about
7.4 hours on this worker allocation. Parallel independent hosted jobs shorten
elapsed collection time; this is not a solver speed improvement.

For Max's 18-core M5 Max MacBook Pro and discussed 36-core M5 Ultra Studio, a
rough unmeasured estimate is 2–4 and 4–8 games/second respectively at this same
32-sample workload. That implies about 40–85 minutes and 20–45 minutes per
10,000 games. These are engineering extrapolations, not Apple DDS measurements;
calibrate with a 100-game local run. CPU resources and sustained thermals matter
more than GPU size or 512 GB capacity for this collector. Apple configuration
reference: https://www.apple.com/mac/compare/?modelList=MacBook-Pro-16-M5-Max%2CMac-Studio-M5-Ultra

As engineering starting budgets, 10,000–30,000 independent games should be a
reasonable first belief-model experiment (roughly 0.5–1.6 million positions).
A learned selector may need 50,000–200,000 games because selected-action returns
are much noisier than ownership labels, and many PIMC ties are equivalent.
These are hypotheses to test with learning curves, not demonstrated sample
complexities. The first 1,000 games mainly validate the pipeline.

Use a small model, mask hard-known ownership, compare beliefs with the existing
constrained sampler, and evaluate belief-only, selector-only and combined bots
at equal wall time on fresh paired deals. Report tricks/board and strength gain
per time doubling, alongside uncertainty grouped by deal/family. Self-play
training alone does not demonstrate improvement against a frozen opponent.

See [usage, schema and leakage controls](../docs/SELFPLAY.md). Bulk records,
arrays, binaries and logs are excluded from Git; only code, tests and compact
reports are versioned. DDS's underlying proof machinery is credited in
[CREDITS.md](../CREDITS.md) and [vendor provenance](../vendor/DDS_SOURCE.md).
