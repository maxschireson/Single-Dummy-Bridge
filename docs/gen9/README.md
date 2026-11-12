# Gen 9 (design in progress)

> Work in progress on `feature/gen9`. Nothing here is adopted or deployed;
> [current system](../current-system.md) is unchanged.

Gen 9 develops what Gen 8 starts: a model of each player (declared card, matched profiles,
experience from finished boards) used to read their calls and signals, and an arena run as a
population that players join and leave.

| Page | What |
| --- | --- |
| [Architecture](architecture.md) | The overall flow and the interfaces between the areas |
| [Work plan](workplan.md) | Areas, tasks, checkpoints, team size |
| [Arena statistics](arena-statistics.md) | Rating table, field score, admission, the promotion test |
| Area design notes | `bidding.md`, `signals.md`, `arena.md`, `workflow.md`, added by the area leads at checkpoint 1 |

Live task and experiment state: branch `team/gen9` (`STATUS.md`). That branch is the team's
channel and is never merged into source.

**Base.** `feature/gen9` is `main` plus one snapshot commit of the Gen 8 prototype
(`feature/gen8-prototype-20261112` at `ca4fe53`), so Gen 9 work can use the Gen 8 system layer,
rule bidder, early play reading and match runner before Gen 8 is on main. The snapshot is
replaced by Gen 8's real source when that lands; Gen 9 code is kept in new files with small,
named hooks into Gen 8 files so the swap is mechanical.
