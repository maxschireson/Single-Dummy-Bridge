# Gen 8 (current arena generation)

**Status, 12 November 2026 18:20 UTC.** Authorized by Max at 15:32 UTC ("Go ahead") and collecting since 16:30 UTC.
Both of its plans are open; there is no second phase waiting. The operational authority is the
[notice](../../gen8_candidate_2026-11-12.md); this page is the index. A run's frozen manifest takes precedence over
both.

## What changes from Gen 7

Gen 8 keeps Gen 7.1 standard (`71s-32`: Gen 6 fast with `engine: gen7` and policy net v4.1) and adds four things.
Settings, evidence and limits are in the notice.

1. **The play is read from trick 1**, at exponent 1.0, where Gen 7 read it from the trick at which every layout
   can be listed (about trick 7) at 0.5.
2. **The opponents' plays are read by who they are**: in full for the house family, at 0.2 for Gen 1, at 0.5 for
   BEN, at 0.3 for anyone else.
3. **Each side's calls are read by the system that side declares**
   ([system scorer v1](../../../models/cardplay/gen8-system-scorer-v1-2026-11-12/README.md); the layer is described
   in [gen8_systems.md](../../gen8_systems.md)).
4. **A second bidding system at the table**: the project's rule bidder
   ([`bridge_harness/rule_bidder.py`](../../../bridge_harness/rule_bidder.py), a Precision system, version r4 with
   [its settings and trick estimate](../../../configs/rule-systems)).

| Actor | Label | Bids | Identity |
| --- | --- | --- | --- |
| `8s-32` | Gen 8 candidate (32) | the house net | `269fdf1854f4` |
| `8c-32` | Gen 8 candidate, Precision rule bidder (32) | the rule system (bidder `f50e95de93ac`) | `f60c9782f5c8` |

Source: [`bridge_harness/gen7.py`](../../../bridge_harness/gen7.py) (the engine, with the Gen 8 settings),
[`gen5_arena.py`](../../../bridge_harness/gen5_arena.py) (tables whose two sides bid different systems),
[`systems.py`](../../../bridge_harness/systems.py), [`ops/prepare_gen7_alpha.py`](../../../ops/prepare_gen7_alpha.py).

## What was measured before the launch

Max set three gates. From the notice, IMPs a board with standard errors:

| Gate | Result |
| --- | --- |
| Substantially stronger in play than Gen 7 | Met head to head: +0.45 ± 0.08 against Gen 7.1 over 1,600 boards. Not shown against a third opponent: against Gen 6 fast, Gen 8 does +0.10 ± 0.09 better than Gen 7.1 does |
| Accommodates heterogeneous player pools | Met for the types measured: reading the rule system's calls by its own table is worth +0.31 ± 0.11 in card play at tables where it is bid (1,000 boards). BEN was not measured before the launch |
| Materially increases leverage | Not met |

The Precision bot is the weaker bidder: −0.59 ± 0.23 against the house-bidding Gen 8 when each bids its own system
(800 boards). It is in the arena to put a second, declared system at the table.

## Match plan

| Plan | Pairs and weights |
| --- | --- |
| [`round8-candidate.json`](../../../configs/round8-candidate.json), the main mix | `8s-32~71s-32` 2, `8c-32~71s-32` 1, `8c-32~8s-32` 1, `8s-32~5RZ32` 1, `8s-32~1` 1 |
| [`round8-candidate-ben.json`](../../../configs/round8-candidate-ben.json), for machines with BEN's servers | `8s-32~ben64` 1, `8s-32~ben` 1 |
| [`round8-19bbdce5.json`](../../../configs/round8-19bbdce5.json), [`round8-independent.json`](../../../configs/round8-independent.json) | The two collectors' own copies: the main mix, and for the independent collector the two BEN pairs as well |

Every pair but `8s-32~71s-32` has four tables a board: two with a common auction bid by the house net and two where
each side bids its own system. Every cohort is prepared with `--exclude-families` and the list of deal families
policy net v4.1 was trained on. Max, 15:50 UTC: "In general I would never want a bot to play a board in a family it
has been trained on, other than as a specific experiment to measure that particular effect. Never in the arena."
The plans refuse to be prepared without a list.

## Collectors and feeds

