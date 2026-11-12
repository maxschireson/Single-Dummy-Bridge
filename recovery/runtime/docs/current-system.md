# Current system

Snapshot of 12 November 2026 ~03:05 UTC, written at the Gen 6 → Gen 7 cleanup. It describes
what is authorized, not whether a process is alive; check fresh heartbeats and feed heads.

## Generation in the arena: Gen 7, phase 1

| Question | Authority |
| --- | --- |
| What is authorized? | Gen 7 phase 1 ([notice](gen7_candidate_2026-11-11.md)); since 12 November 04:09 UTC without its Gen 5 and Gen 1 pairs, whose deals go to `7s-32` self-play ([notice](gen7_selfplay_2026-11-12.md), source on `feature/gen7-selfplay-20261112`). Phase 2 is not |
| Which source do collectors run? | `fe382f9b` (from `feature/gen7-candidate-20261111`, merged into main at this cleanup) |
| Which plan? | [`round7-candidate-phase1.json`](../configs/round7-candidate-phase1.json), or its `-nonben` / `-ben` halves on machines without / with BEN servers |
| What did one run actually execute? | Its immutable manifest, actor/model hashes and frozen runtime |
| Where are published scores? | [Arena](https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=latest); only feeds in `gh-pages:arena/gen6-sources.json` are counted |
| Who has which Azure box? | `box/coordination` (allocation table) and `fleet/azure` (`STATUS.md`) |
| Where does new development start? | `main` |

## Actors in phase 1

| Actor | What it is |
| --- | --- |
| `7s-32` Gen 7 standard | `6-32` plus `engine: gen7`, policy net v4, play-weighted layouts from trick 7, tree search at tricks 3–6 (margin 0.25, trust 0.3, path 0.5, 3 tricks) |
| `6-32` Gen 6 fast | Unchanged from Gen 6 |
| `5RZ32` Gen 5 (32) | Frozen Gen 5RZ actor |
| `1` Gen 1 | Frozen |
| `ben`, `ben64` | BEN at 16 and 64 samples (separate runtime) |

| Pair | Weight | Purpose |
| --- | ---: | --- |
| `7s-32~6-32` | 1 | Generation comparison |
| `7s-32~ben64`, `7s-32~ben` | 1 each | BEN anchors |
| `7s-32~5RZ32`, `7s-32~1` | 1 each | Older anchors |

Target 2,000 boards per pair over all collectors. Common auctions use the Gen 6 bidder at
all four seats; native auctions use each side's bidder. `7s-32~6-32` keeps tie audits, gap
forks and tree audits. Details and the full settings: [Gen 7 page](generations/gen7/README.md).

## Still running from Gen 6

Some producers were still publishing Gen 6 fast self-play at this snapshot
([list](generations/gen6/README.md#feeds)). Moving each producer to Gen 7 is Max's
instruction to that producer. Gen 6's scored results are closed:
[Gen 6 results](generations/gen6/README.md#results).

## Not authorized or not on main

- Gen 7 phase 2 (self-play volume with the fast bot). The self-play regime, the gen7 engine and
  the capture port are in one runtime on `feature/gen7-selfplay-20261112`, which is not on main;
  [backlog item 1](backlog.md).
- Gen 8 systems layer: WIP on `feature/gen8-systems-20261111`.
- Hand-fit scorer v1a: packaged on `research/hand-fit-scorer-v1a-20261111`; phase 1 uses v0.

## Evidence rules

Prediction validation, double-dummy proxy comparisons and paired played IMPs answer
different questions. Keep the evaluation population with any number. Self-play has no
strength estimate. Intervals on the dashboard are unadjusted for repeated looks.
