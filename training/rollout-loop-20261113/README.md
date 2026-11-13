# Rollout loop, round 0 (13 November 2026)

**Work in progress. Research, not an arena cohort.** Max asked for a self-play loop on the rollout bot and assigned
`azure3` and `azure5` to it (08:23 UTC, 13 November: "Take azure 3 and 5"; 07:46: "Starting this loop matters more
than incremental progress"). Design notes: `experiments/sid_loop/SPEC.md`. This folder holds what round 0 runs.
Source: this branch, built on `research/sid-net-s0-20261113` at `24c8091` (the 8X engine at `1a779a9`, the plan
session's `gen7_net.py`, the sidnet session's label heads and trainer).

## The loop

1. **Play.** The rollout bot plays itself; every decision's record keeps the rollout means of its candidate cards.
2. **Learn.** A net is trained from rollout net v2 on those games added to v2's rows: the card the bot played, and for
   each candidate the tricks its rollouts averaged.
3. **Gate.** The bot with the new net inside is measured against opponents the net was not trained on.
4. Repeat with the new net.

Round 0's player is x8's 8Z with rollout net v2 inside (`z0a-v2`, `z0b-v2` in `configs/loop-bots.json`, written by
`make_bots.py`).

## Files

| File | What |
| --- | --- |
| `make_bots.py` | Writes `configs/loop-bots.json` from `configs/x8-bots.json` |
| `run.sh` | One match or collection as a unit; resumes |
| `chain.sh` | A job file's matches one after another |
| `pub.sh` | Pushes rows, summaries and logs to `transfer/rollout-loop-<box>-20261113` |

On a box everything is under `~/work/loop` (own venv, checkout, `sure_cpp` built from
`research/sure-trick-table-20261112` at `2e6ed6d`, a copy of the Gen 7 capture capsule). Deals are a function of
(seed, index). Seed 131 is the gate's and the control's; collections use seeds of their own (round 0: 9001).

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

## Not yet done

- The trainer's per-card value target (rollout means of the candidates only, so a per-card mask) and the soft card
  target from the bot's own probabilities.
- The dataset builder reading `x8_match.py --episodes` records.
- The control at ten times the deals, and the gate against `8p-32-v41`.
