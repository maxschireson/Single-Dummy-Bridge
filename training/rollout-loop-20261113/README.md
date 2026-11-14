# Stu: the rollout loop, round 0 (13 November 2026)

**Work in progress. Research, not an arena cohort.** Max asked for a self-play loop on the rollout bot and assigned
`azure3` and `azure5` to it (08:23 UTC, 13 November: "Take azure 3 and 5"; 07:46: "Starting this loop matters more
than incremental progress"). He named the loop's bot **Stu** (09:05 UTC). Design notes: `experiments/sid_loop/SPEC.md`.
This folder holds what round 0 runs.
Source: this branch, built on `research/sid-net-s0-20261113` at `24c8091` (the 8X engine at `1a779a9`, the plan
session's `gen7_net.py`, the sidnet session's label heads and trainer).

The plan is in [PLAN.md](PLAN.md). This page is what exists.

## Names (Max, 01:26 UTC on 14 November)

**SiD** is any bot with no double dummy in its play; then its flavor; then the net inside its rollouts (the table net is
policy v4.1 unless said). The loop's nets are **Stu R0** (rollout net v2, where the loop started), **R1** (v2 with
Stu's own vectors), **R2**, **R3a** (interim), **R3**. Earlier sections keep the ids they were written with.

| Name | What it is | Ids |
| --- | --- | --- |
| SiD (rollout) Stu R3 | every card from rollouts, the lead included (at most 4 candidates, 32 then up to 128 layouts with the race), round 3's net inside: the collection since 00:45 UTC on 14 November | `stu3-ps` (`stu3-psa~stu3-psb`) |
| SiD (rollout) Stu R0 | the same with v2 inside: the collection from 22:53 to 00:45 UTC | `stu0-ps` |
| SiD (rollout, net lead) Stu R0, R2, R3 | rollouts from the second card on, the lead from the table net ("pure Stu") | `stu0-p`, `stu2-p`, `stu3-p` |
| SiD (rollout, 512 lead) Stu R0 | every lead card on 512 layouts of the three hidden hands | `stu0-pr` |
| SiD (net) Stu R0, R2, R3 | the net's own first card at every trick, nothing else | `stu0-n`, `stu2-n`, `stu3-n` |
| Stu-as-is, Gen 8 card play (not SiD) | both use double-dummy search | `stu0a`, `8p-32-v41` |

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

| Against BEN (64), 256 deals | IMPs a board | Minus Gen 8's result, by deal | Against Gen 8 head to head, the same deals |
| --- | --- | --- | --- |
| Gen 8 card play | +0.09 +- 0.27 | | |
| Stu's own stages | -0.02 +- 0.25 | -0.11 +- 0.27 | -0.57 +- 0.18 |
| Pure Stu | -0.27 +- 0.28 | -0.36 +- 0.31 | -0.91 +- 0.28 |
| Pure Stu, rolled-out lead | -0.08 +- 0.26 | -0.18 +- 0.29 | -0.80 +- 0.27 |

Every bot is within noise of level with BEN (64), and each Stu is closer to Gen 8 when both are measured against BEN
than head to head (Max had expected pure Stu to do less well against BEN). By deal against BEN: pure Stu minus Stu's
own stages -0.25 +- 0.29; the rolled-out lead minus the net's lead +0.19 +- 0.18.

On BEN's own cards the fusion ledger counts 11 guaranteed contracts given up in 2,405 decisions holding one (0.46%, at
15:58 UTC); Gen 8 card play in the same matches 11 in 945 (1.16%).

## Round 2's rungs (`jobs-azure5-r2.txt`, `jobs-azure6-r0c.txt`, `jobs-azure6-r2.txt`, `jobs-azure6-r2s.txt`)

Against Gen 8 card play on the gate's deals 500 to 699, by deal against pure Stu with v2 on the same deals (`l0b-p`,
-0.84 +- 0.27 there):

| | Run | IMPs a board against the reference |
| --- | --- | --- |
| Round 2's net in the rollouts | `l2b-p` | -0.11 +- 0.32 |
| Round 2's net in the rollouts and at the table | `l2b-pt` | -0.15 +- 0.34 |
| Round 2's net, its value head steering the simulated seats | `l2b-pv` | -0.01 +- 0.28 |
| Control: v2 at the table too | `l0b-pt` | -0.20 +- 0.32 |
| Control: v2's value head steering the simulated seats | `l0b-pv` | -0.04 +- 0.35 |

