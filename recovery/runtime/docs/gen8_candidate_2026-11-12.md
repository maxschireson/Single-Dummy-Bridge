# Gen 8 candidate: the play read from trick 1, and two bidding systems at the table (12 November 2026)

**Status: authorized. Max said go on 12 November 2026 at 15:32 UTC. Both plans are open; the collectors are
started by g7, the arena's operator.** Branch `feature/gen8-prototype-20261112`, which contains the Gen 7.1 launch
line (`codex/gen71-independent-20261112` at `a588e09`, merged at `9c40d64`) and main. This page is what was built,
what was measured and on how many boards, and what was not. It was written as the candidate's notice and its
findings stand as they were when Max decided, the caveat on gate 3 among them.

Max's instructions. 12 Nov, 02:38 UTC: build and test a Gen 8 prototype "where there will be multiple
systems deployed", with three gates: it should materially increase leverage (the share of a stronger net's
gain that the bot keeps), accommodate heterogeneous player pools, and be substantially stronger in play
than Gen 7. 05:28 UTC: no outside bidding engine in Gen 8. 05:46 UTC: build a rule-based, configurable
Precision bidder and tune it on double-dummy results, to be the second bidder "if its bidding accuracy
isn't a disaster". 06:54 UTC: "If you hit only 2 of your 3 gates it's not a disaster but of course all 3 is
better. You have made enough strength progress that I will want to push when you have bidding diversity."
And: nothing launches without him.
15:30 UTC: "Leaning towards pushing sooner rather than later. When might we go?" 15:32, to "if you say go now, I open
the plans as soon as the preflight returns clean and post the box question to g7 on the board": **"Go ahead"**.
15:33: "All machines not working on 9 and other future projects can switch from 7 work to 8 arena."

## The three gates

| Gate (Max, 02:38 UTC) | Verdict | The figure |
| --- | --- | --- |
| 3. Substantially stronger in play than Gen 7 | **Met head to head; against a third opponent the edge is not shown** | Against Gen 7.1 standard, both with policy v4.1: **+0.453 +- 0.080** IMPs a board (1,600 boards). Against Gen 6 fast, Gen 8's result less Gen 7's on the same deals: +0.135 +- 0.131 with policy v4.1 and +0.077 +- 0.122 with v4 (800 deals each) |
| 2. Accommodates heterogeneous player pools | **Met for the types measured; BEN not measured** | No worse than Gen 7 against carders the net does not model (+0.53 against +0.45, +0.30 against +0.30), where reading them at full weight would cost 0.36; a second bidding system at the table, read by its declared system: the bot that reads it right beats the same bot reading it as house calls by **+0.314 +- 0.109** (1,000 boards) |
| 1. Materially more leverage | **Not met** | A stronger net alone gains +0.76 (v4.1 over v4) and +4.05 (v4 over v0); the bots that use it gain -0.04 +- 0.08 (Gen 8) and -0.00 +- 0.05 (Gen 7.1), +0.04 +- 0.11 and -0.02 +- 0.09 |

Max, 06:54 UTC: two of three is not a disaster, and he will want to push when there is bidding diversity. The
bidding diversity is the second system below.

**Gate 3, strength.** All in common auctions (both rooms of a board play one auction bid by the house net), fork-free
matches on fresh deals (`scripts/gen8_match.py`), IMPs a board for the first-named bot:

| Match | Boards | Result |
| --- | --- | --- |
| Gen 8 (`8p-32-v41`) against Gen 7.1 standard (`7s-32-v41`) | 1,600 | **+0.453 +- 0.080** |
| The same two with policy v4 (`8p-32` against `7s-32`) | 1,623 | +0.405 +- 0.083 |
| The early reading alone: trick 1 to the deal list at 1.0, Gen 7's 0.5 after (the test bot called `8s-32` in `configs/gen8-proto-bots.json`) against `7s-32` | 896 | +0.376 +- 0.104 |

