# Stu: the plan

**Work in progress, research only.** Kept by the loop session (`https://claude.ai/code/session_01N2EvxDPjdoFBFtyygdYP4j`).
This page is what is intended and why. What exists and how to run it: [README.md](README.md). What each run is:
`runs.json`. Who decided what and when, and who holds which box: the board (`box/coordination`, `BOARD.md`, entries
signed `loop`). Last revised 13 November 2026, 11:40 UTC.

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
| 11:10 | "The rollout should supply that? Choosing moves with more known cards." (on who models expert opponents; 11:16: "not more of the layout, just the future") | The simulated seats are the net, and the net is to learn from the rollouts' choices: that is the loop's own answer, and its value targets are how (below) |
| 11:16 | "v8 is trained to have strategy fusion errors. As we extinguish those, it may not be all up and to the right" | IMPs against Gen 8 are not the only yardstick: a count against the exact single-dummy solver is added (below) |
| 11:25 | "Should we just do pure Stu (with single dummy guarantee)?" | Pure Stu becomes the main line and plays the collection, from the 1,000-deal comparison at about 12:35 UTC unless it is more than about half an IMP behind Stu-as-is |
| 11:27 | "I don't mind a different lead I think. Leading is different than every other trick at bridge - you don't see the dummy." | The lead may differ from Gen 8's: the net's own card (`stu0-p`), the search's (`stu0-pl`), or rollouts' (next row), whichever measures better on the same deals |
| 11:29 | "Or we could try rollouts for the lead but with more layouts and more choices - try everything for 512 because you don't know, and let the rollouts teach you?" "Same methodology but different parameters." | Built (`0a87e01`): the engine's `lead` block. `stu0-pr` is pure Stu with every distinct lead rolled out on 512 layouts of the three hidden hands; its records give every lead a value to learn from |
| 11:30 | "I think this won't do as well against Ben, but we'll see!" | BEN (64) as a second outside opponent: asked of the arena session on the board (12:05) |

## Stu from here: pure

**Pure Stu** is the bot `stu0-p`: the net's own opening lead; from the second card of trick 1 every card by rollouts
alone, each seat played from its own view; no double-dummy search at any trick; the exact single-dummy claims as
before (a card that wins every remaining trick, in any contract; a declarer's guaranteed contract kept in games, slams
and doubled contracts; defenders avoiding handing one over). "Stu-as-is" (`stu0a`: search at the lead and tricks 1 to
2, the search blended with rollouts at tricks 3 to 6, rollouts alone from trick 7) stays as a rung.

Why now: on the ladder's first 200 deals it is +0.10 +- 0.37 against Stu-as-is deal by deal (both near -0.55 against
Gen 8 card play); every card after the lead is rollout-made, so a change in the net reaches every trick and every
board gives about twice the rollout decisions to learn from (35 a side against 16); and its games hold no card chosen
by the search, so the net is no longer trained on new strategy-fusion play. The comparison at 1,000 deals lands at
about 12:35 UTC; pure Stu's games (`sp0`, `sp0b`) start then.

**The comparison at 1,000 deals (12:42 UTC):** Stu-as-is -0.42 +- 0.10 IMPs a board against Gen 8 card play, pure Stu
-0.65 +- 0.14, by deal -0.22 +- 0.17. That is inside the bar (not more than about half an IMP behind), so pure Stu
plays the collection. The halves disagree: +0.08 +- 0.26 on deals 0 to 499 (azure3), -0.53 +- 0.23 on deals 500 to 999
(azure5). 64 of azure3's boards replayed on azure5 came out the same on all 64 (same decision counts on 63), so the
boxes play alike and the halves differ by their deals.

**The opening lead, three ways** (same bot otherwise, same deals; runs `l0-p`, `l0-pl`, `l0-pr`):

| Lead | Bot | How |
| --- | --- | --- |
| The net's | `stu0-p` | policy v4.1's likeliest card; nothing is sampled |
| Searched | `stu0-pl` | Gen 8's lead: layouts from the lead belief net, each solved double dummy |
| Rolled out | `stu0-pr` | every distinct lead (touching cards are one; 9 to 12 a hand) on 512 layouts of the three hidden hands, drawn as the search draws them; all four seats then play each layout out from their own views, dummy as that layout has it; none is dropped on the way |

