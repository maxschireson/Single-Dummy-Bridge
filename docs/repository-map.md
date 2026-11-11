# Repository and research map

## Source, artifacts and deployments

| Branch/location | Role | What to do with it |
| --- | --- | --- |
| `main` | Shared source and contributor documentation | Start development here |
| `codex/launch-gen6-20261111` | Source lineage adopted into main | Preserve for existing deployment references |
| `gh-pages` | Live dashboard | Treat as deployment output with its own publisher |
| `arena-*-feed` | Producer snapshots, replay and recovery data | Read manifests; never merge into main |
| `transfer/*` | Dataset/model handoffs | Read provenance and restore instructions |
| `research/*`, `experiment/*` | Research snapshots and candidates | Inspect results and adoption status before reusing |
| `archive/*` | Preserved excluded/historical observations | Keep for provenance; not active headline data |

The complete [branch inventory](branch-inventory.md) is a discovery snapshot, not
a list of active workers. Branch age/name alone does not establish abandonment.

## Find the right area

| Area | Adopted source or evidence | Separate work worth discovering |
| --- | --- | --- |
| Bidding | [bidding loop](dds_bidding_loop.md), [Gen6 model](../models/bidding/gen6-candidate-2026-11-11/README.md) | `research/bidding-structure-20261110`, `research/gen6-bidding-refresh-20261110`, `transfer/dds-bidding-40000-20261110` |
| Hidden-hand inference | [Gen6 implementation](../bridge_harness/gen6.py), [model releases](../models/cardplay) | `research/joint-auction-belief-20261110`, `research/belief-lab-20261110` |
| Policy | [Gen5 policy](../bridge_harness/policy_v5.py), [release](../models/cardplay/gen5-2026-11-10/README.md) | `research/clean-policy-v5-20261110`, `research/gen6-system-aware-policy-20261111`, `research/gen6-policy-width96-full1513-20261110` |
| Representative sampling | [Gen5R](../bridge_harness/gen5r.py), [Gen6 layout study](../reports/gen6-layout-selection-2026-11-11/README.md) | `experiment/representative-pool-tuning-20261110`, `research/layout-embedding-20261110` |
| DDS and approximations | [binding](../bridge_harness/dds.py), [cache](../bridge_harness/dds_cache.py) | `research/dds-value-quick-20261109`, `research/ddsd-corrector-20261110` |
| Alpha-mu / strategy consistency | [archived result](archive/README.md) | `research/consistent-strategies-alpha-mu`; not adopted into Gen6 |
| Collection/reporting | [operations](operations.md), [recovery](gen6-arena-recovery-20261111.md) | Producer feed branches and `gh-pages` |

“Separate work” means a place to inspect, not a claim that it is trained, winning,
promoted, or still running. Its own frozen report and artifacts must establish that.

## Proposed changes should preserve stable paths

The current source folders already separate engine, operations, models and tests.
The immediate structural fix is a navigable documentation hierarchy, current
source on main, explicit branch roles and a real backlog. Renaming modules such as
`gen5_runtime.py` would touch imports, scripts and frozen source hashes; do it
only as a separately tested migration, not a cosmetic cleanup.

Do not fetch every branch just to get started. Fetch a specific branch only when
needed; the repository's data/model history makes an all-branch clone expensive.