The nets alone on deals 500 to 999: v2 -2.63 +- 0.21 (500); round 2's net (epoch 1) -2.43 +- 0.20 (500), by deal
+0.20 +- 0.17; the longer-trained variant (`train-r2s/`, epoch 5 under `--select stup0 --forget 0.02`) -2.54 +- 0.24 at
358 deals, by deal against v2 +0.18 +- 0.21. Inside the full bot the net's change does not show; alone it points the
right way without being established, and more epochs on the same tables add nothing.

## Round 3 (`round2.sh r3`, 23:09 to 23:29 UTC; `train-r3/`, sha256 `a8cf8a94ebcf...`)

About 28,000 pure-Stu tables: azure5's own (7,233 trained on; the 300 newest of `spr0` held out to choose the epoch,
the 300 newest of `sp0` held out as a test set that makes no choice) and every row block and cut file of the other four
boxes. Four epochs at 1e-4 from round 1's net with as many replay rows; epoch 4 chosen. Gen 8's held-out log-loss 0.458
to 0.473 (the limit is +0.02).

Indicator 1 on the test set (tricks the net's card gives up against the rollouts' values, a decision; paired, SE by
deal; the test tables have the net's own lead, so no lead rows):

| Policy head | Tricks 1 to 4 | 5 to 8 | 9 to 13 | All |
| --- | --- | --- | --- | --- |
| round 1's net (the start) to round 3's | -0.0057 +- 0.0014 | -0.0023 +- 0.0021 | +0.0019 +- 0.0030 | -0.0025 +- 0.0012 |
| round 2's net to round 3's | -0.0038 +- 0.0013 | -0.0019 +- 0.0020 | +0.0030 +- 0.0028 | -0.0013 +- 0.0011 |
| the interim net (r3a) to round 3's | -0.0012 +- 0.0009 | -0.0023 +- 0.0012 | -0.0018 +- 0.0011 | -0.0018 +- 0.0006 |
| Value head, start to round 3's | -0.0064 +- 0.0016 | -0.0022 +- 0.0023 | -0.0049 +- 0.0027 | -0.0045 +- 0.0013 |

## Label quality, tables against positions, and the rollout budget (Max, 22:26 to 22:31 UTC)

`exp_labels.sh` on azure6's 5,100 pure-Stu tables (train split; no replay rows), each net from round 1's for 3 epochs,
the epoch chosen on the validation split of every published block and cut file, scored on their test split (1,997
deals, 63,902 decisions; full labels). Tricks the policy's card gives up, a decision, paired against the net trained on
every table with full labels:

| Net | Policy head | Value head |
| --- | --- | --- |
| round 1's (the start) | +0.0028 +- 0.0004 | +0.0041 +- 0.0005 |
| a quarter of the tables | +0.0013 +- 0.0003 | +0.0018 +- 0.0004 |
| half the tables | +0.0007 +- 0.0003 | +0.0012 +- 0.0003 |
| half the decisions of every table | +0.0007 +- 0.0003 | +0.0005 +- 0.0003 |
| labels from 32 of the layouts | +0.0003 +- 0.0002 | |
| labels from 16 | +0.0009 +- 0.0003 | |
| labels from 8 | +0.0016 +- 0.0003 | |

- A doubling of the tables is worth about 0.0007 a decision. The same rows from half the tables (every decision) or
  from every table (half the decisions) give the same policy (0.0000 +- 0.0002): learning goes with positions.
- Labels from 16 layouts on every table equal full labels on half the tables (-0.0002 +- 0.0003); from 8, full labels
  on a quarter (-0.0003 +- 0.0003). A decision costs 0.26 s at 32 or 64 layouts and 0.35 s at 128 (fixed costs, reading
  the layouts and the claims test, dominate low budgets), so fewer rollouts would not buy more learning a CPU-hour.
- The labels come from K of the recorded layouts on which every candidate was played (drawn at random), and the card
  learned is the one best over them; the line played after the decision is still the 128-layout bot's.

`bench/budget.py`, 997 rollout decisions of `sp0d` played again at other budgets, each card scored against a 1,024-layout
rollout of every legal card: at 128 layouts and 4 candidates pure Stu gives up 0.037 tricks a decision to it; 512
layouts +0.001 +- 0.002 (0.83 s a decision against 0.35), 256 +0.002 +- 0.002, 6 candidates -0.0001 +- 0.0013, no race
+0.001 +- 0.002, 64 layouts +0.003 +- 0.002 (0.26 s), 32 layouts +0.007 +- 0.003. The budget is saturated at 128. The
reference rates by the same rollouts, so this is the noise part of the budget's cost, not whether the values are right.

## Round 3 at the table (00:00 to 02:20 UTC on 14 November)

| Test | Result (IMPs a board) |
| --- | --- |
| SiD (net) Stu R3 against Gen 8, by deal minus SiD (net) Stu R0, deals 0-999 | +0.18 +- 0.14 (1,000) |
| the same, minus SiD (net) Stu R2, deals 500-999 | -0.14 +- 0.18 (500) |
| **SiD (net) Stu R3 head to head against SiD (net) Stu R0**, gate seed deals 1,000-4,999 (`h3-n`) | **+0.40 +- 0.07 (4,000)** |
| **SiD (net) Stu R3 head to head against SiD (net) Stu R2**, the same deals (`h32-n`) | **+0.19 +- 0.06 (4,000)** |
| SiD (rollout, net lead) Stu R3 against Gen 8, minus Stu R0's, deals 500-999 (`l3-p` against `l0b-p`) | -0.09 +- 0.19 (500) |
| SiD (rollout, net lead) Stu R3 against BEN (64), minus Stu R0's, deals 0-255 (`b3-p` against `b0-p`) | +0.21 +- 0.22 (256) |
| SiD (rollout) Stu R3 head to head against SiD (rollout) Stu R0, gate seed deals 5,000-6,999 (`h3-p`, `h3-pb`) | see PLAN.md |

## Round 3 inside the rollouts, diagnosed (02:30 to 05:45 UTC on 14 November)

The net got better alone (head to head R3 against R0 +0.40 +- 0.07) and not inside the rollouts (-0.13 +- 0.09). What
was tried, IMPs a board, +- standard error (boards); "reference" is SiD (rollout) Stu R0 (`stu0-ps`):

| Test | Result |
| --- | --- |
| The seats draw from the net: R3 told it is Stu is flatter (0.94 nats against 0.55), its drawn card gives up more (`draw_regret.py`) | top card 0.0608 against R0's 0.0631; drawn 0.0791 against 0.0731 tricks a decision |
| R3 inside, the draw sharpened (power 2), by deal minus plain draw (`h3-p2`) | +0.05 +- 0.17 (1,000) |
| R3 inside, the seats play the top card, by deal minus plain draw (`h3-pg`) | -0.01 +- 0.17 (1,000) |
| R3 inside **and at the table** (one net, `stu3-pst`), head to head against the reference (`h3-pt`, `h3-ptb`) | **+0.16 +- 0.09 (2,000)** |
| the one-net bot against Gen 8, by deal minus R3 inside only (`l3-pst` against `l3-p`) | +0.12 +- 0.23 (500) |
| the one-net bot against BEN (200), by deal minus R3 inside only (`b3-pst200` against `b3-ps200`), partial | -0.17 +- 0.35 (237) |
| R3 inside, blind (told nothing about its opponent), against Gen 8, by deal minus `l3-p` (`l3-pu`) | -0.09 +- 0.20 (500) |
| A net from Gen 8's rows only against one from as many rows of v2's mix (top card on Stu's rows; `exp_strong.sh`) | STRONG 0.0716, MIX 0.0746 at 512 wide; full v2 0.0631: volume with bot ids beats subsetting |

Sharper seats do nothing. One net helps against its own family; against outside opponents it is not yet shown (the
1,024-board BEN pair and the Gen 8 pair are queued). The worry (Max): a net at the table that was trained on an
opponent's games reads that opponent's cards, which is knowledge of the opponent, not strength.

**Where the tricks go** (`bench/dd_ledger.py`: every card rated by double dummy on the deal as it lay; hindsight, which
flatters Gen 8; SiD (rollout, net lead) Stu R3 and Gen 8 against each other, `l3-p`, 994 tables each):

| Tricks given up a table | SiD | Gen 8 |
| --- | --- | --- |
| opening lead | 0.120 | 0.103 |
| declaring, tricks 1-4 / 5-8 / 9-13 | 0.153 / 0.100 / 0.022 | 0.106 / 0.099 / 0.031 |
| defending, tricks 1-4 / 5-8 / 9-13 | 0.136 / 0.093 / 0.024 | 0.111 / 0.055 / 0.013 |
| cards that turn the contract, a 100 tables | 17.5 | 13.5 |

SiD's tricks go early and in defence; of them 0.479 a table were a candidate the rollouts rated lower, 0.048 a card the
net's prior left out. Against BEN (200) the same split holds for SiD R0, R3 and the one-net bot.

**BEN (200) baselines**, deals 0-255: SiD (rollout) Stu R0 -0.13 +- 0.24, R3 -0.04 +- 0.26, Gen 8 -0.16 +- 0.26 (R3 minus
R0 by deal +0.09 +- 0.29). **The gate is BEN (200)** (Max, 04:23 UTC); matches against our own bots and Gen 8 are diagnostics.
BEN is installed on azure2 and azure6 as on azure3 (`ben_install.sh`, checked against `ben/manifest.json`).

**BEN in the training data:** in round 3's set BEN is at the table in 528 of 30,816 deals (1.7%; 2.8% of rows, half of
them BEN's own cards), all from the replayed pre-loop set (17.8% of its deals). The loop's own collections have none.

**The guarantee and Pavlicek's fifty trump strip squeezes** (`tests/test_squeeze_endings.py`; test positions only, never
trained on): double dummy agrees with his count and lead in all fifty. As drawn, five are certain from declarer's view;
the rest depend on which defender holds cards of a suit both still hold, which no show-out settles. In the 25 versions
where show-outs fix every card (20 of the 50 techniques) the logic finds his count every time, each lead rated as
double dummy rates it.

**Noise in the data from 05:40 UTC** (Max, 05:37): Gen 8 had none (`near_tie` 0, its net's favourite among exact ties).
Its self-play is now played by its personalities at margin 0 (`bridge_harness/style.py`: among exactly tied cards the one
the style prefers, a random one 15% of the time), six pairs in turn; Stu's self-play twins mix their defenders' equal cards.

**Boxes from about 06:15 UTC** (Max, 05:24 and 05:30): azure1 and azure5 Gen 8's self-play (azure5 after about 3 hours of
style calibration), azure2 and azure6 the one-net Stu R3's self-play, azure3 the test box (BEN through the release, then
the other tests). Round 4 is cut after about 6 hours of collection (about 43,000 tables), with the arena's Gen 8 and Gen 9
feeds (about 21,500 boards without BEN), and gated on BEN (200) on the 2,560 deals the one-net Stu R3 has played there.

