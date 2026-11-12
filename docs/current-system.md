# Current system

Snapshot of 12 November 2026 ~18:10 UTC, written at the Gen 7 → Gen 8 cleanup. It describes
what is authorized, not whether a process is alive; check fresh heartbeats and feed heads.

## Generation in the arena: Gen 8

| Question | Authority |
| --- | --- |
| What is authorized? | Gen 8 ([notice](gen8_candidate_2026-11-12.md)): Max, 12 November 15:32 UTC, "Go ahead"; 15:33, every machine on Gen 7 work that is not on Gen 9 or another future project switches to the Gen 8 arena; 16:11, to the operator, the arena switches, with Gen 7.1 kept as the Gen 7 family's representative. Both plans are open; nothing is waiting behind them |
| Which source do collectors run? | `792c4cb` (`feature/gen8-prototype-20261112`, the commit that opened the plans) on Azure and Codex; `c8a138f` (`ops/gen8-19bbdce5-20261112`) and `6776c28` (`codex/gen8-independent-20261112`), which are that commit plus one collector's own plan and preparation changes. All three merged into main at this cleanup |
| Which plan? | [`round8-candidate.json`](../configs/round8-candidate.json) (the main mix); [`round8-candidate-ben.json`](../configs/round8-candidate-ben.json) on machines with BEN's servers; the 19bbdce5 and independent collectors use their own copies, [`round8-19bbdce5.json`](../configs/round8-19bbdce5.json) and [`round8-independent.json`](../configs/round8-independent.json) |
| Which deals may a cohort play? | Never a deal family a bot's net was trained on (Max, 12 November 15:50 UTC, quoted in both plans). The plans refuse to be prepared without `--exclude-families`; the list in use is the 34,092 families of policy net v4.1's training set (`transfer/v41-training-families-union-20261112`) |
| What did one run actually execute? | Its immutable manifest, actor/model hashes and frozen runtime |
| Where are published scores? | [Arena](https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=latest), whose default view is Gen 8 over all collectors; only feeds in `gh-pages:arena/gen6-sources.json` are counted |
| Who has which Azure box? | `box/coordination` (allocation table and log) and `fleet/azure` (`STATUS.md`) |
| Where does new development start? | `main` |

## Actors

| Actor | What it is |
| --- | --- |
| `8s-32` Gen 8 candidate (32) | `71s-32` with the play read from trick 1 at exponent 1.0, the opponents' plays scaled by who they are, and each side's calls read by the system it declares (system scorer v1). Bids with the house net |
| `8c-32` Gen 8 candidate, Precision rule bidder (32) | The same bot bidding the project's rule system (`rules-precision`, r4) |
| `71s-32` Gen 7.1 standard (32) | `6-32` with `engine: gen7`, policy net v4.1, layouts weighted by the play from trick 7, tree search at tricks 3–6. Unchanged from Gen 7.1 |
| `5RZ32` Gen 5 (32), `1` Gen 1 | Frozen older actors |
| `ben`, `ben64` | BEN at 16 and 64 samples (separate runtime) |
| `6-32` Gen 6 fast | In the roster as the common-auction bidder; it plays no pair |

| Pair | Weight | Purpose |
| --- | ---: | --- |
| `8s-32~71s-32` | 2 | Generation comparison |
| `8c-32~71s-32`, `8c-32~8s-32` | 1 each | The second bidding system, against a bot that is not told how to read it and against one that is |
| `8s-32~5RZ32`, `8s-32~1` | 1 each | Older anchors, for diversity of opponents |
| `8s-32~ben64`, `8s-32~ben` | 1 each | BEN anchors, on machines with BEN's servers |

Common auctions use the Gen 6 bidder at all four seats; native auctions use each side's own
system, and every table records the two systems (`systems:NS|EW` in `auction_source`). Details,
settings and what was measured: [Gen 8 page](generations/gen8/README.md).

## Still running from Gen 7

At this snapshot the Gen 7.1 cohorts on Azure, Codex, 19bbdce5 and the independent collector
were drained. No Gen 8 feed existed from the cloud, extra or ChatGPT producers; moving each is
Max's instruction to that producer, relayed by the operator on `box/coordination`. Gen 7's
scored results are closed: [Gen 7 results](generations/gen7/README.md#results).

## Not authorized or not on main

- Gen 9: work in progress on `feature/gen9` and the branches around it; not on main, not in the arena.
- Self-play in the arena: Gen 8's plans have no self-play pair. Gen 7's phase 2 and
  `round71-selfplay.json` were never opened.
- Collector runtime changes that conflict with main (capture kept in self-play, feed-health
  supervision, BEN auto-expansion): [backlog item 1](backlog.md).
- Hand-fit scorer v1a: packaged on `research/hand-fit-scorer-v1a-20261111`; every bot uses v0,
  the Gen 8 bots with the system scorer built on it.

## Evidence rules

Prediction validation, double-dummy proxy comparisons and paired played IMPs answer
different questions. Keep the evaluation population with any number. Self-play has no
strength estimate. Intervals on the dashboard are unadjusted for repeated looks. A board on a
deal family a bot's net was trained on is not evidence about that bot.
