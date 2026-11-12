# Gen 7 (current arena generation)

**Status, 12 November 2026 ~03:05 UTC.** Phase 1 authorized 02:09 UTC and collecting.
Phase 2 (volume with self-play) is not authorized. The operational authority is the
[phase 1 notice](../../gen7_candidate_2026-11-11.md); this page is the index.

**Change of 04:09 UTC.** Max stopped the Gen 5 and Gen 1 pairs ("it's clear enough") and sent
their deals to self-play. The authority for that is the
[self-play notice](../../gen7_selfplay_2026-11-12.md): plan
[`round7-phase1-selfplay.json`](../../../configs/round7-phase1-selfplay.json) (`7s-32~6-32` one
board in three, `7s-32~7s-32` two), source branch `feature/gen7-selfplay-20261112`, not on main.
The sections below describe phase 1 as launched.

**Gen 7.1, from 06:00 UTC.** Max (05:42 UTC) upgraded the arena's bots to policy net v4.1:
`71s-32` is `7s-32` with that net and nothing else changed. 7.1 plays 7.0 where 7.0 played itself,
for at least 1,000 boards and until it leads outside a 95% interval; in every other pair 7 becomes
7.1. Authority: the [Gen 7.1 notice](../../gen71_2026-11-12.md).

## What changes from Gen 6

Gen 7 keeps Gen 6 fast (`6-32`) — bidder, lead net, hand-fit scorer, layouts, 32 samples —
and replaces the card-play decision with `engine: gen7` and a new policy net:

- Policy net v4 ([release](../../../models/cardplay/gen7-policy-v4-2026-11-11/README.md),
  sha256 `d6b01193…`), trained on Gen 6 decision capture and gap forks; earlier nets v0, v1 and v2
  are kept as releases.
- Layouts weighted by the play so far from trick 7 (`play_weight` 0.5); exact ties broken by
  the net.
- `7s-32` only: tree search at tricks 3 to 6 over the net's likeliest cards. Settings at
  launch: `root_margin` 0.25, `trust` 0.3, `path` 0.5 IMPs, at most 3 tricks deep, 3 cards a
  node, 8 layouts. Opponent-reply nodes average over the net's likely cards; they do not run
  a full PIMC search.

Source: [`bridge_harness/gen7.py`](../../../bridge_harness/gen7.py),
[`gen7_tree.py`](../../../bridge_harness/gen7_tree.py),
[`ops/prepare_gen7_alpha.py`](../../../ops/prepare_gen7_alpha.py). Deployed collectors pin
`feature/gen7-candidate-20261111` at `fe382f9b`, which is now on main.

| Bot | Label | Phase |
| --- | --- | --- |
| `7s-32` | Gen 7 standard (32): net + tree | 1 and 2 |
| `7f-32` | Gen 7 fast (32): net, no tree | 2 |

## Match plan

Phase 1, five cross matches at equal weight to 2,000 boards each, pooled across collectors:
`7s-32` against `6-32` (the generation comparison), BEN (64), BEN (16), `5RZ32` and Gen 1.
Plans: [`round7-candidate-phase1.json`](../../../configs/round7-candidate-phase1.json) (all five),
`-nonben` and `-ben` variants for machines with and without BEN servers.

Phase 2 (closed): 30% `7f-32` self-play, 30% `7s-32` self-play, 20% `7s-32` vs `6-32`, 5% each
against the four anchors ([`round7-candidate-phase2.json`](../../../configs/round7-candidate-phase2.json)).
It needs a runtime that carries both the self-play regime and the gen7 engine; main has
neither combined yet ([backlog](../../backlog.md), item 1).

## Collectors and feeds

Phase 1 source run: the `arena-gen6-gen7-capture-feed` capsule at `8833c62`, split with
`--shard K/8`. Check fresh status before relying on any row.

| Producer | Plan | Shard | Feed | In dashboard registry |
| --- | --- | --- | --- | --- |
| Codex | non-BEN | own source run | `arena-gen7-phase1-codex-20261112-feed` | yes |
| azure1 | non-BEN | 0/8 | `arena-gen7-phase1-azure1-feed` | no |
| azure2–4 | non-BEN | 1/8–3/8 | `arena-gen7-phase1-azure{2,3,4}-feed` (starting at 02:54) | no |

No collector running the BEN pairs had been registered at this snapshot. The Azure boxes
have no BEN server. Azure box control: [boxctl](../../boxctl.md); fleet coordination:
`fleet/azure` and `box/coordination` branches (see [operations](../../operations.md#remote-boxes)).

## Documents

- [Phase 1 notice: mix, plans, launch steps](../../gen7_candidate_2026-11-11.md)
- [Self-play notice of 12 November: the Gen 5 and Gen 1 pairs stop, the plan, the code, what each source records](../../gen7_selfplay_2026-11-12.md)
- [Alpha guide: every setting, the stake rule, what was checked](../../gen7_alpha_2026-11-11.md)
- [Prototype notes: policy net, play weights, measurements](../../gen7_prototype_2026-11-11.md)
- Build session save points: `transfer/gen7-prototype-20261111` (22 commits not on main)

These stay at their current paths while Gen 7 is in development, because the Gen 7 session
is still editing them on its branch; they move into this folder at Gen 7's closeout.

## Next generation

Gen 8 (multiple bidding systems and carding agreements as data; MoE-style scorer/belief/
bidder) is work in progress on `feature/gen8-systems-20261111` — [its guide](https://github.com/maxschireson/Single-Dummy-Bridge/blob/feature/gen8-systems-20261111/docs/gen8_systems.md).
Not on main.

- [Independent collector phase 1](independent-phase1-20261112.md)

- [Independent Gen7.1 comparison](independent-gen71-20261112.md)