## Human boards as training data (`exp_human.sh`, `usbc/human_episodes.py`, `usbc/human_sets.py`; Max, 09:25 to 09:45 UTC on 14 November)

Max: "Take the adult boards. Train a net on them. Have it play, net only, against a net trained on the same number of bot
boards"; then "fine tuned model and from scratch", "rollouts on both", the human boards "with a medium set of other
boards", "with higher weights"; "this is the big question". azure5 was lent to it from 09:50 UTC (its Gen 8 collection
paused). The boards are the adult USBCs (Open, Senior, Mixed, Women's) of 2021 to 2023 from the vugraph records; the
target is the card the expert played (no rollout values); the net knows them as a bot of its own, `usbc`. **The 2025
USBCs and every junior event stay test data**, and a net trained on these tables can be benchmarked on nothing else of the
USBCs. A familiar auction is one whose every call the common bidder gives at least 0.05: 3,841 of the 22,269 usable
tables (17%), on 1,556 of the 3,569 deals.

Matches are the nets alone (first card, no rollouts) on the gate's seed from deal 30000, IMPs a deal for the first net,
by deal. "Offline" is the tricks the net's first card gives up against the rollouts' values on 998 held-out boards of the
one-net SiD's self-play (32,596 rated decisions), paired, the standard error clustered by deal (`regret_pairs.py`).

| Question | Nets | Match | Offline |
| --- | --- | --- | --- |
| Teacher against teacher, 1,556 boards each, from scratch (256 wide) | human boards against SiD self-play boards | **+0.94 +- 0.09** (4,000) | 0.101 against 0.106 |
| The same, round 3's net fine-tuned (4 epochs at 1e-4) | human against SiD boards | +0.14 +- 0.05 (8,000) | 0.0645 both (round 3's net 0.0659) |
| Both together, playing as SiD | against SiD boards alone | +0.08 +- 0.04 (8,000) | -0.0006 +- 0.0005 |
| Round 4 in small: round 1's net tuned as a round is on 10,000 pure-Stu boards (0.0676 offline), with human tables added | 1,556 (one familiar table a deal) | +0.08 +- 0.04 (6,000) | -0.0013 +- 0.0003 |
| | those four times over | +0.20 +- 0.05 (6,000) | -0.0017 +- 0.0004 |
| | 3,841 (every familiar table) | +0.17 +- 0.05 (4,000) | -0.0015 +- 0.0004 |
| | 22,269 (every table, auctions as bid) | **+0.24 +- 0.06** (4,000) | -0.0016 +- 0.0005 |
| | 22,269, the unfamiliar auctions blanked | +0.23 +- 0.06 (4,000) | 0.0660 against 0.0676 |
| From scratch on those 10,000 boards (512 wide), with the 1,556 | against without | +0.21 +- 0.11 (2,000) | -0.0014 +- 0.0009 |
| From scratch at full size (512 wide, 6 epochs): every human table (22,269; 630,296 rows) | against as many pure-Stu boards (920,187 rows) | -0.03 +- 0.11 (2,000) | 0.0754 against 0.0787 |
| The same, both sets together, playing as SiD | against the pure-Stu boards alone | **+0.79 +- 0.08** (4,000) | 0.0730 against 0.0787 |
| The same, both sets together | against the human tables alone (Max, 14:31 UTC: do bot boards add to the human ones?) | **+0.71 +- 0.08** (4,000) | 0.0730 against 0.0754 |
| Inside the one-net rollout bot (250 deals each): the 10,000-board net with the 1,556 four times over | against without | +0.22 +- 0.27 | |
| Inside it: round 3's net fine-tuned on the human boards | against on SiD boards | +0.27 +- 0.28 | |
| Inside it: the from-scratch net of the human boards (1,556) | against the SiD boards' | -0.01 +- 0.32 | |

