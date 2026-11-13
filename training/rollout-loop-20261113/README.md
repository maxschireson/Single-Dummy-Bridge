# Stu: the rollout loop, round 0 (13 November 2026)

**Work in progress. Research, not an arena cohort.** Max asked for a self-play loop on the rollout bot and assigned
`azure3` and `azure5` to it (08:23 UTC, 13 November: "Take azure 3 and 5"; 07:46: "Starting this loop matters more
than incremental progress"). He named the loop's bot **Stu** (09:05 UTC). Design notes: `experiments/sid_loop/SPEC.md`.
This folder holds what round 0 runs.
Source: this branch, built on `research/sid-net-s0-20261113` at `24c8091` (the 8X engine at `1a779a9`, the plan
session's `gen7_net.py`, the sidnet session's label heads and trainer).

The plan is in [PLAN.md](PLAN.md). This page is what exists.

## The loop

1. **Play.** The rollout bot plays itself; every decision's record keeps the rollout means of its candidate cards.
2. **Learn.** A net is trained from rollout net v2 on those games added to v2's rows: the card the bot played, and for
   each candidate the tricks its rollouts averaged.
3. **Gate.** The bot with the new net inside is measured against opponents the net was not trained on.
4. Repeat with the new net.

Round 0's Stu is x8's 8Z with rollout net v2 inside (`stu0a`, `stu0b` in `configs/loop-bots.json`, written by
`make_bots.py`; two ids for one bot, because a pair needs distinct ids). The first 250 or so boards of the collection
(run `r0` on azure5, deals under 1,000) were played under the ids `z0a-v2` and `z0b-v2` with capture level 1: the same
bot, card for card.

Since 12:00 UTC on 13 November the collection is pure Stu (`stu0-pa~stu0-pb`; PLAN.md) and plays one table a board
(`run.sh ... --episodes --one-room`): at two tables two ids of one bot play the same cards, because both tables get
the same seed by ply and seat. The opening lead can be rolled out (`stu0-pr`, the engine's `lead` block; PLAN.md, "The
opening lead, three ways").

**What a record keeps.** For every rollout or blend decision: the candidate cards, each one's mean tricks, layouts
played and standard error, and (capture level 2, up to 128 layouts) every layout's result for every candidate with
the layout's weight. Measured on six deals played both ways on azure3: 27.2 KB a board at level 1, 43.1 KB at level 2
with 128 layouts (38.3 KB with 64); the same 416 decisions with the same cards; all 444 candidate means rebuilt from
the per-layout results exactly; CPU a board 51.9 against 53.7 s on a loaded box, a difference six boards cannot
resolve. So a target other than mean tricks (IMPs against the best card, the chance of making) can be built from the
same games.

## Files

| File | What |
| --- | --- |
| `PLAN.md` | What is intended and why: the rounds, round 1, what comes after, what would change the plan, Max's decisions |
| `make_bots.py` | Writes `configs/loop-bots.json` from `configs/x8-bots.json` |
| `run.sh` | One match or collection as a unit; resumes |
| `chain.sh` | A job file's matches one after another |
| `pub.sh` | Pushes rows, summaries and logs to `transfer/rollout-loop-<box>-20261113` |
| `jobs-azure3.txt`, `jobs-azure5.txt` | What each box runs, in order |
| `sample_set.py`, `round1.sh` | Round 1's net, quick variant: Stu's rows with as many rows again of the bots the net knows, trained and scored on the collecting box |
| `make_runs.py`, `runs.json` | Every run with its role, round, bots and deals, for readers of the outputs |
| `DASHBOARD.md` | For the session building the loop's dashboard (Max, 09:30 UTC): where the data is and what to compute |

On a box everything is under `~/work/loop` (own venv, checkout, `sure_cpp` built from
`research/sure-trick-table-20261112` at `2e6ed6d`, a copy of the Gen 7 capture capsule). Deals are a function of
(seed, index). Seed 131 is the gate's and the control's; collections use seeds of their own (round 0: 9001, deals
1,000 to 19,999 on azure5 as run `s0`, 20,000 to 39,999 on azure3 as run `s0b`).

## Measured before round 0 (a 2-core sandbox, seed 131, 300 deals a match, IMPs a board)

Scoring: a deal is bid once by the common bidder and played twice with the two bots' seats swapped, so both tables play
the same contract and the difference is card play. The rollout bot here plays the table net's top card through trick 6;
from trick 7 it rolls out up to four candidates over 32 to 128 layouts, a net choosing every later card of all four
seats (its top card), and plays the best mean of tricks. No search, no claims, no mixing.

| Net inside the rollouts (table net v4.1) | against v4.1 alone | against v4 alone |
| --- | --- | --- |
| v4.1 | +2.69 +- 0.24 | +3.22 +- 0.28 |
| v4 | +1.28 +- 0.20 | +4.05 +- 0.30 |
| v0 | +0.48 +- 0.23 | not run |

- v4.1 alone against v4 alone: +1.18 +- 0.28.
- Paired by deal, v4.1 inside minus v4 inside: +1.41 +- 0.21 against v4.1 alone, -0.82 +- 0.22 against v4 alone. If
  the two effects add: the inside net being the opponent's own net +1.12 +- 0.16, the better net inside +0.29 +- 0.15.
- Rollouts add to the table net alone in all four cells: +1.28 and +2.05 with the mismatched net inside, +2.69 and
  +2.87 with the matching one.
- A rollout bot built wholly on v4.1 against one built wholly on v4: +0.79 +- 0.27 (the nets alone +1.18 +- 0.28 on
  the same deals; paired difference -0.38 +- 0.24).
- Rollouts from trick 3 on v4.1 against v4.1 alone: +4.06 +- 0.56 over 63 deals (stopped early).

What this says and does not say:

- Most of what the inside net is worth in these matches is how well it predicts the players at the table, not its
  quality as a player. A net trained on a bot's games predicts that bot, so a new rollout bot can beat the old one by
  exploiting it. **The gate therefore uses opponents the net was not trained on** (`8p-32-v41`, BEN), with new against
  old reported beside it, not as the verdict.
- Limits: one pair of nets, top-card play on both sides, opponents that are nets alone, 300 deals a match.
- None of these matches is against a search bot. x8's 8Z against Gen 8 card play: -0.38 +- 0.14 (541 boards).

The bots are `n-v41`, `n-v4`, `r7-v41`, `r7x-v4`, `r7x-v0`, `r7f-v4`, `r3-v41` in `configs/loop-bots.json`. The
sandbox's match rows are on `transfer/rollout-loop-sandbox-20261113`.

## The ladder (Max, 09:24 UTC)

Max: "we will push the rollout boundary over time. Should we also be calibrating against pure rollout bots, and rollout
pushed one trick sooner and/or with higher weight?" Each round, the round's net goes inside Stu and inside four bots
that differ from it only in where rollouts take over, and each plays Gen 8 card play (`8p-32-v41`) on the gate's first
500 deals, so rungs are compared deal by deal:

| Bot | Lead, tricks 1 to 2 | Tricks 3 to 6 | From |
| --- | --- | --- | --- |
| `stu0a` (Stu) | search | blend, trust 0.25 | rollouts alone from trick 7 |
| `stu0-b50` | search | blend, trust 0.5 | rollouts alone from trick 7 |
| `stu0-r6` | search | blend, trust 0.25, to trick 5 | rollouts alone from trick 6 |
| `stu0-r3` | search | rollouts alone from trick 3 | |
| `stu0-p` | the net's lead; rollouts alone from the second card on | | no double dummy anywhere; the claims stay |
| `stu0-n` | the net alone: its first card at every trick | | no search, no rollouts, no claims (asked by the dashboard session for Max) |
| `stu0-pl` | the search's lead; rollouts alone from the second card on | | `stu0-p` with a searched lead: the gap is what the net's lead costs (Max, 11:27 UTC) |
| `stu0-pr` | the lead from rollouts: every distinct lead on 512 layouts of the three hidden hands; rollouts alone from the second card on | | `stu0-p` with the lead rolled out (Max, 11:29 UTC; the engine's `lead` block) |

Against `8p-32-v41` on seed 131, IMPs a board +- standard error (boards), rows as of 15:12 UTC on 13 November (`l0-*`
and `l1-*` on azure3's transfer branch, deals 0 to 499; `l0b-*` on azure5's, deals 500 to 999):

| Rung | rollout net v2 inside | rollout net v1 (ft) inside | round 1's net inside |
| --- | --- | --- | --- |
| Stu's own stages | -0.42 +- 0.10 (1,000) | -0.40 +- 0.20 (200) | -0.52 +- 0.19 (200) |
| Pure (the net's lead) | -0.65 +- 0.14 (1,000) | -0.77 +- 0.28 (200) | -0.33 +- 0.27 (200) |
| Pure, searched lead | -0.63 +- 0.18 (500) | | |
| Pure, rolled-out lead | -0.44 +- 0.18 (500) | | |
| The net alone | -2.63 +- 0.32 (200) | -3.27 +- 0.34 (200) | -2.62 +- 0.31 (200) |

By deal:

| Comparison | Deals | IMPs a board |
| --- | --- | --- |
| Pure minus Stu's own stages (v2) | 1,000 | -0.22 +- 0.17 |
| Searched lead minus the net's lead (pure, v2) | 500 | -0.13 +- 0.13 |
| Rolled-out lead minus the net's lead (pure, v2) | 500 | +0.05 +- 0.16 |
| Rolled-out lead minus searched lead (pure, v2) | 500 | +0.19 +- 0.17 |
| Round 1's net minus v2, inside Stu's own stages | 200 | +0.13 +- 0.17 |
| Round 1's net minus v2, inside pure Stu | 200 | +0.22 +- 0.26 |
| Round 1's net minus v2, alone | 200 | +0.01 +- 0.23 |
| v2 minus v1 (ft), inside Stu's own stages | 200 | -0.26 +- 0.21 |
| v2 minus v1 (ft), inside pure Stu | 200 | +0.22 +- 0.27 |
| v2 minus v1 (ft), alone | 200 | +0.65 +- 0.34 |

The rolled-out lead is not the net's first choice in 62% of hands (310 of 498) and the board's result differs on 147
of 500, 82 better and 65 worse. The net's own lead is as good as either other lead to within about 0.15 IMPs a board.
The middle rungs are not played.

## Against BEN (64) (`jobs-azure3-ben.txt`, `ben.sh`; Max, 11:30 UTC)

The gate's first 256 deals, card play only (the common bidder's auction at both tables), in the arena's eight BEN lanes
on azure3; Stu's rollout net is told the opponent is `ben64`. Runs `b0-p`, `b0-g8`, `b0-stu0`, `b0-pr`, each in eight
folders (`b0-p-1` to `b0-p-8`) on azure3's transfer branch.

| | Deals | IMPs a board |
| --- | --- | --- |
| Gen 8 card play against BEN (64) | 256 | +0.09 +- 0.27 |
| Pure Stu against BEN (64) | 256 | -0.27 +- 0.28 |
| Pure Stu minus Gen 8 card play, each against BEN (64), by deal | 256 | -0.36 +- 0.31 |
| Pure Stu against Gen 8 card play head to head, the same deals | 256 | -0.91 +- 0.28 |

Measured against BEN, pure Stu is no further behind Gen 8 than head to head (Max had expected it to do less well
against BEN). Stu's own stages and the rolled-lead bot against BEN (64) follow (about 16:50 and 17:45 UTC).

On BEN's own cards the fusion ledger counts 11 guaranteed contracts given up in 2,405 decisions holding one (0.46%);
Gen 8 card play in the same matches 11 in 945 (1.16%).

## The fusion ledger (`fusion_ledger.py`; Max, 11:16 UTC)

A count with no opponent in it, from any run's full records: in the last seven tricks, with the contract still open,
how often the declaring side's card gives up a contract it held guaranteed from its own view (the exact single-dummy
solver: against every split of the unseen cards and every defence), and how often a defender's card leaves declarer
holding such a guarantee when another card would not have (in the deal as it lies). It runs on azure3 every half hour
over the ladder's records and is published as `ledger/ledger.json` and `ledger/ledger.txt` on azure3's transfer branch.

What it is not: a pure count of strategy fusion. A bot that maximizes mean tricks also gives up a sure contract when
it plays for an overtrick, and that is counted too. Stu keeps a guaranteed contract by rule in games, slams and doubled
contracts (0 of 5,474 such decisions given up, which checks the ledger against the engine) and has no such rule in
undoubled partscores.

First numbers, 12:08 UTC, all ladder runs pooled (games, slams, doubled | undoubled partscores):

| Bot | Declaring: gave up / held | | Defending: handed over / had the choice | |
| --- | --- | --- | --- | --- |
| Gen 8 card play (`8p-32-v41`) | 81 / 6,818 (1.19%) | 55 / 3,793 (1.45%) | 32 / 587 (5.5%) | 79 / 761 (10.4%) |
| Stu's own stages, v2 | 0 / 1,911 | 12 / 983 (1.22%) | 12 / 201 (6.0%) | 17 / 143 (11.9%) |
| Pure Stu, v2 | 0 / 1,937 | 7 / 990 (0.71%) | 6 / 212 (2.8%) | 17 / 135 (12.6%) |
| v2 alone | 3 / 600 (0.50%) | 6 / 295 (2.03%) | 4 / 44 (9.1%) | 14 / 84 (16.7%) |
| v1 (ft) alone | 5 / 562 (0.89%) | 3 / 304 (0.99%) | 10 / 63 (15.9%) | 11 / 49 (22.4%) |

"Held" counts decisions, so one contract held over several cards counts several times; "gave up" counts cards. Gen 8
gives up a guaranteed contract about once in 13 hands it declares (136 in 1,798). The counts for the nets alone are too
small to rank them; the collection's records (thousands of boards, any bot) can be read the same way.

## Round 1's rows and trainer (in this branch, tested on six recorded boards)

- `scripts/gen7_build_dataset.py --rollout-gap --alias stu0a=stu0,stu0b=stu0,z0a-v2=stu0,z0b-v2=stu0 --policy-only`
  turns Stu's records into rows. A decision made by rollouts alone gets, for each candidate and the cards touching
  it, its deficit to the best candidate in the deciding side's tricks: paired layout by layout where the record has
  the per-layout results, else the difference of the means. The row's other legal cards were not rolled out and
  are marked -1. Search decisions (tricks 1 to 2) and blend decisions (tricks 3 to 6) keep the search's gap as for
  any search bot; claims and forced choices are policy rows. Checked against the engine's own functions on the six
  preflight boards (502 rows, 162 of them rollout rows; largest difference 0.001, the float16 rounding).
- `scripts/train_rollout_net.py` leaves the -1 cards out of the gap loss and scores regret on rated cards only
  (`rated_pick` is the share of rows where the net's own card is one the bot rated). `--init-as stu0=8s-32` starts
  Stu's two vectors from those of the bot round 0's rollouts were told to expect.
- Tests: `tests/test_loop_dataset.py`.
- The card target is the card played. Where the declarer mixed equal cards the record also has the probabilities;
  using them as a soft target is not done (the played card is an unbiased sample of the same target).

## Not yet done

- Round 1's set: Stu's rows joined to v2's, and the training run.
- The gate against `8p-32-v41` (its baseline is queued on azure3 behind the collection) and the control at ten times
  the deals.
