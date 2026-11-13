# Stu: the rollout loop, round 0 (13 November 2026)

**Work in progress. Research, not an arena cohort.** Max asked for a self-play loop on the rollout bot and assigned
`azure3` and `azure5` to it (08:23 UTC, 13 November: "Take azure 3 and 5"; 07:46: "Starting this loop matters more
than incremental progress"). He named the loop's bot **Stu** (09:05 UTC). Design notes: `experiments/sid_loop/SPEC.md`.
This folder holds what round 0 runs.
Source: this branch, built on `research/sid-net-s0-20261113` at `24c8091` (the 8X engine at `1a779a9`, the plan
session's `gen7_net.py`, the sidnet session's label heads and trainer).

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
| `make_bots.py` | Writes `configs/loop-bots.json` from `configs/x8-bots.json` |
| `run.sh` | One match or collection as a unit; resumes |
| `chain.sh` | A job file's matches one after another |
| `pub.sh` | Pushes rows, summaries and logs to `transfer/rollout-loop-<box>-20261113` |
| `jobs-azure3.txt`, `jobs-azure5.txt` | What each box runs, in order |

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

- The same five bots are also measured with rollout net v1 (ft) inside (`stu0v1`, `stu0v1-b50`, `stu0v1-r6`,
  `stu0v1-r3`, `stu0v1-p`; Max, 09:27 UTC: "We should measure v1 rungs too"). `stu0v1` is x8's `8z-ft1` with the
  loop's records and lists. v1 does not change from round to round, so its rungs are measured once.
- A rollout bot is not used as the opponent: the net inside Stu models such a bot better than any other, and in the
  control above that match alone was worth +1.12 +- 0.16 IMPs a board.
- **Seed 131 is never trained on**, so the ladder's records are for reading only. Rollout-made decisions at early
  tricks, which Stu itself does not make, come from the same bots on training deals (`d0-p`, `d0-r3` in
  `jobs-azure3.txt`).
- Known before the ladder (x8, older nets, different deal counts): against Gen 8 card play the blend at trust 0.25
  from trick 3 scored -0.07 +- 0.14 (246 boards) and rollouts alone from trick 7 scored -0.38 +- 0.14 (541).

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
