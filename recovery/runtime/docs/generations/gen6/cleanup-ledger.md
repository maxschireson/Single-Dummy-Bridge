# Gen 6 cleanup ledger (11 November 2026)

Moved from `docs/backlog.md` at the Gen 6 closeout. The 11 November cleanup brought the Gen 6 source onto main and disposed of the twelve open PRs, which were mostly stacked generation launches. Open items that survived it are in the [backlog](../../backlog.md).

## PR dispositions

“Contained” below means exact commit ancestry, not an assumption based on title.
“Historical” explicitly does not claim every branch-only file was integrated.

| PR | Disposition | Evidence / retained work |
| --- | --- | --- |
| [#1](https://github.com/maxschireson/Single-Dummy-Bridge/pull/1) | Archive research | The 1,000-board report says the alpha-mu/rollout variants did not earn their extra compute. Preserve branch and negative results; do not integrate as current engine. |
| [#2](https://github.com/maxschireson/Single-Dummy-Bridge/pull/2) | Close historical launch | Most lineage is in Gen6; the two unique commits are the old bounded collection supervisor and its test. Gen6 has its own watchdog. Preserve the old launcher for reproducing that run. |
| [#3](https://github.com/maxschireson/Single-Dummy-Bridge/pull/3) | Close completed milestone | Bidding loop lineage is in Gen6. The unique tail is the 40k confirmation report; preserve and index that evidence. |
| [#4](https://github.com/maxschireson/Single-Dummy-Bridge/pull/4) | Keep draft: scoped follow-up | DDS binding, cache and cache test are byte-identical to Gen6, but bidding_belief_data.py and exporter/trainer/prediction tools are absent. Review/port only that missing work against main. |
| [#5](https://github.com/maxschireson/Single-Dummy-Bridge/pull/5) | Close completed historical training | Continuation report records completion and promotion. continue_large_belief.py is identical in Gen6; old promotion script and reports remain preserved on the branch. Do not replay a historical promotion. |
| [#6](https://github.com/maxschireson/Single-Dummy-Bridge/pull/6) | Close: contained in Gen6 | Exact PR head is an ancestor of the adopted Gen6 source. |
| [#7](https://github.com/maxschireson/Single-Dummy-Bridge/pull/7) | Close: contained in Gen6 | Exact PR head is an ancestor. Historical IMP-policy work is not a recommendation to replace the current retained Gen5 policy. |
| [#8](https://github.com/maxschireson/Single-Dummy-Bridge/pull/8) | Close: contained in Gen6 | Exact PR head is an ancestor; this generation's launch is historical. |
| [#9](https://github.com/maxschireson/Single-Dummy-Bridge/pull/9) | Keep draft: deferred prototype | All seven unique commits remain outside Gen6. Prefix scoring at a shared state does not supply divergent trajectories, and Gen6 weighted layouts need a separate compatibility decision. |
| [#10](https://github.com/maxschireson/Single-Dummy-Bridge/pull/10) | Close: contained in Gen6 | Exact PR head is an ancestor; Gen4 recovery is historical. |
| [#11](https://github.com/maxschireson/Single-Dummy-Bridge/pull/11) | Close: contained in Gen6 | Exact PR head is an ancestor; its BEN32 preparation is superseded by the current BEN16 plan. |
| [#12](https://github.com/maxschireson/Single-Dummy-Bridge/pull/12) | Close: contained in Gen6 | Exact PR head is an ancestor; Gen5 launch is historical. |

## Review evidence

Checks compared the original PR heads with Gen6
`b34a40fd7829ebeaaf96b86a424289e3f938a868`.
Heads for #6, #7, #8, #10, #11 and #12 are ancestors. For #1, #2, #3, #4,
#5 and #9, the unique tails were inspected; the reasons above preserve that
distinction. [Machine-readable ledger](pr-triage-2026-11-11.json) records head SHAs.

Historical evidence is linked in [archive](../../archive/README.md).
Reopen a closed item if there is a concrete remaining requirement; name that
requirement instead of treating old deployment prose as an active task.
