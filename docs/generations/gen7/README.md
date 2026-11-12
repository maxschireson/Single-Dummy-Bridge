# Gen 7 (closed for development, 12 November 2026)

**Status.** Superseded in the arena by [Gen 8](../gen8/README.md), which Max authorized on 12 November 2026 at
15:32 UTC; the first Gen 8 collectors started at 16:30 UTC. Gen 7 ran for one day in two versions: 7.0 (`7s-32`, policy net
v4) from 02:09 UTC and 7.1 (`71s-32`, policy net v4.1) from 06:00 UTC. `71s-32` stays in Gen 8's mix as the Gen 7
family's representative (Max, 16:11 UTC). Phase 2 was never authorized and `7f-32` never played in the arena.
Development no longer targets Gen 7.

## The bot

Gen 6 fast (`6-32`: bidder, lead net, hand-fit scorer, layouts, 32 samples) with the card-play decision replaced by
`engine: gen7`:

- A policy net chooses among exactly equal cards and feeds the tree. Releases:
  [v4](../../../models/cardplay/gen7-policy-v4-2026-11-11/README.md) (sha256 `d6b01193…`, trained on Gen 6 decision
  capture and gap forks) and [v4.1](../../../models/cardplay/gen7-policy-v4.1-2026-11-12/README.md) (sha256
  `cb3fcfd5…`, the same shape trained on every board on the feeds at 03:59 UTC on 12 November). Earlier nets v0, v1
  and v2 are kept as releases.
- Layouts are weighted by the play so far from trick 7 (`play_weight` 0.5).
- Tree search at tricks 3 to 6 over the net's likeliest cards: `root_margin` 0.25, `trust` 0.3, `path` 0.5 IMPs, at
  most 3 tricks deep, 3 cards a node, 8 layouts.

| Actor | Label | Policy net | Identity | In the arena |
| --- | --- | --- | --- | --- |
| `7s-32` | Gen 7 standard (32) | v4 | `f0a578598673` | 02:09 to 06:00 UTC as the generation's bot, then as 7.1's opponent |
| `71s-32` | Gen 7.1 standard (32) | v4.1 | `7b0f58b4c403` | from 06:00 UTC; in Gen 8's mix after the switch |
| `7f-32` | Gen 7 fast (32): net, no tree | v4 | — | never (phase 2) |

Source: [`bridge_harness/gen7.py`](../../../bridge_harness/gen7.py),
[`gen7_tree.py`](../../../bridge_harness/gen7_tree.py),
[`ops/prepare_gen7_alpha.py`](../../../ops/prepare_gen7_alpha.py). What the collectors ran, from their feeds'
`recovery/environment.json`:

| Version | Collectors | Source |
| --- | --- | --- |
| 7.0, phase 1 | Azure (four boxes and the BEN lanes) | `feature/gen7-candidate-20261111` at `fe382f9b` |
| 7.0, phase 1 | independent | `codex/gen7-phase1-independent-20261112` at `522eda6` |
| 7.0, self-play mix | Codex, azure2 | `feature/gen7-selfplay-20261112` at `05d2cd8` and `7780e5e`; Codex with capture, `fix/gen7-selfplay-capture-codex-20261112` at `317cea3` |
| 7.0, self-play mix | independent | `codex/gen7-independent-selfplay-20261112` at `168d580` |
| 7.1 | Azure | `codex/gen71-independent-20261112` at `a588e09` (`feature/gen7-selfplay-20261112` at `9f5ec19` plus `--exclude-families`) |
| 7.1 | Codex | `feature/gen7-selfplay-20261112` at `56dafd6` |
| 7.1 | 19bbdce5 | `ops/gen71-19bbdce5-20261112` at `7d96087` |
| 7.1 | independent | `codex/gen71-independent-20261112` at `08b0465` |

The Codex phase 1, cloud and extra feeds record no source commit.

## Timeline (12 November 2026, UTC)