- **The human boards are the better teacher board for board**, by nearly an IMP a deal from scratch, although a human board
  carries fewer decisions (29 against 41: experts claim earlier) and no values.
- **Added to SiD's own boards they help at every dose, and more of them helps more** in the matches (+0.08, +0.17, +0.20,
  +0.24). Offline the gain is there at the smallest dose and does not grow clearly (-0.0013 to -0.0017 a decision, about
  0.05 tricks a board; the opening lead gains most). The 10,000-board net with human tables scores what round 3's
  28,000-board net does (difference 0.0000 +- 0.0005).
- **Unfamiliar auctions cost nothing**: every table as bid and every table with the unfamiliar auctions blanked play the
  same (+0.24, +0.23), so the 18,428 tables our bidder would not have bid that way are as usable as the others.
- **At full size the two teachers are equal board for board** (-0.03 +- 0.11), and together they beat Stu's boards alone by
  +0.79, and beat the human tables alone by +0.71: at this size each set adds about as much to the other, so most of
  the gain is twice the data, and Stu's boards still add on top of the human ones. (This is from scratch at 44,000
  tables; it does not say how much more bot boards add at round 4's 103,000 deals on top of round 3's net.) The
  22,269 human tables are 3,569 deals, about six tables each. As data they are worth about what 22,000 self-play tables
  are, which is about 18 box-hours of the one-net bot.