At 18:20 UTC on 12 November. Check fresh status before relying on a row; who has which Azure box is on
`box/coordination`.

| Producer | Pairs | Deals in the cohort | Feed | Source |
| --- | --- | ---: | --- | --- |
| azure1 | main mix | 1,097; then 1,468 from about 20:20 UTC | `arena-gen8-azure1-feed`; then `arena-gen8-s3-azure1-feed` | `792c4cb` |
| azure6, 16:57 to 18:12 UTC | main mix | 1,484, of which 410 played | `arena-gen8-azure6-feed` | `792c4cb` |
| azure3, eight lanes | `8s-32~ben64` | 1,365 | `arena-gen8-azure3-ben64-{1..8}-feed` | `792c4cb` |
| Codex | main mix | 18,283 | `arena-gen8-candidate-codex-20261112-feed` | `792c4cb` |
| 19bbdce5 | main mix | 16,036 | `arena-gen8-19bbdce5-20261112-feed` | `c8a138f` (`ops/gen8-19bbdce5-20261112`) |
| independent ([its page](independent-collector.md)) | main mix and both BEN pairs | 7,816 | `arena-gen8-independent-feed` | `6776c28` (`codex/gen8-independent-20261112`) |

All thirteen feeds are in the dashboard registry as generation 8, every manifest carries the same identity for each
bot it lists, and every cohort excludes the 34,092 training families. `792c4cb` is
`feature/gen8-prototype-20261112` at the commit that opened the plans; the other two sources are that commit plus
each collector's own plan and preparation changes. All three are on main since the Gen 7 to Gen 8 cleanup. azure6
left the arena at 18:12 UTC for other work (Max, 18:07); its unplayed deals go to azure1. No Gen 8 feed existed at
this snapshot from the cloud, extra or ChatGPT producers.

## Results

None are stated here while the generation is collecting; the [arena](https://maxschireson.github.io/Single-Dummy-Bridge/arena/?source=latest)'s
default view is Gen 8 over all collectors. What its rows can be read against is [Gen 7's closed table](../gen7/README.md#results):
Gen 7.1 against BEN (64) at 0.00 in common auctions and +0.32 in own, and Gen 7.0 against Gen 5 at +1.14 and
against Gen 1 at +2.24, on other deals at other times.

## Open at launch

From the notice's "What this package does not do":

- Leverage is not raised, so a net retrained on Gen 8's games is not expected to make it measurably stronger.
- Gen 8's edge over Gen 7.1 against opponents outside its own family is not shown. The BEN lanes and the Gen 5 and
  Gen 1 pairs are the first measurements.
- BEN's reading factor, 0.5, was carried over from Gen 7 and not played before the launch.
- Carding is not declared: `systems` covers bidding only.
- A training pipeline that reads auctions with the hand-fit scorer must bind each table's systems
  (`systems:NS|EW` in the record's `auction_source`) or leave out tables that are not house against house.

## Documents

- [Notice: what was built, measured and not measured; launch steps](../../gen8_candidate_2026-11-12.md)
- [System layer: systems as data and the system-aware scorer](../../gen8_systems.md)
- [The independent collector's Gen 8 cohort](independent-collector.md) and its
  [cutover report](../../../reports/gen8-independent-cutover-2026-11-12/README.md)
- Releases: [system scorer v1](../../../models/cardplay/gen8-system-scorer-v1-2026-11-12/README.md); the rule
  system r4 in [`configs/rule-systems`](../../../configs/rule-systems) and
  [`configs/systems/rules-precision.json`](../../../configs/systems/rules-precision.json)
- On branches, not on main: the prototype's match results (`transfer/gen8-proto-azure{1,3,4,6}-20261112`), the
  reading bench of the policy 4.1 session (`feature/gen8-p41-20261112`, `transfer/gen8-p41-reading-20261112`), the
  training-family list (`transfer/v41-training-families-union-20261112`)

The notice stays at its path in `docs/` while Gen 8 is the current generation and moves into this folder at Gen 8's
closeout.

## Next generation

Gen 9 is work in progress on `feature/gen9` and the branches around it (channel `team/gen9`); the open pull
requests #21, #26, #29 and #30 target those branches, not main. Not on main.