| When | Event |
| --- | --- |
| 02:09 | Phase 1 authorized: `7s-32` against `6-32`, BEN (64), BEN (16), `5RZ32` and Gen 1, to 2,000 boards a pair ([notice](gen7_candidate_2026-11-11.md)) |
| 04:09 | Max stops the Gen 5 and Gen 1 pairs ("it's clear enough") and sends their deals to `7s-32` self-play ([notice](gen7_selfplay_2026-11-12.md)) |
| 05:42 | Gen 7.1 authorized, effective 06:00: policy net v4.1 in the same bot; 7.0 self-play gives way to 7.1 against 7.0 "for at least 1000 boards / until 7.1 establishes a 95% CI lead", then 7.1 self-play ([notice](gen71_2026-11-12.md)) |
| 06:32 to 06:39 | Azure's first 7.1 cohorts closed: their pools held deals v4.1 was trained on (393 boards, counted nowhere). From 06:51 (`41b18c1`) every 7.1 cohort is prepared with `--exclude-families` |
| 11:36 | Max puts azure1 on 7.1 self-play and 7.1 against 7.0 |
| 15:46 | The 7.1 settings matches on azure1 end ("Let's wrap this up") |
| 15:53 | Max keeps 7.1 although the lead rule was not met: "Ok we can stick with 7.1; it should in theory be slightly better." |
| 16:11 | Max to the operator: the arena switches to Gen 8, with 7.1 kept as the Gen 7 family's representative |
| 16:22 to 16:30 | The Gen 7.1 cohorts on Azure, Codex and 19bbdce5 drained |
| 17:45 | The independent collector's Gen 7.1 cohort published for the last time |

## Results

The 53 Gen 7 feeds in the dashboard registry, pooled with the dashboard's counting rules (one observation per deal
family and matchup, earliest wins). IMPs per board from the first-named actor's side, with normal-approximation 95%
intervals, unadjusted for repeated monitoring. Computed 12 November 2026 at 18:04 UTC by
[`scripts/generation_results.py`](../../../scripts/generation_results.py); per-feed revisions in
[results.json](../../../reports/gen7-closeout-2026-11-12/results.json).

| Pair | Boards | Common auction (play) | Native auction (total) | Bidding (native − common) |
| --- | ---: | --- | --- | --- |
| `71s-32` vs `7s-32` (7.1 against 7.0) | 5,507 | −0.07 (−0.14 to −0.00) | same bidder | — |
| `71s-32` vs `6-32` | 2,234 | +0.30 (+0.18 to +0.43) | same bidder | — |
| `71s-32` vs BEN (64) | 4,623 | +0.01 (−0.10 to +0.12) | +0.32 (+0.19 to +0.46) | +0.32 (+0.21 to +0.43) |
| `71s-32` vs BEN (16) | 378 | −0.16 (−0.58 to +0.26) | +0.72 (+0.16 to +1.29) | +0.88 (+0.41 to +1.35) |
| `7s-32` vs `6-32` | 3,083 | +0.26 (+0.15 to +0.38) | same bidder | — |
| `7s-32` vs `5RZ32` (Gen 5) | 1,319 | +1.14 (+0.92 to +1.36) | +1.41 (+1.15 to +1.67) | +0.27 (+0.08 to +0.46) |
| `7s-32` vs Gen 1 | 1,319 | +2.24 (+1.99 to +2.48) | +2.23 (+1.95 to +2.51) | −0.01 (−0.19 to +0.18) |
| `7s-32` vs BEN (16) | 1,274 | +0.09 (−0.14 to +0.33) | +0.48 (+0.20 to +0.77) | +0.39 (+0.17 to +0.60) |
| `7s-32` vs BEN (64) | 684 | +0.07 (−0.23 to +0.37) | +0.55 (+0.17 to +0.93) | +0.48 (+0.19 to +0.77) |
| `71s-32` self-play | 628 | no strength estimate | | |
| `7s-32` self-play | 552 | no strength estimate | | |

21,601 counted boards from 22,214 observations. Reading the table:

- **7.1 against 7.0.** The rule Max set for moving to 7.1 self-play, at least 1,000 boards and a 95% lead for 7.1,
  was not met: after 5,507 boards 7.1 stands at −0.07 with the interval's upper end at zero, a figure read
  repeatedly during the day (about 15 looks by 14:29 UTC) with no sequential correction. Matches outside the arena,
  on random deals without forks, with standard errors: the operator's two settings matches, 7.1 with the deal-list
  exponent at 1.0 against 7.0, +0.14 ± 0.08 and +0.11 ± 0.08 (1,081 boards each, on the same deals), and the Gen 8
  session's match of v4.1 against v4 in the Gen 7 bot, −0.01 ± 0.05 (3,075 boards). The operator pooled all of it to
  about −0.02 ± 0.03 at 15:50 UTC. So the net trained on one more round of games did not make the bot measurably
  stronger.
- **Against Gen 6 fast**, 7.0 is ahead by 0.26 and 7.1 by 0.30, on different deals at different times: not a paired
  comparison of the two. Of the 3,083 boards in the 7.0 row, 1,637 are the pre-arena test (four retired Azure
  feeds published at 03:09 UTC, registered as Gen 7); whether its bot had the launched tree settings this page did
  not check.