- **Inside the rollout bot it does not show**: three matches of 250 deals, +0.22, +0.27 and -0.01, each +-0.3. The last
  is the pair that differs by +0.94 alone: a net nearly an IMP better alone made no visible difference inside the
  rollouts. A better net alone is not yet a better bot; an effect of 0.1 to 0.2 inside needs several thousand deals.
  That is the BEN gate's job (round 4 below).
- Not finished: every table against the familiar tables only, directly (`xh-m10A-F`, stopped at 1,134 deals for round 4's
  cut), and blanked against as bid directly (`xh-m10B-A`, not started); two more rollout pairs (`xh-s10h-p`, `xh-m10h-p`).
- Void: `xh-s10h-n` (its two nets were kept at different epochs; replayed as `xh-s10h-n6`). A from-scratch net's epoch is
  not chosen by its log-loss on the one-net bot's rows: that rises while the tricks given up fall (the rows' defenders
  mix their equal cards), so the last epoch is kept.

**Round 4 is therefore cut in two nets** (Max, 09:39: "If we aren't sure we can do a R4a and an R4b"): `stu4`, the round as
planned plus every human table (as bid; they draw no replay rows, `round2.sh` NOREPLAY, so both nets train beside the same
replay), and `stu4c`, the control without them. Both are gated blind on BEN (200) in turns on the same deals
(`jobs-azure3-ben8.txt`), after a nets-alone match between them (`jobs-azure5-r4.txt`).

