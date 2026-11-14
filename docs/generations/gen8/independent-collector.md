# Independent Gen 8 collector (12 November 2026)

This producer follows Max's opened Gen 8 plans on
[`6950784`](https://github.com/maxschireson/Single-Dummy-Bridge/blob/695078457205693f48a24c355681aef47ca21935/docs/gen8_candidate_2026-11-12.md).
It combines their weights in [round8-independent.json](../../../configs/round8-independent.json):

| Pair | Weight | Share |
| --- | ---: | ---: |
| `8s-32~71s-32` | 2 | 25% |
| `8c-32~71s-32` | 1 | 12.5% |
| `8c-32~8s-32` | 1 | 12.5% |
| `8s-32~5RZ32` | 1 | 12.5% |
| `8s-32~1` | 1 | 12.5% |
| `8s-32~ben64` | 1 | 12.5% |
| `8s-32~ben` | 1 | 12.5% |

`8s-32` and `8c-32` use policy v4.1, 32 samples and the standard tree settings.
The difference between them is the Precision r4 bidder. Gen 8 reads play from
trick 1 and uses the released system-aware scorer. BEN's effort remains 16/64,
with pinned original weights and bidders. See the shared notice for the exact
reading factors, system/scorer provenance and experimental limitations.
The former Gen 7.1 comparison/promotion gate is historical: the authorized
Gen 8 deployment supersedes that schedule, without relabelling any results.

The successor is `/workspace/work/gen8-independent`, published on
`arena-gen8-independent-feed`; its immutable manifest is authoritative for
actor settings, artifacts, source hashes, corpus and conditions. The versioned
`/workspace/work/gen7-independent-cutover.json` identifies the current phase
and exact recovery paths. Never race a preparing/draining transition or restart
its intentionally stopped predecessor. The new run uses only unused predecessor
families, excluding the conservative 34,092-family union. It preserves the
34,029-family model-owner authority and the earlier reconstruction as separate,
hash-pinned provenance. No training takes place here.

Common auctions retain the Gen 6 house bidder; native auctions use each side's
own bidder. Records retain their `systems:NS|EW` auction labels and bidder
identities. The exporter carries that system label into replay shards and
reports common play, native total and paired bidding differences. The recovery
capsule includes system/rule JSON files; the manifest pins the rule bidder's
external trick-estimate bytes so resume fails if those change. Gap forks remain
2 per band `[.125, .5]`, CPU share 1.5, and tie-audit probability .5. BEN gets
neither type of fork. Fork tables and auction regimes are never new families.

Validation and final cutover evidence are stored in the run's
`artifacts/validation` and source/feed recovery metadata. Tests cover the launch,
system binding, early play, rule bidder, and external-estimate tamper rejection.
Real-model preflight checks legal replay, swapped rooms, native/common auctions,
searched decision arithmetic, tree budgets and nonzero gap capture; the BEN
preflights require the actual configured retained samples. This producer's
publication and dashboard registration are checked separately from prototype
benchmarks. Preflight episodes are not published as arena observations.

Only this producer is changed. The repository-wide generation cleanup and main
integration remain separate from this host's cutover; other feeds and collectors
keep their owners and exact historical records. No new phase-2 or training
program is opened by this handoff. The hourly instruction watcher remains active.
