# DDS costs on ten live mixed-arena boards — 9 November 2026

The current DDS path took **58.63 CPU-seconds**, versus **114.17** for original DDS with the historical Large table: **1.95× faster**. Exact caching is the main gain. A rollback from Pattern to Large with caching produced **58.51 seconds** (0.20% faster), effectively tied on this small sample. No production source or configuration was changed.

The two headline speedups use different baselines: **1.78×** holds Pattern constant (104.23 / 58.63), while **1.95×** compares the historical Large scalar baseline with the current Pattern pipeline (114.17 / 58.63). The 0.2% Large/Pattern near-tie applies to the fully batched-and-cached path, not to original scalar DDS.

## Same-table ablations

All rows below use Pattern tables, so the compact-rank, batching and exact-cache comparisons hold the native table implementation constant. Times are sums over the ten paired boards, including recorded fork tails.

| DDS configuration | CPU seconds | Actual native position solves |
|---|---:|---:|
| Original DDS, scalar, Pattern table | 104.23 | 58,688 |
| Compact ranks, scalar, Pattern | 98.37 | 58,688 |
| Compact ranks + native batches, proofs reset per world | 103.14 | 58,688 |
| Compact ranks + native batches with retained proofs | 101.61 | 58,688 |
| Current: above + cold exact-position cache | 58.63 | 30,554 |

Compact ranks save 5.6% of time. Batching with retention is 3.3% slower than scalar compact DDS in this sample; its net gain is approximately zero. Adding exact caching saves 42.3% of the batched DDS time. Cache hits (13,752) and duplicate-world elimination (14,382) avoid 47.9% of the 58,688 requested solves.

## Historical table rollback

| Table configuration | Original scalar DDS | Compact batched DDS | Current batched + cached path |
|---|---:|---:|---:|
| Pattern (current) | 104.23s | 101.61s | 58.63s |
| Large (historical) | 114.17s | 96.12s | 58.51s |

The table passes were separate serial replay passes, with mode order rotated by board. Both ran beside the live arena. Treat small percentage differences as noisy, especially across passes. All eight configurations agree on every sampled world and every legal-card value.

## What the history shows

- Local source history `d51679839c451e39efba587c6c329b771d3abd38` added all-moves batching and changed the harness from Large (`tt_kind=1`) to Pattern (`tt_kind=2`). This is the concrete broader-pattern table change that was tested above.
- `78e4c386d523810055486f2e2e65ba98c707ed72` subsequently added the persistent exact-position cache. Its keys contain exact card masks, strain, leader and current trick; it does not match abstract shape descriptions.
- The costly generalized proof-replay experiment and abstract cashing/root certificates are not called by this arena. Its native adapter calls the related-layout validator and ordinary `solve_board` with all-legal-move output.
- A source comparison against pinned upstream finds only the compact-rank core changes plus the added related-batch module. The discarded winner-update/cashing-run prototypes are not present in the search path.
- The initial [all-moves self-play report](selfplay_initial_2026-11-08.md) already measured serial 61.072s versus batch 61.805s (0.988×) before persistent caching. Its eight-full-game Large/Pattern check was 53.274s versus 53.215s.
- Larger earlier related-layout gains concerned best-score-only searches, larger batches (up to 1,000 layouts), fixed N/S, and often tighter E/W constraints. Current cardplay scores every legal move across 32 samples; opening leads expose only one hand. Those earlier gains were not established for the current all-moves workload.

## Overhead profile

A separate instrumented replay verified the same answers. Phase shares are approximate and include timer effects; speedups above use uninstrumented timings.

| Current DDS-path phase | Share of profiled CPU |
|---|---:|
| python deal packing | 0.97% |
| python cache validation | 1.21% |
| python cache key | 0.45% |
| cache lookup | 0.26% |
| native validation | 0.08% |
| native reset | 0.46% |
| native search | 95.05% |
| cache write | 0.77% |
| other python and instrumentation | 0.75% |

Native search accounts for about 95%. There is no large newly added validation, reset or SQLite overhead to remove. The current experiment does not support reverting the table switch or the exact cache.

## Workload and verification

Seed 202611090310 selected ten completed records uniformly without replacement from the 800 records present at capture. Board indices: 193, 390, 758, 659, 741, 691, 781, 612, 348, 639.

The trace has 1,834 non-forced DDS decisions and 58,688 sampled positions. We reconstructed observations and sampled hands from the frozen models and original RNG streams, replaying the saved actions. Copied branch prefixes and forced deviations issue no new DDS work. Every mode used identical inputs; all legal-move values agreed, and recomputed means matched the production action records.

The benchmark cache starts empty and accumulates natural reuse across paired tables, forks and these ten boards. It neither reads nor warms the live arena cache. The baseline is upstream revision `0f969b86a4841f438fd0cdff2924c4f2404abf6a`, compiled with C++20, `-O3 -fPIC -pthread` and GCC 14.2, matching the production build script flags. The Large row restores the historical native table choice; all modes use the same current Python packing/validation adapter.

CPU times include DDS search, ctypes packing and cache reads/writes. Belief sampling, policy inference, context construction, output verification and file output are excluded. The profiler is a separate isolated native adapter. This is a ten-board spot check of the DDS portion, not a precise full-arena throughput forecast.

## Reproduction

Code: [build original DDS](../ops/build_stock_dds.py), [replay benchmark](../ops/benchmark_live_dds.py), [cost profiler](../ops/profile_live_dds.py). Full summary: [JSON](dds_live_workload_2026-11-09.json). Raw trace, selected source episodes and runtime libraries are preserved separately in `DDS_Live_Workload_10_Boards_2026-11-09.zip`.

```sh
python ops/build_stock_dds.py --git-repo /path/to/dds --out runs/dds-live-workload-10
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ops/benchmark_live_dds.py \
  --run runs/mixed-fork-25k/g0001-bid40k --out runs/dds-live-workload-10 \
  --upstream runs/dds-live-workload-10/libdds-upstream.so
```

For the Large check, copy `trace.json.gz`, `selection.json` and `upstream-build.json` into a fresh output directory, then use `--tt-kind 1 --modes upstream_scalar batch_retained production_cache`. Every timing pass needs a fresh cache. Profiling uses `ops/profile_live_dds.py --trace-root runs/dds-live-workload-10 --out FRESH_PROFILE_DIRECTORY`.