These rows are not independent: the first two are on the same 1,600 deals (their results correlate at +0.23 board by
board; together +0.43 +- 0.064), and the third is on 896 of them and correlates with the second at 0.96, so it is the
same evidence seen through one setting less, not a second match. On those 896 deals the deal-list exponent at 1.0
against 0.5 is worth +0.026 +- 0.030; the early reading is what carries the result.

**Against a third opponent the edge over Gen 7 is not shown.** Against Gen 6 fast, each pair of matches on the same deals:

| Nets | Gen 8 against Gen 6 | Gen 7 against Gen 6 | Gen 8 less Gen 7, deal by deal |
| --- | --- | --- | --- |
| v4.1 (`8x-32-v41`, `7s-32-v41`; 800 deals) | +0.439 +- 0.127 | +0.304 +- 0.097 | +0.135 +- 0.131 |
| v4 (`8p-32`, `7s-32`; 800 other deals) | +0.357 +- 0.121 | +0.280 +- 0.111 | +0.077 +- 0.122 |

Together about +0.10 +- 0.09. So Gen 8 beats Gen 7.1 by 0.45 when the two meet, and against Gen 6 it does a quarter
of that better than Gen 7.1 does, which is not told apart from nothing. p41's pairing of the result rows brought
this out, and why it is so is not explained. One reading was tested and is not supported: that Gen 7 and Gen 8
choose among exactly equal cards with the net, so that their cards say more to a reader with the same net than
Gen 6's do. Against Gen 7.1 with Gen 6's tie-break in place of the net's (`h1`, 800 deals of the head-to-head
match) Gen 8 scores +0.341 +- 0.108, which is -0.049 +- 0.098 from its result against Gen 7.1 as it is on the same
deals. A second reading is not tested: that Gen 7.1 reads Gen 8's cards with a net that models Gen 6's and Gen 7's
play and loses by it (the test bot `7n-32-v41`, a Gen 7.1 that does not read the play, is there for that match).
Until it is explained, the head-to-head figure says how Gen 8 does against Gen 7.1 and not how it does in a mixed
field or against BEN. The plan's mix has Gen 8 against Gen 5 and Gen 1, and the BEN lane against BEN, so the arena
will show what the edge is there.

The whole of the head-to-head result is reading the play from trick 1 at full weight. The ids here are the test bots of
`configs/gen8-proto-bots.json`. `8p-32-v41` reads every opponent at full weight; the plan's candidate `8s-32` is that
bot with the opponent factors of gate 2 and nothing else changed (checked field by field), and the factors are 1.0
against the house family, so against Gen 7.1 the two are the same player.

**Gate 2, player pools.** Three kinds of evidence.

*Carders the policy net does not model* (stand-ins for a new type: Gen 6 fast's search with a fixed carding rule,
`t-high` always the high card of equals, `t-random` a random card of equals). 800 boards each against `t-high`, 600
against `t-random`:

| Opponent | Gen 7 standard | Gen 8, every opponent read in full (`8p-32`) | Gen 8 with type factors (`8x-32`) |
| --- | --- | --- | --- |
| `t-high` | +0.449 +- 0.123 | +0.094 +- 0.133 | **+0.532 +- 0.118** |
| `t-random` | +0.297 +- 0.134 | not played | **+0.303 +- 0.140** |

