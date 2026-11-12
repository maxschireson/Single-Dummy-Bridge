# Generations

One page per generation: what the bot was, when it ran, its pooled results, its feeds and
what it handed on. A generation's page is finished at its closeout
([procedure](../generation-cleanup.md)).

| Gen | Arena dates (2026, UTC) | Main change | Status | Page |
| --- | --- | --- | --- | --- |
| 8 | — | Bidding systems and carding agreements as data; MoE-style nets | WIP on `feature/gen8-systems-20261111` | [guide on branch](https://github.com/maxschireson/Single-Dummy-Bridge/blob/feature/gen8-systems-20261111/docs/gen8_systems.md) |
| 7 | 12 Nov – | Policy net v4 + tree search at tricks 3–6 over Gen 6 fast | Phase 1 collecting | [gen7](gen7/README.md) |
| 6 | 11 Nov – 12 Nov | Graded-alternatives bidder, lead belief net, hand-fit scorer | Closed 12 Nov | [gen6](gen6/README.md) |
| 5 / 5R / 5RZ | 10 Nov – 11 Nov | Rebuilt networks; representative layouts (5R); policy ties-only (5RZ) | Closed | [gen5](gen5/README.md) |
| 1–4 | 8 Nov – 10 Nov | Harness, PIMC, first belief/policy nets, Gen 4 components | Closed | [historical reading guide](../archive/README.md) |

Results are pooled from the dashboard registry with
[`scripts/generation_results.py`](../../scripts/generation_results.py). The live view is the
[arena](https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=latest).
