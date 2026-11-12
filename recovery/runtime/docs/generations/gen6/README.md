# Gen 6 (closed for development, 12 November 2026)

**Status.** Superseded in the arena by [Gen 7](../gen7/README.md) phase 1, authorized
12 November 2026 02:09 UTC. Gen 6's scored matchups are complete. Some producers were
still publishing Gen 6 fast self-play at closeout (training data, no strength estimate);
`6-32` remains in Gen 7 phase 1 as the comparison bot. Development no longer targets Gen 6.

## The bot

Gen 5 networks and search, with three new components (details in the
[architecture note](gen6_architecture_2026-11-11.md), whose initial defaults were superseded
at launch):

| Component | Release |
| --- | --- |
| Bidder: graded alternative calls, trained on 40k DD-solved deals | [gen6-candidate-2026-11-11](../../../models/bidding/gen6-candidate-2026-11-11/README.md) |
| Opening-lead belief net (auction-conditioned) | [joint-auction-belief-lead-v0](../../../models/cardplay/joint-auction-belief-lead-v0-2026-11-10/README.md) |
| Hand-fit scorer for layouts after the lead | [hand-fit-scorer-v0](../../../models/cardplay/hand-fit-scorer-v0-2026-11-11/README.md) |
| Policy (PIMC exact ties only) | [Gen 5 policy](../../../models/cardplay/gen5-2026-11-10/README.md) |
| Layout selection | [layout-selection study](../../../reports/gen6-layout-selection-2026-11-11/README.md) |

| Actor | Samples before listing | Full compatible-layout listing from | Late solve ceiling |
| --- | ---: | ---: | ---: |
| `6-32` Gen 6 fast | 32 | trick 7 | 256 |
| `6-256` Gen 6 medium | 256 | trick 6 | 256 |

Source: [`bridge_harness/gen6.py`](../../../bridge_harness/gen6.py) and `gen6_nets.py`; main at
`b0909bb` is the Gen 6 source. Model hashes: [recovery runbook](gen6-arena-recovery-20261111.md).

## Timeline (UTC)

| When | Event |
| --- | --- |
| 11 Nov 01:45 | Engine, launch files and model releases committed (`8702fa1`) |
| 11 Nov 02:06–02:15 | Collectors launched; BEN16 share moved from fast to medium (13 accidental fast-vs-BEN16 games archived, excluded from scores) |
| 11 Nov 05:43 | Medium vs BEN64 authorized |
| 11 Nov 07:40 | Mix replaced: 92.5% fast self-play, 7.5% fast vs BEN16; Gen 7 decision capture and gap forks kept on |
| 12 Nov 02:09 | Gen 7 phase 1 authorized; producers begin moving to Gen 7 |

The launch mix was fast vs 5RZ32 40%, fast vs medium 15%, medium vs BEN16 15%, fast vs
Gen 3/2/1 10% each ([`round6-codex.json`](../../../configs/round6-codex.json)); the final mix is
[`round6-fast-selfplay.json`](../../../configs/round6-fast-selfplay.json).

## Results

All 18 Gen 6 feeds in the dashboard registry, pooled with the dashboard's counting rules
(one observation per deal family and matchup, earliest wins). IMPs per board from the
first-named actor's side, with normal-approximation 95% intervals, unadjusted for
repeated monitoring. Computed 12 November 2026 ~03:05 UTC by
[`scripts/generation_results.py`](../../../scripts/generation_results.py); per-feed revisions
in [results.json](../../../reports/gen6-closeout-2026-11-12/results.json).