On the same deals (p41's pairing): reading `t-high` at full weight against Gen 7's half weight, -0.355 +- 0.134; the
type factor against full weight, +0.439 +- 0.135; the type factor against Gen 7, +0.084 +- 0.121 on `t-high` and
+0.007 +- 0.142 on `t-random`. So reading a carder the net mis-models at full weight costs about a third of an IMP a
board, and scaling the reading by who the opponent is (`opponent_play_weight`, a factor by opponent id; partner is always read in full)
recovers it. In these matches the factor was the one calibrated for that type on 96 boards (0.2 for `t-high`, 0.25
for `t-random`), and the table is the check on other deals. The plan's table has 1.0 for the house family, 0.2 for
bot `1`, 0.5 for BEN and 0.3 for anyone not listed. The 0.3 was not itself played: it sits between the calibrated
values, and below Gen 7's 0.5.

*A known type with another bidding system* (the rule system r4 below, declared at the table).
*Read by its system or as house calls: the awareness match* (`a1-8a-v-8p-r4`). The auctions were bid beforehand
at tables where r4 sits North-South, East-West or at both sides, a third each, and both rooms of a board play the same
auction, so the bidding cancels and what is left is card play. `8a-32-v41` reads each side's calls with that side's
table; `8p-32-v41` is the same bot without the system scorer and reads every call as a house call.

| Tables | Boards | The bot that is told the systems |
| --- | --- | --- |
| All | 1,000 | **+0.314 +- 0.109** (won 245, lost 159, flat 596) |
| r4 at both sides | 333 | +0.486 +- 0.197 |
| House North-South, r4 East-West | 333 | +0.291 +- 0.187 |
| r4 North-South, house East-West | 334 | +0.165 +- 0.181 |

So a bot that is not told the system gives up about 0.3 IMPs a board in card play at tables where the rule system is
bid, which is what Gen 7.1 gives up at a table with the Precision bot. On tables where both sides bid the house system the candidate's two additions change no card: the
scorer (`8a-32-v41` against `8p-32-v41`, no auction book; `f1`) and the opponent table at 1.0 (`8x-32-v41` against
`8p-32-v41`; `f2`) each played 100 boards and all 100 were flat. So the head-to-head match of gate 3 is the candidate's.

*Each bidding its own system: the native match* (`b1-8c-v-8a`). `8c-32-v41` bids r4, `8a-32-v41` the house system,
and both are told the systems. 800 boards: **-0.594 +- 0.225** for the r4 bidder (won 259, lost 316, flat 225). In the
common-auction rooms the two are one engine and all 800 boards are flat, so this is the bidding, played out; at
double dummy the gap was -0.75. From the other side: the house-bidding Gen 8 scores +0.59 against the new type.

*The Precision bot against Gen 7.1* (`c1-8c-v-7s`, 800 boards): stopped at 90 boards when azure6 went to the arena (common auctions +0.31 +- 0.38, own auctions +0.26 +- 0.64: no result). The arena's `8c-32~71s-32` pair is this match at scale.

*Not measured:* any Gen 8 board against BEN. The plan reads BEN's plays at Gen 7's exponent (factor 0.5), now from
trick 1; the first BEN lane is that measurement.

**Gate 1, leverage** (the share of a stronger net's gain that the bot keeps). Not met, and not by a small margin: it
is about zero for Gen 7 and Gen 8 alike.

| Nets | The nets alone, one against the other | Gen 7 with the newer net against Gen 7 with the older | Gen 8 the same |
| --- | --- | --- | --- |
| v4.1 over v4 | +0.762 +- 0.074 (4,000) | -0.003 +- 0.047 (3,200) | -0.036 +- 0.080 (1,600) |
| v4 over v0 | +4.048 +- 0.088 (4,000) | -0.017 +- 0.089 (1,000) | +0.040 +- 0.112 (1,000) |

Why, as far as it is understood (p41's reading bench on 530 tables, plan's work, and the matches above): the bots
use the net as a model of how the house bots play, to weight layouts and to break exact ties. From v0 to v4 that
reading does improve, by 0.069 +- 0.024 double-dummy tricks a board, about a quarter of an IMP: 6% of the 4.05 IMPs
between those nets played alone. From v4 to v4.1 it is flat (+0.012 +- 0.015 tricks). Letting the net choose among
near ties (a window of 0.1 tricks) measured +0.142 +- 0.153 for leverage on 600 boards and -0.025 +- 0.068 for
strength on 2,000, so it is not in. Leverage needs the net inside the search (plan's line of work) or a net that
knows something the solver does not; neither is in this candidate.

## The bots

Both are Gen 7.1 standard (`71s-32`: Gen 6 fast with the gen7 engine and policy net v4.1) with the changes
below; the settings are spelled out in `configs/round8-candidate.json`.

| Id | Label | Bids | What it adds to Gen 7.1 standard |
| --- | --- | --- | --- |
| `8s-32` | Gen 8 candidate (32) | the house net | The play read from trick 1 at exponent 1.0, scaled by opponent type; each side's calls read by the system it declares |
| `8c-32` | Gen 8 candidate, Precision rule bidder (32) | the rule system | The same bot, bidding `rules-precision` in place of the house net |

1. **The play is read at every trick.** Gen 7 weights the listed layouts by the policy net's probability
   of the cards the hidden seats have played, from the trick where every layout can be listed (about
   trick 7), at exponent 0.5. Gen 8 does it from trick 1 at exponent 1.0: before the deal list a pool of
   512 layouts drawn by the hand-fit scorer is weighted by the net and resampled for the solver
   (`early_play_weight`, `early_pool`, `early_min_effective`; `play_weight` 1.0 on the deal list). The
   tree, the tie-break and everything else are Gen 7.1's.
2. **The opponents' plays are read by who they are** (`opponent_play_weight`, a factor on the exponent
   by opponent bot id; partner's plays are always read in full). The runner tells each player whom it
   faces. 1.0 for the house family (Gen 5RZ, 6, 7, 7.1, 8), 0.2 for bot `1`, 0.5 for BEN, 0.3 for anyone
   else. The factors for the house family and bot `1` come from calibration matches (below); BEN's is
   Gen 7's exponent and is not measured.
3. **Each side's calls are read by the system that side declares** (`system_scorer`): the hand-fit scorer
   with one more table of call readings, for the rule system
   ([release](../models/cardplay/gen8-system-scorer-v1-2026-11-12/README.md)). The cohort's `systems`
   says what each bot declares; the runner labels every table with its two systems and tells both
   players before the table is played, because the two rooms of a board can differ. The policy net's
   picture of what each seat has shown follows the same reading. The lead net is used at tables where
   each side bids a system Gen 7.1 already meets (`lead_systems`: the Gen 6, Gen 5 and DDS-trained house
   bidders and BEN's); at a table with the rule system the opening leader's layouts come from the scorer.
   A system the scorer holds no table for is read with the base file. So against every bot Gen 7.1 plays
   today the calls and the leads are read exactly as Gen 7.1 reads them, number for number, and the
   scorer's new table matters only where the rule system is bid.

## The second bidding system

`bridge_harness/rule_bidder.py`: the project's own code and rules, nothing from another program. A
Precision-style strong club (1C 16+, limited one-level openings, 14 to 16 no trump, 2C six clubs, 2D
three-suited short diamonds, weak twos in the majors). Every call the rules define has a meaning (a
point range, suit-length ranges, whether it forces, sometimes a private test); the bidder makes the first
defined call its hand fits, the same tables explain every call at the table, and where they stop a
general procedure places the contract from the two hands' shown ranges. Every range and threshold is a
setting, so a system is a small file, and its identity is a hash of its settings and of the versions of
the rules and of the judgement.

Two frozen versions are in the repository, built by the same code:

- **r4, the candidate's** (`configs/rule-systems/precision-r4.json`, identity `f50e95de93ac`, pinned in
  `configs/systems/rules-precision.json` and in the plan): r3's rules, with judgement from a **trick estimate**. The
  estimate is a small network (104 inputs, two layers of 192, 159 KB:
  `configs/rule-systems/precision-estimate-r4.json`) fitted by `scripts/fit_rule_estimator.py` to double-dummy
  tables on 64,000 deals of the system's own auctions: from the bidder's hand, the ranges the other three seats have
  shown and the auction itself, the tricks each side takes as declarer in each strain. The general procedure uses it
  four ways, each bounded: it moves its point count for a game by at most two points toward what the estimate
  implies; it bids a small slam up to four points short of the count when the estimate expects 11.5 tricks; over the
  opponents' contract it bids a suit it holds (a known eight-card fit, a six-card suit, a five-card suit up to the
  three level, or no trump with stoppers) when that is worth half an IMP on average, counting its own contract as
  doubled when it fails by two, or at all from the four level; and it doubles their contract from the three level
  when that is worth 3.5 IMPs. The estimate file, the settings that govern its use and a version of that use
  (`JUDGEMENT`) are part of the system's identity.
- **r3** (`configs/rule-systems/precision.json`, identity `7ee5d918af80`): the rules with point count alone. It is
  unchanged: the same calls on 3,000 deals as at commit `5b007c3`, and a test holds its identity. Gen 9's cards are
  built on it.

Double dummy against the house bidder (a team match without card play: the rule pair holds North-South at one table
and East-West at the other, each final contract scored by the deal's double-dummy table; `scripts/tune_rule_bidder.py
measure`), IMPs a board for the rule pair:

| Deals | r3 | r4 | r4 minus r3, same deals |
| --- | --- | --- | --- |
| 16,000 used for no fit, no tuning and no reading of hands (seeds 302, 307, 419, 420) | -1.149 +- 0.042 | -0.672 | **+0.477 +- 0.033** (paired by deal) |
| 32,000 made for this measurement alone (seeds 601 to 608), on a box | -1.233 +- 0.030 | -0.750 +- 0.031 | **+0.483 +- 0.028** (from the spread of the eight seeds) |

Where the IMPs go, on 4,000 of those deals (seed 419), by how the rule pair's contract differs from the house
pair's with the same cards:

| | r3 | r4 |
| --- | --- | --- |
| Different sides declare at the two tables (competition) | -0.43 | -0.19 |
| One pair in game, the other in a part score | -0.25 | -0.25 |
| A slam at one table only | -0.19 | -0.09 |
| The same kind of contract in another strain or at another level | -0.23 | -0.16 |
| All | -1.09 | -0.69 |

r3 sold out: the house pair bought the contract at both tables on 620 of the 4,000 deals, and on 433 against r4. r4
declares 0.96 contracts a board against r3's 0.89, and 5.0% of its contracts go three or more down against 4.4%.
The largest item left is games: the house bids 381 games that r4 stays out of with the same cards, and 215 of them
make; r4 bids 206 that the house stays out of, and 80 make. Its judgement of the games it can see is about right
(moving its game thresholds either way gains nothing); what it lacks is the exchange of information that finds the
others.

How it was built, and what did not work. Every figure above is from deals that took no part in the work: an earlier
round of rule fixes looked like -0.99 on the deals they were made on and was -1.24 on fresh ones. The estimate's
first use, placing games outright by expected IMPs, measured -2.15 (it saved undoubled at the five level, and
partner read strength into the bids); bounding it as above is what turned it round. Choosing the game's strain by
the estimate lost 0.03 +- 0.01 and is not in. Refitting the estimate on the auctions of the bidder that uses it, with
the auction among its inputs, was worth +0.085 +- 0.023 on 16,000 deals; one round of that was done. Five settings
moved when the tuner was run with the estimate in place (lighter preempts: `weak_lo` 5 to 4, `weak_quality` 2 to 1,
`preempt_len` 7 to 6; `game_minor` 28 to 27; `penalty` 25 to 24), worth +0.086 +- 0.028 on 8,000 deals the tuner did
not see.

It is still the weaker bidder of the two, by about two thirds of an IMP a board at double dummy, with exactly known
meanings for the calls its tables define; the calls its general procedure makes are read by rough public ranges, and
the system scorer learns what they show from data.

## What changed in the code

- `bridge_harness/gen5_arena.py`: `auction(board, bidders, systems)` seats a bidding net or a system
  bidder at each seat; `run_board` reads `manifest['systems']`, labels each table `systems:NS|EW` and
  calls `seat_table` on the players before every table. With nothing declared every call and every
  record is as before (`auction_source` stays `gen5-neural-only`).
- `bridge_harness/gen6.py`, `gen7.py`: `seat_table`; the Gen 8 settings on `Gen7Config`
  (`early_play_weight`, `early_pool`, `early_min_effective`, `opponent_play_weight`), absent from a
  Gen 7 bot's settings and so from its identity.
- `ops/gen5_runtime.py`: a bot whose spec has `bidder` bids by that system bidder, built from the
  generator entry and checked against its pin.
- `ops/prepare_gen7_alpha.py`: a plan may give `systems`, and a bot `bidder`, `system_scorer` and
  `lead_systems`; the `system_scorer` artifact must have been built on the bots' hand-fit scorer. A
  plan that uses none of this prepares what it always did.
- `bridge_harness/rule_bidder.py` (the rule bidder and its judgement), `scripts/tune_rule_bidder.py`
  (measure and tune by double-dummy IMPs), `scripts/fit_rule_estimator.py` (the trick estimate),
  `scripts/gen_system_fit.py` and `scripts/train_system_scorer.py` (the system scorer's table).
- `scripts/gen8_match.py` (fork-free matches on fresh deals between any two bots of
  `configs/gen8-proto-bots.json`, with `--book` for auctions bid beforehand), `scripts/gen8_auction_book.py`,
  `scripts/gen8_results.py` (pools the boxes' published results), `scripts/gen8_play_info.py` (what the
  play reading is worth in nats), and the system layer they rest on ([gen8_systems.md](gen8_systems.md)).

## The match mix

Max, 12 November: 15:12 UTC "We should have some Ben boards, but those can come in the arena."; 15:14 "We should
also have some 5 and some 1 for diversity"; 15:15 "Maybe 2 also."

`configs/round8-candidate.json`, per six boards, common bidder `6-32`:

| Pair | Boards in six | What it shows |
| --- | --- | --- |
| `8s-32~71s-32` | 2 | The generation comparison, in common auctions |
| `8c-32~71s-32` | 1 | The Precision bot against Gen 7.1: card play in the common-auction rooms, bidding and play in its own |
| `8c-32~8s-32` | 1 | The two systems against each other: one engine in common auctions, so its own-auction rooms are the bidding |
| `8s-32~5RZ32` | 1 | Gen 8 against Gen 5 (its own bidder; representative layouts, policy on exact ties) |
| `8s-32~1` | 1 | Gen 8 against Gen 1 (the DDS-trained bidder; plain sampling, no nets) |

`configs/round8-candidate-ben.json`, for machines with BEN's servers: `8s-32~ben64` and `8s-32~ben`, one each. It is
Gen 7.1's BEN plan with the candidate in Gen 7.1's place. BEN declares `ben-gib-bbo-8742`; at a BEN table calls and
leads are read as Gen 7.1 reads them, and the play reading (0.5 from trick 1) is what is new and unmeasured.

Bot `2` is not in. It shares bot `1`'s bidder and adds the first belief and policy nets; Gen 8 has no calibrated
reading factor for it and would read it at the default 0.3. Bots `3` and `4` are near twins of each other (same
bidder as `1`, same policy net, belief nets a version apart). The mix, the lanes and the self-play cohorts are Max's
and g7's to set. A self-play cohort of the Precision bot needs `common_bidder` `8c-32`.

## Launch steps

Max said go at 15:32 UTC on 12 November (his words are in the plans' notes), and at 15:33 that every machine on
Gen 7 work, other than those on Gen 9 and other future projects, switches to the Gen 8 arena. The plans are open at
the commit that adds this page. g7 operates the collectors; this is what a collector needs.

1. **Source.** A collector runs this branch at the commit named at the foot of this page or later (it contains the
   Gen 7.1 launch line). Earlier sources do not know `systems`, `bidder` or `system_scorer` and refuse the plan.
2. **Restore the two artifacts** in the checkout: `python models/cardplay/gen7-policy-v4.1-2026-11-12/restore.py`
   and `python models/cardplay/gen8-system-scorer-v1-2026-11-12/restore_model.py`. The trick estimate of the rule
   bidder is a plain file in the tree (`configs/rule-systems/precision-estimate-r4.json`) and needs nothing.
3. **Prepare**, per machine with its own shard:
   `python ops/prepare_gen7_alpha.py --source <source run> --run <run> --plan configs/round8-candidate.json [--shard K/N] --exclude-families <list>`.
   **The list is not optional.** Max, 15:50 UTC: "In general I would never want a bot to play a board in a family it
   has been trained on, other than as a specific experiment to measure that particular effect. Never in the arena."
   The Gen 8 bots play with policy net v4.1, so the list is the families v4.1 was trained on, as for the Gen 7.1
   cohorts; both plans carry `exclude_training_families` and prepare refuses them without a list.
   It refuses a closed plan, a bidder that is not the pinned one, and a system scorer not built on the bots'
   hand-fit scorer. The manifest then carries `systems` (what each bot declares) and a `gen8` block (the rule
   bidder's identity, the scorer's hash).
4. **Preflight**: `python ops/smoke_gen7.py --run <run> --out <report> --deals 2`, as for Gen 7. Done on azure6 with copies of the plans opened under
   `~/work/g8`, the repository's plans closed at the time (prepare refused them as it should). First at `1162aed`
   (13:41 UTC), the four-bot mix: prepared, two deals played (`8c-32~8s-32` at four tables, `8s-32~71s-32` at two),
   records accepted. Then at `478e937` with the wider mix and the BEN lane: both prepared (main cohort `7d8e8ad2af39`,
   `8s-32` `269fdf1854f4` in both plans, `8c-32` `f60c9782f5c8` with rule bidder `f50e95de93ac`, `71s-32`
   `7b0f58b4c403`, `5RZ32` `54591b0880b1`, `1` `5ba471c0a612`); its six-deal play ran into the command's 40-minute
   limit on a box loaded with a match and did not finish. A third run, the play alone on the box with nothing else running, follows the commit that adds this page; its result is on the coordination board. No collector, feed or publisher was started by
   any of this. A BEN board needs BEN's server, so the BEN lane's first preflight is on the machine that has it.
5. **Mix and lanes.** The plan's `pair_weights` is a proposal (above). The BEN lane is
   `configs/round8-candidate-ben.json`, opened and prepared the same way on a machine with BEN's servers; its
   prepare was checked, and its first boards are its preflight, since a BEN board needs the server.
6. **Records.** Every table's `auction_source` is `systems:NS|EW` in a cohort that declares systems
   (`gen5-neural-only` in one that does not), and `bidding_records` name the bidder of each seat. Dashboards and
   exporters that filter on `gen5-neural-only` will not see these tables until they accept the new label.
7. **After it is authorized**: the generation cleanup of `docs/generation-cleanup.md` (Gen 7.1's close-out, this
   source onto main).

## What this package does not do

- **It does not raise leverage.** Gate 1 is not met (above). Retraining the policy net on Gen 8's games will make
  Gen 8 about as much stronger as it made Gen 7.1: not measurably.
- **No BEN board has been played.** The candidate reads BEN's plays at Gen 7's exponent, 0.5, from trick 1; the
  figure is carried over and tuned on nothing. The BEN lane plan is in the package and its first boards are the
  measurement (Max: the BEN boards can come in the arena). If it loses to Gen 7.1's result on BEN, lower the factor.
- **Against a third opponent its edge over Gen 7.1 is not shown** (gate 3 above): the head-to-head result may belong
  to meetings inside the family.
- **The Precision bot is the weaker bidder.** About two thirds of an IMP a board behind the house bidder at double
  dummy. Its job is to put a second, declared system at the table, for the opponents to read and for the next
  policy and scorer to learn from; it is not there to win.
- **One system scorer table, one rule system.** A new version of the rules, of their settings or of the trick
  estimate is a new identity and needs the table trained again (about half an hour on one box:
  `scripts/gen_system_fit.py`, `scripts/train_system_scorer.py`). BEN's system has no table: BEN's calls are read
  as house calls, as in Gen 7.1.
- **Training pipelines that read auctions with the hand-fit scorer** (policy, lead net, scorer retraining on arena
  records) must bind each table's systems (`systems:NS|EW` in the record's `auction_source`) or leave out the tables
  that are not house against house. Read as house calls, the rule system's auctions are wrong (loss 0.7 to 1.3
  against 0.12).
- **Carding is not declared.** `systems` covers bidding only; every bot cards as Gen 7.1 does.
- **The opponent factors are a table by bot id.** A new bot in the roster needs a line, or it is read at 0.3.

## Evidence, and what kind

| What | Kind | Where |
| --- | --- | --- |
| Strength, type and leverage matches | Played. Fork-free matches on fresh deals (`scripts/gen8_match.py`): each board is one deal at two tables with the bots' seats swapped, in common auctions bid by the house net; +- is one standard error over boards | `transfer/gen8-proto-azure1-20261112`, `-azure4-`, `-azure6-`, one folder a match (`results.jsonl`); pooled by `python scripts/gen8_results.py`. Bots: `configs/gen8-proto-bots.json` |
| Awareness and native matches (`a1-8a-v-8p-r4`, `b1-8c-v-8a`, `c1-8c-v-7s`), the all-flat checks (`f1`, `f2`), Gen 7.1 against Gen 6 (`g3-7s41-v-6`) and the tie-break test (`h1-8p41-v-7g41`) | Played, as above; the awareness match plays auctions bid beforehand (`scripts/gen8_auction_book.py`), the native rooms have each bot bid its own system | `transfer/gen8-proto-azure4-20261112` and `-azure6-`, sources `6638547` and `d5f1b66`, seeds 91, 94, 95, 96, 73, 81 |
| The rule bidder against the house bidder | Double dummy, no card play (`scripts/tune_rule_bidder.py measure`) | `configs/rule-systems/precision-r4.json` (`measured`); the box's lines on `transfer/gen8-proto-azure4-20261112:est/final-r3.txt`, `final-r4.txt` |
| The system scorer | Held-out loss on 8,000 deals | `models/cardplay/gen8-system-scorer-v1-2026-11-12/metrics.json` |
| The reading bench and the tree by net | p41's, on stored solves of 530 tables | `reports/gen8-reading-by-net-2026-11-12` on `feature/gen8-p41-20261112`; the coordination board (`box/coordination`), entries of 11:42 and 13:01 UTC |
| The arena path | Preflight on azure6: prepare one shard, play two deals, validate | this page, launch step 4 |

**Checked by another session.** p41 recomputed every match figure on this page from the result rows with a script
of its own (`scripts/gen8_results_check.py` at `82a2ead` on `feature/gen8-p41-20261112`; board entry of 14:19 UTC)
and found them unchanged; no board or deal twice in a match; every board's IMPs the standard scale of its score
difference; and none of the 12,951 distinct deals played among policy v4.1's 34,029 training families. Its remarks
(matches that share deals, the test bot named `8s-32`) are taken into the tables above.

Deals: every match and measurement here is on deals drawn for it by seed; none is an arena deal. p41 checked the
matches' deals against the families policy v4.1 was trained on: none.

## Tested, and not

Tested: the full suite at the commit below (328 passed, 1 skipped). The pieces specific to this package: `tests/test_rule_bidder.py`
(13 tests: no rule fails against an erratic opponent with or without the estimate, legal and finite auctions, the
opening structure and the meanings of calls, r3's identity held, the estimate in the identity, the reckoning of
bidding on and doubling, behaviour with a stand-in estimate), `tests/test_gen8_tables.py` (mixed bidders at one
table, players told each table's systems, the auction book), `tests/test_gen8_launch.py` (the shipped plan closed
and naming the frozen pieces, plans that declare systems, the bots' identities, prepare freezing systems, scorer and
rule bidder, the wrong pin and the wrong base scorer refused, a board whose two rooms seat different systems, a
cohort that declares nothing run as before), `tests/test_gen8_early_play.py` (the engine settings) and
`tests/test_bidding_systems.py` (the system layer). A plan that uses none of the Gen 8 keys prepares what it always did, and with nothing
declared every call and record is as before: the Gen 7 and Gen 7.1 launch tests pass unchanged.

Not tested: a collector, a feed or a publisher with these records (the preflight plays and validates boards; it
starts none of them); the dashboard and the exporters on `systems:` tables; a BEN table; the stop and resume of a
cohort that declares systems; more than two systems in one cohort; a self-play cohort of the Precision bot.

**Source.** The launch files (plan, scorer release, rule system r4) are at `48982f7` on
`feature/gen8-prototype-20261112`; the matches ran at `6638547` (the commit that froze r4) and earlier commits named in
their logs. Prepare at the commit that adds this page or later.