**The cut (12:41 to 12:56 UTC on 14 November)**: 46,494 loop tables since round 3's cut (the one-net SiD's self-play 15,768,
pure Stu with round 3's net 7,192, pure Stu on rollouts alone 7,641, Gen 8's self-play 15,893), with round 3's 28,000
about 3.1 million rows; and 23,067 arena records not in v2's set (1,157 with BEN, 1.7% of the round's new boards).
**The first try at the training failed in its sizing** (`loop-201`, 12:50 UTC): an arena record carries about 600 rows
(root and fork tables, both rooms), so the arena came to about 14 million rows against the loop's 3.1 million; with as
many replay rows again the set would have been about 30 million rows, more than azure5's free disk (26 GB) and two hours a
net. It was also sent as one long command, which holds the box's queue until it ends. `round4.sh` is the round as it
should be, a unit of its own: the arena's rows from a sample of the records (500 of the BEN feed, 2,100 of the others,
about 1.5 million rows), a third as many replay rows (arena and replay together about the loop's rows, the share other
bots' rows had in round 3), each net's big files removed when it is done, nothing started under 14 GB of free disk.

**Round 4 as trained (14:09 to 15:16 UTC)**: the arena sample 2,600 records, 1,719,627 rows; 12,101 own records (498,784
rows; 300 held out, 300 for the test); 68 row files from the other boxes; 1,591,633 replay rows (3,972 of v2's deals); the
human tables drawing no replay. Training set 102,811 deals, 6,996,453 rows; round 1's net, 4 epochs at 1e-4, about 25
minutes a net. `stu4` sha256 edc5d6cf..., `stu4c` e4b689c8...

| Offline, tricks the first card gives up a decision (paired, SE by deal) | All | Tricks 9-13 |
| --- | --- | --- |
| Round 3's net -> stu4, round 4's test set (300 deals, 9,522 rows) | -0.0012 +- 0.0008 | -0.0043 +- 0.0021 |
| Round 3's net -> stu4c, the same | -0.0015 +- 0.0008 | -0.0042 +- 0.0022 |
| stu4c -> stu4, the same | +0.0003 +- 0.0006 | -0.0001 +- 0.0016 |
| stu4c -> stu4, the one-net SiD's held-out rows (998 deals, 32,596 rows) | **-0.0010 +- 0.0003** | -0.0013 +- 0.0008 |

Together the two test sets give stu4 about -0.0007 +- 0.0003 a decision over the control (about 0.03 tricks a board),
smaller than the -0.0013 to -0.0017 of the small version, where the human rows were a larger share. Round 3's blind
baseline against BEN (200) finished at -0.09 +- 0.09 (2,047 deals); round 4's gate began on azure3 at 14:55 UTC.

| Round 4's two nets (`jobs-azure5-r4.txt`, seed 131) | IMPs a deal for the first |
| --- | --- |
| stu4 against stu4c, nets alone | +0.03 +- 0.03 (8,000) |
| stu4 against round 3's net, nets alone | +0.10 +- 0.06 (4,000) |
| stu4c against round 3's net, nets alone | +0.09 +- 0.05 (4,000) |
| stu4 against stu4c, each inside the one-net rollout bot | **-0.10 +- 0.17** (500) |
| Blind against BEN (200), first 512 deals: stu4; R3 on the same deals -0.10 | -0.28 +- 0.19 (paired against R3 -0.19 +- 0.20) |

**No gain from the human tables reaches the bot**, so by Max's rule (15:39 UTC) and his preference for a net trained only on
bots (15:50), **stu4c is round 4's net**. stu4's gate blocks c to e are dropped (commented in place in the running job
file at 16:36 UTC, same length, so the chain's offsets do not move); azure3 plays stu4c alone through its 2,048 deals.

## The rollouts' values against the table (`bench/value_check.py`; Max, 17:11 UTC on 14 November: "Should we experiment with different rollout mechanisms?")

For every rollout decision in recorded tables: declarer's tricks the rollouts expected with the card played (and the
chance they gave the contract, from the kept layouts) against declarer's tricks at that table. Standard errors by table.
A read-only pass over the records (seconds a thousand tables).

| Records | Declaring: expected minus took | Defending | The lead | Contract's chance minus share made: declaring, defending |
| --- | --- | --- | --- | --- |
| R3 blind against BEN (200), the gate's 2,039 deals (`bu3-pst200a` to `e`) | +0.074 +- 0.014 | -0.180 +- 0.013 | -0.152 +- 0.026 | +0.034 +- 0.006, -0.069 +- 0.005 |
| stu4 the same, 510 deals | +0.102 +- 0.029 | -0.175 +- 0.025 | -0.132 +- 0.055 | +0.043 +- 0.012, -0.063 +- 0.011 |
| stu4c the same, 382 deals | +0.070 +- 0.031 | -0.129 +- 0.032 | -0.059 +- 0.062 | +0.032 +- 0.013, -0.062 +- 0.013 |
| R3's self-play (`sp3s`, 2,500 tables; the two ids) | +0.086 +- 0.017, +0.090 +- 0.018 | -0.137 +- 0.016, -0.147 +- 0.016 | -0.119 +- 0.034, -0.106 +- 0.034 | +0.024, +0.029 +- 0.008; -0.028, -0.037 +- 0.007 |
| R0's self-play (`sps0`, 779 tables; the two ids) | +0.094 +- 0.031, +0.090 +- 0.029 | -0.153 +- 0.027, -0.141 +- 0.029 | -0.145 +- 0.061, -0.132 +- 0.060 | +0.028, +0.034 +- 0.013; -0.036, -0.035 +- 0.011 |

- **The values are optimistic for the side deciding**: declaring the rollouts expect about 0.07 to 0.10 tricks more than
  declarer then takes, defending 0.13 to 0.18 fewer than declarer then takes, at the lead 0.11 to 0.15 fewer. Against BEN
  and in self-play, with round 0's net and round 3's and both of round 4's: the rounds have not moved it.
- By stage against BEN (R3): declaring +0.01 at trick 1, +0.03 at trick 2, +0.06 at tricks 3-4, +0.10 at 5-8 and 9-13;
  defending -0.20, -0.24, -0.23, -0.20 and -0.10. It does not vanish with few cards left.
- **Contract odds against BEN**: when the defending bot's rollouts give declarer 50%, BEN makes 63% (tricks 1-4) and 69%
  (later); 30% is 43% and 47%; 70% is 80% and 83%. When the declaring bot's rollouts give itself 50% it makes 46% (tricks
  1-4) and 38% (later); 70% is 65% and 56%. In self-play the defending side's gap is about half of that (50% is 55-58%
  early, 57-63% later); declaring the same as against BEN.
