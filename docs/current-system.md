# Current system

Checked 11 November 2026 against Gen6 source commit
`b34a40fd7829ebeaaf96b86a424289e3f938a868`, incorporated into `main`
by the repository cleanup. This is a configuration snapshot, not a claim that
a process is alive now.

## Source of truth

| Question | Authority |
| --- | --- |
| What should new development start from? | `main` |
| What should the primary Gen6 cohort play? | [round6-codex.json](../configs/round6-codex.json) |
| What should other producers coordinate against? | [gen6-active-mix.json](../configs/gen6-active-mix.json) |
| What did one run actually execute? | Its immutable manifest, actor/model hashes and frozen runtime |
| Where are published scores? | [Arena dashboard](https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=latest), with pinned feed revisions |
| Is a worker alive? | Fresh heartbeat, process/lock inspection and publisher status on its owning host |

The older [architecture launch document](gen6_architecture_2026-11-11.md)
explains the implementation but its initial “not launched” state and 32/64/256
defaults are historical. [Recovery documentation](gen6-arena-recovery-20261111.md)
and the active configuration supersede those deployment details.

## Active actors

| Actor | Early samples | Full compatible-layout listing begins | Late solve ceiling | Policy |
| --- | ---: | ---: | ---: | --- |
| `6-32` — Gen6 fast | 32 | Trick 7 | 256 | PIMC ties only |
| `6-256` — Gen6 medium | 256 | Trick 6 | 256 | PIMC ties only |

The automatic 64-sample middle phase is disabled in these active profiles.
Both use the Gen6 candidate bidder, lead-belief net, hand-fit scorer and retained
Gen5 policy. “Gen5 (32)” in this cohort is the frozen `5RZ32` actor, not plain Gen5.

| Match | Scheduled share |
| --- | ---: |
| Fast vs 5RZ32 | 40% |
| Fast vs medium | 15% |
| **Medium vs BEN16** | **15%** |
| Fast vs Gen3 | 10% |
| Fast vs Gen2 | 10% |
| Fast vs Gen1 | 10% |

Common auctions use the Gen6 bidder; native auctions use each partnership's bidder.
Swapped partnerships and both conditions are retained. Short completed windows can
differ from the scheduled proportions.

## Models and evidence

- Bidder: [Gen6 candidate release](../models/bidding/gen6-candidate-2026-11-11/README.md).
- Lead belief: [joint auction lead release](../models/cardplay/joint-auction-belief-lead-v0-2026-11-10/README.md).
- Hand-fit scorer: [v0 release](../models/cardplay/hand-fit-scorer-v0-2026-11-11/README.md).
- Policy: [Gen5 release](../models/cardplay/gen5-2026-11-10/README.md).
- Exact deployed model hashes: [recovery document](gen6-arena-recovery-20261111.md) and frozen run artifacts.

Prediction validation, double-dummy proxy comparisons and paired played IMPs answer
different questions. Preserve those distinctions and the evaluation population.
The initial architecture note explicitly includes some evidence whose raw records
were not pushed; do not upgrade those claims to reproduced repository results.

## Publication and history

Current producer feeds are `arena-gen6-codex-feed`,
`arena-gen6-medium-ben-feed` and `arena-gen6-chatgpt-feed`.
Compatible earlier records from `arena-gen6-independent-feed` may contribute to
the aggregate. This does not imply its worker is still active.
The 13 accidental fast-vs-BEN records have a separate archive and are excluded
from dashboard scores, rates and timing; preserve them for provenance/training.

See [operations](operations.md) for recovery and [branch inventory](branch-inventory.md)
for older feeds and research.