| Pair | Boards | Common auction (play) | Native auction (total) | Bidding (native − common) |
| --- | ---: | --- | --- | --- |
| `6-32` vs `5RZ32` (Gen 5) | 3,025 | +0.73 (+0.58 to +0.88) | +0.82 (+0.65 to +0.99) | +0.09 (−0.03 to +0.21) |
| `6-32` vs Gen 3 | 755 | +0.70 (+0.41 to +0.99) | +1.13 (+0.77 to +1.50) | +0.43 (+0.17 to +0.70) |
| `6-32` vs Gen 2 | 758 | +0.71 (+0.42 to +1.01) | +0.86 (+0.53 to +1.19) | +0.15 (−0.09 to +0.38) |
| `6-32` vs Gen 1 | 756 | +1.67 (+1.35 to +1.99) | +1.81 (+1.45 to +2.18) | +0.14 (−0.11 to +0.39) |
| `6-32` vs `6-256` | 1,133 | −0.13 (−0.34 to +0.07) | same bidder | — |
| `6-32` vs BEN (16) | 1,809 | −0.11 (−0.31 to +0.10) | +0.05 (−0.19 to +0.30) | +0.16 (−0.03 to +0.35) |
| `6-256` vs BEN (16) | 392 | +0.43 (+0.03 to +0.82) | +0.50 (+0.01 to +0.99) | +0.07 (−0.31 to +0.46) |
| `6-256` vs BEN (64) | 180 | +0.04 (−0.56 to +0.65) | +0.29 (−0.38 to +0.97) | +0.25 (−0.25 to +0.75) |
| `6-32` self-play | 23,127 | no strength estimate | | |

Reading the table:

- Against Gen 5 the gain is mostly in play (common auction); the bidding difference is
  small. Against older bidders it is larger (Gen 3: +0.43).
- Fast and medium are within noise of each other head to head (medium +0.13, interval −0.07 to +0.34).
- Against BEN (16), medium is ahead in play; fast is level. The two were measured on
  different deal sets and at different times, so the fast-vs-medium gap against BEN is
  not itself a tested comparison. BEN (64) has 180 boards and no conclusion.
- Common-auction pairs use the Gen 6 bidder at all four seats; native pairs use each
  side's own bidder.

## What Gen 6 handed to Gen 7

- **Data.** ~23k self-play boards plus decision capture and gap forks (the Gen 7
  policy-net training set), on the Gen 6 feeds and `transfer/gen7-capture-forks-20261111`.
- **Source run for phase 1.** The recovery capsule of `arena-gen6-gen7-capture-feed` at
  `8833c62` (22,508 unplayed deals), sharded across Gen 7 collectors.
- **The comparison bot.** `6-32` unchanged.

## Not merged at closeout

The collectors' Gen 6 runtime changes (self-play regime, decision capture, gap forks, BEN
auto-expansion, feed-health supervision) live on their branches, not on main. They conflict
with each other in `ops/`. Gen 7 phase 2 needs the self-play regime. See
[backlog](../../backlog.md), item 1.

## Documents

- [Architecture note](gen6_architecture_2026-11-11.md) (formerly `docs/gen6_architecture_2026-11-11.md`)
- [Recovery runbook and shared results contract](gen6-arena-recovery-20261111.md) (formerly `docs/gen6-arena-recovery-20261111.md`)
- [Gen 6 cleanup ledger: PR dispositions of 11 November](cleanup-ledger.md)
- Reports: [layout selection](../../../reports/gen6-layout-selection-2026-11-11/README.md),
  [primary launch](../../../reports/gen6-primary-launch-20261111.json),
  [dashboard verification](../../../reports/gen6-primary-dashboard-verification-20261111.json),
  [accidental fast-vs-BEN archive](../../../reports/gen6-accidental-fast-ben-archive-20261111.json),
  [closeout results](../../../reports/gen6-closeout-2026-11-12/README.md)

## Feeds

Registered in the dashboard (`gh-pages:arena/gen6-sources.json`); revisions used above are
in results.json. Retired: `arena-gen6-codex-feed`, `arena-gen6-medium-ben-feed`,
`arena-gen6-independent-feed`, `arena-gen6-ben-expansion-feed`,
`arena-gen6-codex-ben-followups-feed`, `arena-gen6-codex-v7-capture-feed`,
`arena-gen6-gen7-capture-feed`, `arena-gen6-fast-selfplay-codex-20261111`, and four retired
cohorts on `arena-gen6-chatgpt-feed`. Publishing self-play within the hour before closeout:
`arena-gen6-fast-selfplay-independent-feed`, `arena-gen6-chatgpt-feed`,
`arena-gen6-fast-selfplay-cloud-feed`, `arena-gen6-extra-selfplay-feed`,
`arena-gen6-fast-selfplay-20261111-19bbdce5-feed`. Not marked retired but last published
11 November 12:05 UTC: `arena-gen6-fast-selfplay-primary-feed`. Whether each producer should
stop Gen 6 self-play is a per-producer instruction; this page does not stop anything.
