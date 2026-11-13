# Stu: the plan

**Work in progress, research only.** Kept by the loop session (`https://claude.ai/code/session_01N2EvxDPjdoFBFtyygdYP4j`).
This page is what is intended and why. What exists and how to run it: [README.md](README.md). What each run is:
`runs.json`. Who decided what and when, and who holds which box: the board (`box/coordination`, `BOARD.md`, entries
signed `loop`). Last revised 13 November 2026, 10:20 UTC.

## The aim

Max: "I want to eventually build a bot that beats human experts." The route he chose on 13 November: a bot whose
cards come from playing positions out from each seat's own view, not from double-dummy search, improved round by round
on its own games, with the trick at which playouts take over from the search pushed earlier over time ("we will push
the rollout boundary over time", 09:24 UTC). He named the bot **Stu** (09:05).

## Max's decisions so far (13 November, UTC)

| When | His words | What follows from it |
| --- | --- | --- |
| 07:46 | "I would like you to have 2 azure boxes immediately... Starting this loop matters more than incremental progress." | Rounds are started before every measurement one could want is in |
| 08:23 | "Take azure 3 and 5" | Both boxes are the loop's |
| 08:56 | "I don't care that much which objective we train to; eventually I will do both." | Rollouts pick by mean tricks for now, as 8Z does |
| 08:59 | "See how much bigger / if it matters." | Records keep every layout's result for every candidate (43 KB a board against 27 KB, same cards), so an IMP target can be built from the same games |
| 09:05 | "I think I want to name this bot Stu." | Bot ids `stu<round>...` |
| 09:24 | "Should we also be calibrating against pure rollout bots, and rollout pushed one trick sooner and/or with higher weight?" | The ladder (README) |
| 09:27 | "We should measure v1 rungs too" | Every rung also with rollout net v1 inside, once |
| 09:30 | "another chat will create a dashboard to monitor the process" | `DASHBOARD.md`, `runs.json` |
| 09:38 | "ETA for initial calibration results?" | The ladder's first pass (200 deals a rung) ran at once on azure3 instead of at the cut |

## A round

1. **Play.** Stu against itself on training deals, full records (`s<round>...` runs). It does not stop between rounds:
   the rollout values need volume (below).
2. **Rows.** `scripts/gen7_build_dataset.py --policy-only --rollout-gap --alias ...` (README).
3. **Net.** Train from the last round's net on Stu's rows together with the rows of the bots the net already knows, so
   that it keeps its model of the others (the opponents at the gate are among them).
4. **Bots.** The round's Stu is the last round's with the new net inside its rollouts; the simulated seats of its own
   side are told they are Stu, the other side what it is (Stu in self-play, `8s-32` against Gen 8 card play).
5. **Measure.** The gate: the round's Stu against `8p-32-v41` on seed 131, the same deals every round, compared with the
   last round deal by deal. The ladder: the round's net inside the five rungs, same opponent, same deals. New Stu
   against old Stu is reported beside them and is not the verdict (a net trained on a bot's games predicts that bot).
6. **Decide.** Whether the next round's games are played by the new Stu, and whether the boundary moves (below).

## What is measured so far

- **The control** (README): rollouts add 1.3 to 2.9 IMPs a board to a net alone; of what the inside net is worth, its
  being the opponent's own net is +1.12 +- 0.16 and its being the better net +0.29 +- 0.15 (v4 against v4.1, which
  differ by +1.18 +- 0.28 alone). Opponents were nets alone.
- **How the nets' play scales with data** (the policy nets' own notes): tricks given up by a net's first card fall as
  training deals to the power -0.37 (v3, v4, v4.1). v2 was trained on 75,390 deals.