- **Against BEN** both versions are level in common auctions and ahead by 0.3 to 0.7 when each side bids its own
  system; the gain is the bidding column. 7.1 against BEN (16) has 378 boards, all from the independent collector.
- **Against Gen 5 and Gen 1** only 7.0 played, until 04:09 UTC. Twelve boards in each of those rows come from a
  producer whose `5RZ32` and Gen 1 actors carry other identities (`f18374761152`, `c8714b6ff29e`) than everyone
  else's.
- Common-auction pairs use the Gen 6 bidder at all four seats; every Gen 7 bot bids with it too, so pairs inside
  the Gen 6 and Gen 7 family have no bidding column.

**Not counted, because not in the registry at 18:04 UTC:** `arena-gen7-1-mix2-azure1-feed` (381 boards of 7.1
self-play and 7.1 against 7.0, drained at 16:22) and `arena-gen7-1-fresh3-azure3-ben64-*-feed` (105 boards against
BEN (64), drained at 16:30). **Not counted by design:** the three sets closed at 06:32 to 06:39 because v4.1 was
trained on their deals (`arena-gen7-1-azure3-ben64-*-feed` 225 boards, `arena-gen7-1-vs70-azure2-feed` 160,
`arena-gen7-1-compare-azure2-feed` 8). The policy 4.1 session checked every other 7.1 cohort against the net's
training file and found no training deal, played or waiting (coordination board, 16:12 UTC).

## What Gen 7 handed to Gen 8

- **The engine.** Gen 8's bots are `engine: gen7` with the Gen 8 settings added; the tree and the tie-break are
  Gen 7.1's.
- **Policy net v4.1**, which the Gen 8 bots play with, and with it the rule on its training deals. Max, 15:50 UTC:
  "In general I would never want a bot to play a board in a family it has been trained on, other than as a specific
  experiment to measure that particular effect. Never in the arena." The list in use is the union of the two
  published lists of v4.1's training families (34,092, `transfer/v41-training-families-union-20261112`).
- **The comparison bot.** `71s-32` unchanged.
- **Deals.** The Gen 8 cohorts are prepared from the unplayed deals of the drained Gen 7.1 cohorts and from unused
  shards of the capture capsule.
- **Data.** 1,180 self-play boards and every cross-match board, with decision capture and gap forks, on the Gen 7
  feeds.
- **An open problem.** A better policy net barely moves the bot (the 7.1 against 7.0 row). Gen 8's
  [notice](../../gen8_candidate_2026-11-12.md) calls the share of a net's gain that the bot keeps leverage, measures
  it as its first gate and does not raise it.

## Merged and not merged at closeout

Merged into main at this cleanup, without conflict: `feature/gen7-selfplay-20261112` at `5099000` (the self-play
regime and the Gen 7.1 notice) and `codex/gen71-independent-20261112` at `b09c865` (`--exclude-families`, the
promotion gate [`ops/check_gen71_gate.py`](../../../ops/check_gen71_gate.py) with its checkpoint, and the
training-family audit).

Not merged, because they conflict with what is now on main ([backlog](../../backlog.md), item 1):

