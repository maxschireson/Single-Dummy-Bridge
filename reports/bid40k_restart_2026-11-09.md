# Shared 40k bidder and restarted mixed arena — 9 November 2026

The user adopted the new bidding network and requested that **all current and
historical bots share the latest bidding for now**. The restarted arena uses
the exact reviewed 40,000-pair bidder in all seats. Candidate and reference
play identical frozen auctions; this campaign promotes play versions without
trying to separate a bidding contribution.

## Bidder and verification

The frozen actor follows 40,000 training pairs and 314 PPO updates. A separate
5,000-pair greedy DDS review produced +313 IMPs (+0.0626 per board), with a
descriptive 95% interval [0.00681, 0.11839]: 172 wins, 156 losses, 4,672 ties.
This is positive held-out DDS evidence, not a demonstrated real-cardplay
bidding gain or a claim of sequentially adjusted significance. Adoption is
explicitly user-authorized.

The 1,524,776-parameter deployment exports only the actor, without its training
critic. Reloaded probabilities match the reviewed training actor exactly on
256 real public auction observations; no legal greedy choices changed. BEN's
batch bidding interface also matches its scalar path on all eight preparation
checks. Search, DDS bidding calls and rescue are disabled.

- Source review snapshot SHA256:
  `51cd49e12a28995006ae12a7fae5b4088410d59a6523b70cdfcac62f6b8e98b4`.
- Deployed actor SHA256:
  `680470163f198802a5522d90f7ae4a1394fea3ca02ca4398f65c14eccb4934b3`.
- Restart manifest identity:
  `09c13570763e5ba836424c9992579a0bb400e5e5e7ca9caae4c138b921654a73`.

All 25,200 prepared deals were re-auctioned. Relative to the original bidder,
2,535 auctions and 1,948 contracts or declarers changed. The cohort contains
25,000 distinct contracted boards. All four roster entries pin the same actor
hash; their belief and play artifacts retain their intended differences.

## Play campaign and recovery

The newest candidate uses the new public-play belief and auction-aware policy
described in [the component report](v2_network_results_2026-11-09.md). The
historical mixture, 32 PIMC samples, paired full boards, independent random
policy audits, train/validation family split, and 25k training boundary are
unchanged. The next policy fit uses audited IMP contrasts; the current policy
is still the predictive warm-start.

- Checkout: `/workspace/scratch/a1f2b806f0ac/bridge-arena`.
- Pointer: `runs/mixed-fork-25k/current.json`.
- Restart: `runs/mixed-fork-25k/g0001-bid40k`.
- Permanent historical STOP: `runs/mixed-fork-25k/g0001`, at 351 pairs,
  2,090 nonidentical audited deviations and +24 IMPs. Never resume it or pool
  its outcomes with the restart.
- Shared registry: `runs/mixed-fork-25k/bidding-current.json`.
- Boundary implementation: `ops/finish_mixed_generation_v3.py`, independently
  pinned in `training-config.json`. It binds every successor roster entry to
  the shared latest bidder before freezing the next auctions.

Use `ops/supervise_mixed.py supervise` for recovery, following the active
pointer and checking both OS-owned locks first. Never delete lock files.
Completed episodes and receipts are immutable. The boundary retains model and
Adam state, trains both play components and prepares the next 50k generation
even if the match is inconclusive. The shared bidder itself remains frozen
within each generation.

The operational monitor for this chat runs at the top of the hour. Independent
monitor schedules remain unchanged. The old 8,315-board v2 collection and
150-board fork pilot remain stopped.

The deployable actor and its validation/export record are checked in under
[`models/bidding/dds-40000`](../models/bidding/dds-40000). Eight workers are now
active. A short sequential production comparison gave about 1,635 paired
boards/hour with four workers (38 boards in 83.68 seconds), versus roughly
2,940/hour early in the eight-worker trial (44 in 53.88 seconds). This is an
operational throughput estimate over different deals, not a controlled speed
benchmark. Each paired board includes two full tables plus random forks.

Resume with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -u ops/supervise_mixed.py supervise \
  --run runs/mixed-fork-25k/g0001-bid40k --seconds 240 --workers 8
```
