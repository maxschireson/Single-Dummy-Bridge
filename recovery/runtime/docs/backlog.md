# Backlog and request triage

Reviewed 11 November 2026. The twelve original open items were pull requests,
mostly stacked generation launches. They were not twelve outstanding feature
requests. The cleanup brings the existing Gen6 source onto main and disposes of
historical PRs without deleting their branches or artifacts.

## Remaining PR work

| Priority | Item | Next action | Done when |
| --- | --- | --- | --- |
| Next | [#4: missing bidding-to-belief export tools](https://github.com/maxschireson/Single-Dummy-Bridge/pull/4) | Compare the remaining exporter/trainer/prediction code with current training paths; port only needed pieces from the preserved branch into a new main-based change | Provenance/family split tests pass, or redundancy is documented and the PR is closed |
| Deferred | [#9: nested 16/32/64 scoring](https://github.com/maxschireson/Single-Dummy-Bridge/pull/9) | Decide whether the older prefix-sampling prototype fits current Gen6 weighted sampling; if pursued, port and test explicitly | Prefix decision/RNG parity and physical solve accounting verified; divergent-trajectory limitations stated |

Neither is ready to merge wholesale into main. The old PR bases preserve their
original diffs; do not blindly retarget them and import a whole historical stack.
There is no assigned owner until someone takes the work.

Research branches may contain additional experiments or unfinished ideas; their
existence alone does not put them in the committed backlog. When adopting one,
create one scoped issue with an owner/claim and completion criterion rather than
another indefinite “launch” PR.

## Disposition ledger

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

Historical evidence is linked in [archive](archive/README.md).
Reopen a closed item if there is a concrete remaining requirement; name that
requirement instead of treating old deployment prose as an active task.
