# First batch-PIMC self-play data collection — 8 November 2026

The bot now evaluates sampled worlds through an all-legal-moves batch DDS
binding. A self-play collector randomizes near-equal moves and records separate
policy-return and hidden-ownership targets. No neural net has been trained and
no playing-strength improvement is claimed.

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

## Larger run and next learning experiment

A 1,000-deal, 32-sample run with eight workers and deal seed 20261110 was started
after the pilot. Its completed results will be added to this report when the
run finishes. Use measured throughput, not a speculative solver-speed factor,
to estimate data collection time.

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