| Branch | Conflicts in | What it holds |
| --- | --- | --- |
| `fix/gen7-selfplay-capture-codex-20261112` (PR #15) | `bridge_harness/gen5_arena.py` | Gap and guess capture kept in the self-play runtime; Codex's 7.0 self-play cohort ran it |
| `codex/gen7-independent-selfplay-20261112` | `ops/prepare_gen7_alpha.py`, this page | The independent collector's 7.0 self-play cutover |
| `ops/gen71-19bbdce5-20261112` | `ops/prepare_gen7_alpha.py` | The 19bbdce5 collector's 7.1 preparation with explicit common and native metadata |

## Backlog dispositions at closeout

Items of the [backlog](../../backlog.md) closed at the Gen 7 → Gen 8 cleanup:

| # | Item | Disposition |
| --- | --- | --- |
| 2 | Azure Gen 7 feeds not in the dashboard registry | Done during the day: the registry lists the Azure phase 1 feeds, the BEN lanes and the Gen 7.1 feeds, and the table above counts them. Two late Gen 7.1 sets are still out (backlog item 12) |
| 3 | No phase 1 collector for the two BEN pairs | Done: azure2's eight BEN (16) lanes and azure3's eight BEN (64) lanes, and the independent collector, played them (1,274 and 684 boards for 7.0) |
| 6 | Gen 8 systems layer, work in progress on `feature/gen8-systems-20261111` | Done: the finished layer came onto main with Gen 8's source. The branch's one commit is the earlier draft of the same files and is superseded |

Item 1 (collector runtime off main) stays open in a smaller form: the self-play regime it asked for is on main,
the capture and supervision changes are not.

## Documents

Moved into this folder at closeout:

- [Phase 1 notice: mix, plans, launch steps](gen7_candidate_2026-11-11.md) (formerly `docs/gen7_candidate_2026-11-11.md`)
- [Self-play notice of 12 November](gen7_selfplay_2026-11-12.md) (formerly `docs/gen7_selfplay_2026-11-12.md`)
- [Gen 7.1 notice: policy net v4.1, the mix, the deals it may not play](gen71_2026-11-12.md) (formerly `docs/gen71_2026-11-12.md` on `feature/gen7-selfplay-20261112`)
- [Alpha guide: every setting, the stake rule, what was checked](gen7_alpha_2026-11-11.md) (formerly `docs/gen7_alpha_2026-11-11.md`)
- [Prototype notes: policy net, play weights, measurements](gen7_prototype_2026-11-11.md) (formerly
  `docs/gen7_prototype_2026-11-11.md`, where a pointer stays because the policy net releases link to it)
- [Independent collector, phase 1](independent-phase1-20261112.md) and [its Gen 7.1 comparison](independent-gen71-20261112.md)

Reports and records: [closeout results](../../../reports/gen7-closeout-2026-11-12/README.md); the independent
collector's [7.1 gate checkpoint](../../../reports/gen71-gate-20261112T1353.md) and
[training-family audit](../../../reports/gen71-authoritative-training-audit-20261112.md). On branches, not on main:
the 7.1 settings matches (`transfer/gen71-settings-azure1-20261112`, `FINDINGS.md`), policy net v4.1's training
box output, benches and family list (`transfer/gen7-policy-v4.1-*-20261112`), the build session's save points
(`transfer/gen7-prototype-20261111`).

Plans: `configs/round7-candidate-phase1.json` with its `-nonben` and `-ben` halves, `round7-phase1-selfplay.json`,
`round71-compare.json`, `round71-ben.json`, `round71-selfplay.json` (never opened), `round7-candidate-phase2.json`
(never opened), and the independent collector's `round7-independent-phase1.json`, `round71-independent-*.json`.

## Feeds

Registered in the dashboard (`gh-pages:arena/gen6-sources.json`) as generation 7: 53 sources, 14 retired at a pinned
revision and 39 read at their branch heads. The 39 had all published their last snapshot by 16:25 UTC except
`arena-gen7-phase1-azure4-feed`, which still publishes (829 boards at 17:51 and at 17:57 UTC). Revisions and snapshot
times are in results.json.

| Group | Feeds | Boards published |
| --- | ---: | ---: |
| Pre-arena test, `7s-32` against `6-32` (`arena-gen7-pre7-azure{1..4}-feed`) | 4 | 1,637 |
| 7.0 phase 1, non-BEN (`arena-gen7-phase1-azure{1..4}-feed`, `-codex-20261112-`, `-extra-`, `-cloud-`) | 7 | 3,653 |
| 7.0 phase 1, five pairs (`arena-gen7-phase1-independent-feed`) | 1 | 387 |
| 7.0 against BEN (16), azure2 lanes (`arena-gen7-phase1-azure2-ben16-{1..8}-feed`) | 8 | 1,195 |
| 7.0 against BEN (64), azure3 lanes (`arena-gen7-phase1-azure3-ben64-{1..8}-feed`) | 8 | 606 |
| 7.0 self-play mix (`arena-gen7-selfplay-codex-20261112-feed`, `-selfplay-capture-codex-`, `arena-gen7-phase1-selfplay-azure2-feed`, `arena-gen7-independent-selfplay-feed`) | 4 | 900 |
| 7.1 against 7.0 and Gen 6 (`arena-gen7-1-compare-codex-20261112-feed`, `arena-gen71-19bbdce5-20261112-feed`, `arena-gen7-1-vs70-fresh-azure2-feed`) | 3 | 4,908 |
| 7.1 self-play and against 7.0 (`arena-gen7-1-mix-azure1-feed`) | 1 | 1,256 |
| 7.1 against BEN (64), azure3 lanes (`arena-gen7-1-fresh-` and `-fresh2-azure3-ben64-{1..8}-feed`) | 16 | 4,379 |
| 7.1, the independent collector's five pairs (`arena-gen71-independent-feed`) | 1 | 3,293 |

A board published is not always a board counted: a deal family counts once per matchup across all feeds.