- **Not sampling noise**: the optimism grows with how clear the choice was (R3 against BEN; the card played ahead of the
  next candidate by under 0.05 tricks, 0.05-0.2, 0.2-0.5, 0.5 and more): declaring +0.036, +0.081, +0.135, +0.093;
  defending +0.110, +0.215, +0.269, +0.226 (each +- 0.01 to 0.02). A winner's curse on noisy means would be largest for
  the close choices. (And 128 layouts are saturated, `bench/budget.py` above.)
- A level error common to every candidate changes no choice; this says the values are wrong in a way that favours the
  card chosen, not what it costs in IMPs.

**The oracle test** (`bench/oracle_layout.py`, azure1, 05:48 UTC on 14 November; R3 pure Stu's 1,459 rollout decisions to
trick 4 on 120 boards of `l3-p`, each card rated by double dummy on the deal as it lay): the recorded card gives up 0.0569
tricks a decision, the bot's card on layouts drawn again 0.0589 (it plays the recorded card again at 57% of the
decisions), and its card when every layout rolled out IS the deal 0.0288 (below "again" by 0.0302 +- 0.0067; declaring
0.0285, defending 0.0291). So about half of the early tricks go with not knowing the cards and half remain when they
are known: the simulated play itself.

**Reading (untested):** the simulated seats draw their cards from the net's probabilities, mistakes included (`seat:
draw`, no cut), and the real players, BEN or the bot, make fewer; a line that needs a mistake is rated above its worth.
The engine's stage already has the settings to test it (`seat` top or draw, `power`, `cut`, and `seat_other`,
`power_other`, `cut_other` for the side not deciding); at the table the two tried (top card, power 2) were within
+-0.17 of the plain draw over 1,000 deals each, which cannot see 0.1.

## Round 4 adopted; the gate, the rows and the net's size (14 November, 17:27 to 18:45 UTC)

**Adopted without the full gate** (Max, 17:27: "Too much time testing relative to learning"; 17:34: "I think we should likely
adopt. I also don't know if it's even worth the long test; maybe we only do that every few releases?"; 17:57: "New collections
should flip"). stu4c plays the one-net self-play on azure2 (`sp4t`, from 17:41) and azure6 (`sp4tb`, 17:43). The BEN gate was
stopped at 698 deals of stu4c: on its first 512, +0.01 +- 0.17 against BEN and +0.10 +- 0.20 by deal against round 3 (it read
+0.36 at 306 deals and +0.17 at 466). A full gate (2,048 deals, 5.3 hours of a box) resolves 0.10; a round moves the net alone
by about 0.1 and the bot by a quarter of that, so rounds are judged on the offline test and the nets-alone match, and the gate
is kept for a change of mechanism or a release.

**The exponent, counted on the pool.** The 0.37 of the Gen 7 series is per doubling of everything the net trains on. The pool
before the loop is 30.4M rows; round 3 added 1.15M, round 4 another 3.6M (1.26M of Stu's, 0.65M of Gen 8's self-play, 1.7M of
the arena's): +11.6% from round 3 to round 4 (+4.0% counting Stu's rows alone), for which 0.37 predicts a fall of 4.0% (1.4%)
in tricks given up; measured 1.8% and 2.4%. A Stu table counts by its rows (about 41), the low line of the three guessed
before round 3. (I first divided by the growth of Stu's tables and reported an exponent of 0.02 to 0.03: the wrong
denominator.)

**Rows a CPU-second** (250 arena records and 150 of each self-play, from the records' own CPU):

| Records | Tables a record | Rows a record | CPU-s a record | Rows a CPU-s |
| --- | --- | --- | --- | --- |
| the arena's (Gen 8 and 9, two auctions, audit and gap forks) | 36.3 (3.1 root, 33.2 forks) | 764 | 85 | 9.0 |
| Gen 8's self-play here (`sg8t`, one table, no forks) | 1 | 41 | 12.5 | 3.3 |
| Stu's self-play (`sp3s`) | 1 | 36 | 17.2 | 2.1 |

The arena's collector (gap forks) is not in this branch's runner. Round 4 used 1.7M of the 17.6M arena rows on hand. On disk a
row is 756 bytes as the sets are written (the pool file is 23 GB, and each net had a merged copy), 51 bytes compressed (the
published blocks); in the trainer's memory 465 bytes. azure1 stood idle from 17:15 to 18:09 (its job list had ended).

**The net's size is the limit at the pool's size** (Max, 17:43: "Do we need a wider net?"). Rollout net v2 (768 wide, 1.74M
parameters, 5 epochs on the pool) scored on 400,646 rows it was trained on and on the held-out deals (`freshB`, 123,142 rows):

| Bot | Log-loss: trained-on, held-out | Exact card | Tricks given up |
| --- | --- | --- | --- |
| 71s-32 | 0.4339, 0.4552 | 0.8267, 0.8194 | 0.0182, 0.0196 |
| 8s-32 | 0.4380, 0.4581 | 0.8289, 0.8216 | 0.0218, 0.0223 |
| 8c-32 | 0.4427, 0.4418 | 0.8291, 0.8270 | 0.0229, 0.0210 |
| 5RZ32 | 0.5575, 0.5682 | 0.7704, 0.7602 | |
| 1 | 1.0015, 1.0048 | 0.4816, 0.4809 | |

It does as badly on the rows it has seen as on rows it has not, so more rows of this kind can close only that small gap. At
3.7M rows the same net was far from it (`exp-strong`, 768 wide: training loss 0.36 against 0.79 held out; 512 against 768 wide
there: tricks given up 0.0312 against 0.0305). What it does not show is that a larger net does better: what is left may be
noise in the labels. **The width test** (`loop-width` on azure5 from 18:37 UTC, its Gen 8 collection paused): v2's recipe at
1,536 wide (four times the parameters) on the pool's rows, scored on the same held-out deals; 47 minutes an epoch.

## BEN at its upstream play sampling (`ben200`, `ben_session.sh`; Max, 23:31 UTC on 13 November)

lorserker/ben's defaults are sample_hands_play 200 and min_sample_hands_play 20; the arena's lanes run 64 and 64.
Eight more servers on azure3's lanes (port 8090) with those two lines and min_sample_hands_play_bad 20 changed, every
other setting as the lane's BEN (64). Deals 0 to 255, card play only:

| | IMPs a board | Wall clock a lane, 32 boards |
| --- | --- | --- |
| BEN (200) against BEN (64), for BEN (200) | +0.07 +- 0.14 | 50 min |
| Gen 8 against BEN (200) | -0.11 +- 0.27; by deal minus Gen 8 against BEN (64), -0.22 +- 0.21 | 28.4 min |
| Gen 8 against BEN (64) | +0.09 +- 0.27 | 27.0 min |

Gen 8's own process time is 12.2 CPU-s a board against BEN (64) and 13.2 against BEN (200) (about 6 a table side), so
of the wall clock BEN (64) takes about 19 s a table side and BEN (200) about 20: BEN's time is mostly fixed a card
(sampling 5,000 boards, its networks), and 200 samples cost about 5% of it. (A first reading at 01:40 UTC that put Gen
8 at 2 s a table side was wrong: it solved the three clocks without Gen 8's measured time.) From round 4's
measurements on, BEN means BEN (200).

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