A rolled-out lead costs 27 to 29 CPU-s (about 200,000 net rows), so against Gen 8 a board goes from 48 to about 77
CPU-s. On 24 leads the rollouts' choice was not the net's first choice in 14. The record keeps all 512 layouts with
every lead's result in each, and the dataset builder gives all 13 cards a value. If Stu rolls out every lead, what the
net learns from those values does not change Stu's lead (every lead is tried whatever the net says); it changes the
net's own lead and would let a later Stu try fewer leads.

At 200 deals (12:42 UTC) the rolled-out lead is level with the net's against Gen 8: -0.01 +- 0.22 by deal. It is a
different card in 63% of hands; the board's result differs on 59 of 200, 31 better and 28 worse. **The collection
rolls out its leads from 12:43 UTC** (`spr0`; my call, Max told at 12:45): a net that leads its own first choice
teaches itself nothing about leads, and only these records give a lead a value. The price is volume (below).

**One table a board in the collection.** Until 12:00 UTC the collection played two ids of one bot at two tables, as a
match does. Both tables get the same random seed by ply and seat, so the same bot played the same cards at both: 113
of 119 boards of `s0` and 111 of 119 of `r0` were identical card for card. Half that CPU bought nothing, and round 1's
set (759 boards) held about half the distinct tables its 62,504 rows suggest; the learning curve was by board and
stands. `scripts/gen8_match.py --one-room` plays one table a board: 28.6 CPU-s a distinct table for pure Stu against
52.4, about 1,000 tables an hour a box (46.5 CPU-s and about 620 an hour with rolled leads).

**Two yardsticks, because of fusion.** Against Gen 8, removing fusion from Stu does two things at once: Stu's own
cards improve where fusion cost tricks, and Stu's simulated opponents stop making Gen 8's fusion mistakes and so
predict Gen 8 less well. The gate nets the two and need not rise. Two of the usual scores are biased the same way: the
nets' "tricks given up" is the double-dummy search's value on every search bot's rows, and v2 and v4.1 learned their
cards from search bots. So beside IMPs against Gen 8: in the last seven tricks, for every bot in the ladder's records
(Gen 8 included), how often its card gives up a contract the exact single-dummy solver says it had guaranteed, and how
often a defender's card hands declarer one (`fusion_ledger.py`; README, "The fusion ledger", has the first numbers: Gen
8 gives up a guaranteed contract about once in 13 hands it declares, Stu never where its rule applies and at about
Gen 8's rate in partscores, where it has no such rule). The count includes playing for an overtrick at the contract's
risk, which a bot that maximizes mean tricks does on purpose, so it is not fusion alone; a sharper yardstick needs the
single-dummy value of each card, which the sidnet session's labels carry.

## A round

1. **Play.** Stu against itself on training deals, full records, one table a board (`sp<round>...` runs with
   `--one-room`). It does not stop between rounds: the rollout values need volume (below).
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
- **What a round-1 net keeps and forgets** (azure5, 10:57 UTC; `~/work/loop/r1`). 759 of Stu's boards (62,504
  decisions) with as many rows again of the other bots, scored on 250 later boards of Stu's and on the plan session's
  held-out boards of the other bots (`freshB.npz`):

  | Net | Stu's card: log-loss, exact | `8s-32`'s card: log-loss, exact |
  | --- | --- | --- |
  | v2, Stu's vectors set to `8s-32`'s, nothing trained | 1.230, 64.3% | 0.458, 82.2% |
  | The whole net, rate 3e-4 (epoch 1) | 0.886, 63.7% | 0.484, 81.1% |
  | The whole net, rate 1e-4 (epoch 4) | 0.889, 64.0% | 0.478, 81.3% |
  | The whole net, rate 5e-5 (epoch 4) | 0.900, 64.2% | 0.477, 81.5% |
  | Only Stu's two vectors, rate 3e-3 (epoch 6) | 0.962, 63.3% | 0.458, 82.2% |
  | **Only Stu's two vectors, rate 1e-2 (epoch 6): round 1's net** | 0.955, 63.3% | 0.458, 82.2% |

  Training the whole net costs the other bots about a point of exact card at any rate tried, and they are the
  opponents at the gate. Part of that loss is an artefact: some of `freshB.npz` was in v2's own training set (v2 scored
  0.463 on `8s-32` on its true held-out boards), so the loss that is real is nearer 0.015 to 0.02 of log-loss. The two
  vectors alone get four fifths of what the whole net learns of Stu and cannot change anything else.