- **How fast the net learns Stu** (azure5, 10:00 UTC; `~/work/loop/lc`). Rollout net v2, Stu's vectors started from
  `8s-32`'s, fine-tuned on Stu's rows alone and scored on 200 later boards (16,527 decisions):

  | Stu boards trained on | Log-loss of Stu's card | Exact card | The same from trick 7 | Tricks its own card gives up by Stu's ratings, from trick 7 |
  | --- | --- | --- | --- | --- |
  | 0 (v2 told `8s-32`, as round 0's rollouts use it) | 1.228 | 64.1% | 1.112, 67.1% | 0.073 |
  | 65 | 0.918 | 63.6% | 0.866, 66.5% | |
  | 131 | 0.902 | 63.6% | 0.851, 66.5% | |
  | 262 | 0.885 | 63.5% | 0.838, 66.0% | |
  | 523 | 0.866 | 64.1% | 0.822, 66.7% | 0.069 |

  On the same rows: v2 with no bot named 1.071 and 63.8%; policy v4.1 1.060 and 66.7%; rollout net v1 (ft) 1.411 and
  65.2%. Stu's own randomizing (the declarer plays a random one of its equal cards) puts the floor at 0.232 and the
  ceiling at 85.4% (0.141 and 90.7% from trick 7); the chance in the rollouts' layouts is on top of that and is not
  in those figures. For comparison v2 scores 0.463 and 82.0% on `8s-32`'s own decisions.
  - Almost all of the gain is the declaring side (1.690 to 1.020; defending 0.745 to 0.705), and most of it comes in
    the first 65 boards: the net learns that Stu's declarer randomizes among equal cards. After that each doubling
    brings about 0.02.
  - Which card Stu plays where it departs from the net is not learned at this size: the exact-card share does not
    move. The gap head (trained on the rollouts' gaps from these rows) does not improve either.
  - Limits: Stu's rows alone, so what the net forgets about other bots is not measured here; one held-out set.
- **The ladder and the gate:** `runs.json`; results on the boxes' transfer branches as they arrive.

## What I expect, written before the results

Three things Stu's games can change in the net, and the data each needs:

1. **Playing better by imitating Stu's cards.** By the scaling above, 6,000 more boards on 75,390 is about 3% fewer
   tricks given up, which I convert to about +0.05 IMPs for the net alone and +0.01 inside a rollout bot: not
   measurable. About another 75,000 boards (2.7 days of both boxes) for something near +0.1 at the table. The
   conversion chains three ratios measured in other settings; read it as an order of magnitude. Stu's cards are also
   not better than Gen 8's, which the net has already learned from.
2. **Knowing how Stu plays**, so that simulated seats match real ones. The table above: the part that is quick is
   learned in under a hundred boards; the rest is slow.
3. **The rollout value of each candidate card.** The only information in Stu's games the net has never seen (its
   value targets so far are the double-dummy search's). No measurement to lean on; my rough expectation is tens of
   thousands of boards before it changes play. It is not used in play yet.

**Round 1 at the gate: within about 0.1 IMPs of round 0**, so no visible change. An estimate. Round 1 is worth doing
for the pipeline end to end, and for whether a net that knows Stu's own side helps against Gen 8.

## Round 1

- **Cut.** Not at 6,000 boards as first planned: by the table, waiting buys about 0.02 of log-loss a doubling. Round 1
  is cut as soon as its set and training chain are ready, with every board both boxes have then. The collection goes
  on.
- **Set.** Stu's rows (the two ids and the first runs' ids as one bot, `stu0`) with the rows of v2's own set (on
  azure5 under the plan session's `~/work/plan/rnet2w/data`, read-only; to be confirmed with plan). A quick variant
  first: Stu's rows with an equal number of v2's rows drawn at random, a few epochs at a low rate, scored on held-out
  Stu boards and on v2's own held-out set to see what it forgets. Then the full joined set for an epoch or two
  (about 25 minutes an epoch on 8 cores, by v2's own run).
- **Net.** 768 wide, from v2's epoch 5, `--init-as stu0=8s-32`.
- **Bots.** `stu1a`, `stu1b` and the five rungs with the round-1 net inside (`make_bots.py`, not written yet).
- **Measure.** The gate on the deals of `l0-stu0` and `g0b-stu0`, paired with round 0's; the ladder's five rungs;
  new against old beside them.
- **Then.** Round 2's games are played by round 1's Stu unless it is behind round 0's at the gate by more than two
  standard errors.

## After round 1, in the order I expect to matter

1. **Put the rollout values to use in play.** First in the simulated seats: the engine can already let a seat's card
   depend on the net's gap head (`seat: blend`), and for a seat told it is Stu that head would carry Stu's rollout
   values. Measured as a rung. Later as the value at the end of a shortened rollout, which needs engine work.
2. **Move the boundary** when the ladder says so. Proposed rule, Max's to set: a rung becomes Stu when it is not behind
   the current Stu by more than one standard error on at least 1,000 deals compared deal by deal.
3. **Rollout-made decisions at early tricks** in the training set (`d0-p`, `d0-r3`: the pure bot and rollouts from
   trick 3 against Stu on training deals). Without them the net's early play still comes from the search.
4. **The IMP objective** as a second bot and a second target from the same records (Max: "eventually I will do both").
5. **One net with the line finder's labels:** the sidnet session's `S_0` heads joined to this net, and the
   conditional claims (g9's X9) in Stu's rollouts.
6. **Opponents other than itself** in the collection (earlier rounds, other styles) and a second outside opponent at
   the gate (BEN (64): its servers are up on azure3). The shares are Max's.
7. Smaller things: the bot's own probabilities as a soft card target; the chance of making as a target; more than four
   candidates a decision.

## What would change the plan

- New Stu beats old Stu and does not move against Gen 8, round after round: the loop is chasing its own tail. Then
  the opponent mix (6) comes first.
- The ladder's rungs stay as far behind as in round 0 after the value head is in play: the net is not learning what
  the search knows at early tricks from this data. Then more early-trick rows, a larger net, or the line finder's
  labels come before more of the same games.
- The gate falls: stop feeding the collection with the new Stu and find out why before another round.

## Open, for Max

- The rule for moving the boundary (proposal above).
- The opponent mix in the collection and when BEN joins the gate.
- Whether round 1 should wait for anything I have not thought of. My default is to run it today.

## Where things are

| What | Where |
| --- | --- |
| Source | `research/rollout-loop-20261113` (built on `research/sid-net-s0-20261113`): `training/rollout-loop-20261113/`, `configs/loop-bots.json`, `scripts/gen7_build_dataset.py`, `scripts/train_rollout_net.py`, `tests/test_loop_dataset.py` |
| The first design note | `experiments/sid_loop/SPEC.md` (the line finder as teacher; the sidnet session builds its labels and `S_0`) |
| Rows and logs | `transfer/rollout-loop-azure3-20261113`, `transfer/rollout-loop-azure5-20261113`, `transfer/rollout-loop-sandbox-20261113` |
| Full records | on the boxes, `~/work/loop/runs/<run>/episodes` |
| Every command run on a box | `box/azure3/control`, `box/azure5/control` (`commands/*-loop-*.sh`) |
