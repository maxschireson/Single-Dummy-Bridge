# Repository and research map

## Branch families

| Branch/location | Role | What to do with it |
| --- | --- | --- |
| `main` | Shared source and documentation; contains the deployed Gen 7 source | Start development here |
| `feature/genN-*`, `fix/*`, `docs/*` | Scoped source work targeting main | Merge through a PR |
| `codex/*`, `ops/*` | Collector launch and runtime branches | Read manifests; Gen 6 runtime lineage still to integrate ([backlog 1](backlog.md)) |
| `gh-pages` | Live dashboard and feed registry (`arena/gen6-sources.json`) | Its own publisher |
| `arena-genN-*` | Producer feeds: scores, replays, recovery capsules | Never merge into main |
| `transfer/*` | Dataset/model handoffs | Read provenance and restore instructions |
| `box/*`, `fleet/*` | Azure box control and coordination channels | Never merge; see [operations](operations.md#remote-boxes) |
| `research/*`, `experiment/*` | Research snapshots and candidates | Check adoption status before reuse |
| `archive/*` | Preserved excluded observations | Keep for provenance |

The [branch inventory](branch-inventory.md) lists every branch by family with its last
commit. Fetch a branch only when you need it; data branches are large.

## Find the right area

| Area | Adopted source or evidence | Separate work worth discovering |
| --- | --- | --- |
| Bidding | [bidding loop](dds_bidding_loop.md), [Gen 6 bidder](../models/bidding/gen6-candidate-2026-11-11/README.md) | `research/bidding-structure-20261110`, `research/gen6-bidding-refresh-20261110`, `transfer/dds-bidding-40000-20261110` |
| Bidding and carding systems | [system layer](gen8_systems.md): packages in `configs/systems/`, `bridge_harness/systems.py`, `system_nets.py`, `system_bidders.py`, `system_fit.py`; work in progress, not deployed | `research/gen6-system-aware-policy-20261111` (integer-id prototype it replaces) |
| Hidden-hand inference | [Gen 6 implementation](../bridge_harness/gen6.py), [model releases](../models/cardplay) | `research/hand-fit-scorer-v1a-20261111`, `research/joint-auction-belief-20261110`, `research/belief-lab-20261110` |
| Card play: Gen 7 net and tree | [Gen 7 page](generations/gen7/README.md), [player](../bridge_harness/gen7.py), [tree](../bridge_harness/gen7_tree.py), [net](../bridge_harness/gen7_net.py), [policy v4](../models/cardplay/gen7-policy-v4-2026-11-11/README.md) | `transfer/gen7-prototype-20261111`, `transfer/gen7-capture-forks-20261111` |
| Card play: Gen 5 policy (ties only) | [policy_v5.py](../bridge_harness/policy_v5.py), [release](../models/cardplay/gen5-2026-11-10/README.md) | `research/clean-policy-v5-20261110`, `research/gen6-system-aware-policy-20261111` |
| Representative sampling | [Gen5R](../bridge_harness/gen5r.py), [Gen 6 layout study](../reports/gen6-layout-selection-2026-11-11/README.md) | `experiment/representative-pool-tuning-20261110`, `research/layout-embedding-20261110` |
| DDS and approximations | [binding](../bridge_harness/dds.py), [cache](../bridge_harness/dds_cache.py) | `research/dds-value-quick-20261109`, `research/ddsd-corrector-20261110`; the separate `Faster-DDS` repository |
| Alpha-mu / strategy consistency | [archived result](archive/README.md) | `research/consistent-strategies-alpha-mu`; not adopted |
| Collection and arena runtime | [operations](operations.md), [`ops/gen5_runtime.py`](../ops/gen5_runtime.py), [`ops/prepare_gen7_alpha.py`](../ops/prepare_gen7_alpha.py) | Collector lineage branches above; PR #13 |
| Remote boxes | [boxctl](boxctl.md), [`ops/boxctl/`](../ops/boxctl) | `box/*`, `fleet/azure` |
| Results by generation | [generations](generations/README.md), [`scripts/generation_results.py`](../scripts/generation_results.py) | Feeds via the dashboard registry |

“Separate work” is a place to look, not a claim that it is trained, winning, promoted or
running.

## Stable paths

Module names such as `gen5_runtime.py` are cited by frozen manifests and source hashes;
rename them only in a separately tested migration. Generation documents move into
`docs/generations/genN/` at that generation's closeout.