- **The ladder's first pass** (azure3, rows as of 10:42 UTC; against `8p-32-v41`, seed 131): Stu -0.65 +- 0.18 (200
  deals); the same stages with v1 inside -0.40 +- 0.20 (200); **the pure bot (no double dummy anywhere) -0.55 +- 0.30
  (200), which is +0.10 +- 0.37 against Stu deal by deal.** With v1 inside the pure bot stands at -0.88 +- 0.41 after
  98 deals. Later figures: `runs.json` and the boxes' transfer branches, or the dashboard.

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

- **Cut.** Not at 6,000 boards as first planned: by the learning curve, waiting buys about 0.02 of log-loss a
  doubling. Round 1's set was cut at 10:29 UTC with the 1,009 boards azure5 had (759 trained on, 250 held out).
- **Net.** Rollout net v2 with one bot added, `stu0`, whose two vectors start from `8s-32`'s and are the only weights
  trained (`scripts/train_rollout_net.py --only-vectors stu0`; table above). `train-r1/` on azure5's transfer branch,
  sha256 `a9ee66def78c...`. The chain that built the rows and the first variant: `round1.sh`.
- **Bots.** `stu1a`, `stu1b` and their ladder (`make_bots.py`): round 0's bots with that net inside, told its own side
  is `stu0` and Gen 8 card play is `8s-32`. Since every weight but Stu's vectors is v2's, round 1 differs from round 0
  in one thing: what the rollouts' seats on Stu's own side do.
- **Measure.** `l1-stu1`, `l1-p`, `l1-n`: Stu, the pure bot and the net alone with round 1's net, against Gen 8 card
  play on the deals of round 0's rungs, compared deal by deal. New against old beside them, later.
- **Then.** The collection is pure Stu's from about 12:35 UTC (above). Whether its rollouts use round 1's net or
  round 0's follows from `l1-p` against `l0-p`. Stu-as-is has 1,448 boards on the two boxes (`r0`, `s0`, `s0b`); its
  collection is not resumed.

## After round 1, in the order I expect to matter

1. **Put the rollout values to use in play.** First in the simulated seats: the engine can already let a seat's card
   depend on the net's gap head (`seat: blend`), and for a seat told it is Stu that head would carry Stu's rollout
   values. Measured as a rung. Later as the value at the end of a shortened rollout, which needs engine work.
2. **The boundary** is at the first card after the lead (pure Stu, above). What is left of it is the lead: the net's
   own, the search's or rollouts' (`l0-p`, `l0-pl`, `l0-pr`), and then whether the collection rolls its leads out.
3. **A net that knows pure Stu:** its own name in the net (as `stu0` is Stu-as-is's), trained on its games, the two
   vectors first; then the rollout values at every trick, which only its games have.
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

- Pure Stu passed the bar I set (not more than about half an IMP behind Stu-as-is at 1,000 deals: it is -0.22 +- 0.17).
  If a fifth of an IMP against Gen 8 matters more to you than a bot with no double dummy in it, say so.
- The opponent mix in the collection and when BEN joins the gate.
- The collection rolls out its leads since 12:43 UTC (level with the net's lead at 200 deals): 46.5 CPU-s a table
  against 28.6, so about 620 tables an hour a box against about 1,000, for a value on every lead of every board. Yours
  to reverse if you would rather have the volume.
- Stu in partscores gives up a guaranteed contract about as often as Gen 8 (the ledger): its rule is off there, on
  x8's finding that it lost IMPs in partscores. Worth a rung with the rule on everywhere once the lead rungs are in.
- A yardstick that rewards modelling good play, not Gen 8's habits: the single-dummy count is one; a second outside
  opponent or strong people on the play server would be another.

## Where things are

| What | Where |
| --- | --- |
| Source | `research/rollout-loop-20261113` (built on `research/sid-net-s0-20261113`): `training/rollout-loop-20261113/`, `configs/loop-bots.json`, `scripts/gen7_build_dataset.py`, `scripts/train_rollout_net.py`, `tests/test_loop_dataset.py` |
| The first design note | `experiments/sid_loop/SPEC.md` (the line finder as teacher; the sidnet session builds its labels and `S_0`) |
| Rows and logs | `transfer/rollout-loop-azure3-20261113`, `transfer/rollout-loop-azure5-20261113`, `transfer/rollout-loop-sandbox-20261113` |
| Full records | on the boxes, `~/work/loop/runs/<run>/episodes` |
| Every command run on a box | `box/azure3/control`, `box/azure5/control` (`commands/*-loop-*.sh`) |
