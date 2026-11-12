# Generations

One page per generation: what the bot was, when it ran, its pooled results, its feeds and
what it handed on. A generation's page is finished at its closeout
([procedure](../generation-cleanup.md)).

| Gen | Arena dates (2026, UTC) | Main change | Status | Page |
| --- | --- | --- | --- | --- |
| 8 | 12 Nov – | The play read from trick 1 at full weight, opponents' plays scaled by type; a second, declared bidding system (the project's rule bidder) and a hand-fit scorer that reads each side's calls by its system | Authorized 12 Nov 15:32 UTC; collecting from 16:30 on `feature/gen8-prototype-20261112` at `792c4cb`, not yet on main (the cleanup has not been run) | [notice](../gen8_candidate_2026-11-12.md) |
| 7 | 12 Nov – | Policy net v4 + tree search at tricks 3–6 over Gen 6 fast | Phase 1 collecting | [gen7](gen7/README.md) |
| 6 | 11 Nov – 12 Nov | Graded-alternatives bidder, lead belief net, hand-fit scorer | Closed 12 Nov | [gen6](gen6/README.md) |
| 5 / 5R / 5RZ | 10 Nov – 11 Nov | Rebuilt networks; representative layouts (5R); policy ties-only (5RZ) | Closed | [gen5](gen5/README.md) |
| 1–4 | 8 Nov – 10 Nov | Harness, PIMC, first belief/policy nets, Gen 4 components | Closed | [historical reading guide](../archive/README.md) |

Results are pooled from the dashboard registry with
[`scripts/generation_results.py`](../../scripts/generation_results.py). The live view is the
[arena](https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=latest).
