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
| 11:30 | "I think this won't do as well against Ben, but we'll see!" | Played 14:58 to 17:44 UTC on the gate's first 256 deals (`jobs-azure3-ben.txt`, `ben.sh`; the arena's idle BEN servers): Gen 8 card play +0.09 +- 0.27 against BEN (64), Stu-as-is -0.02 +- 0.25, pure Stu -0.27 +- 0.28, pure Stu with the rolled-out lead -0.08 +- 0.26. Each Stu is closer to Gen 8 measured against BEN than head to head (README) |

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

At 14:02 UTC: the rolled-out lead minus the net's +0.23 +- 0.20 (333 deals), the searched lead minus the net's
-0.02 +- 0.18 (200), rolled-out minus searched +0.01 +- 0.26 (200). **Since 14:29 UTC the collection is split** (my
call, Max told at 14:32): six workers play pure Stu with the net's lead (`sp0`) and two with the lead rolled out
(`spr0`), about 890 tables an hour with some 130 rolled-out leads among them. As training data a rolled-out lead costs
as much CPU as a table's forty other decisions together (55 CPU-s a table against 28), and the first run of round 2's
training puts the net's first-choice lead 0.058 tricks behind the rollouts' best on 148 held-out leads (a random lead
0.185; part of the 0.058 is the best of ten noisy means). At the table that would be about 0.15 IMPs a board, so the
bot keeps its rolled-lead rung; the collection needs the volume for the other decisions.

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

- **Result (14:02 UTC, 200 deals each, by deal against the same rung with v2):** inside Stu's own stages
  +0.13 +- 0.17, inside pure Stu +0.22 +- 0.26, alone +0.01 +- 0.23. Within noise, as expected of two vectors.

## Round 2

- **Net.** Round 1's net with one more bot, `stup0` (pure Stu, both its lead variants), whose vectors start from
  `stu0`'s; every weight trained at a low rate on pure Stu's rows with as many replay rows of the bots the net knows
  (`round2.sh`). Its rows carry the rollouts' value for each candidate at every trick, and for all 13 cards at a
  rolled-out lead.
- **A first run at 14:09 UTC** (`train-r2a/`, 647 tables, 148 held out, 6 minutes, selected epoch 1) to prove the
  chain. Log-loss on pure Stu's cards 1.031 to 0.984. Tricks the net's first card gives up against the rollouts'
  values: lead 0.058 to 0.053, tricks 1 to 4 0.061 to 0.061, tricks 5 to 8 0.077 to 0.073, tricks 9 to 13 0.040 to
  0.039 (a random rated card gives up 0.13 to 0.19). `8s-32` log-loss 0.4581 to 0.4641. These "given up" numbers are
  against the best of a few noisy means, so they overstate what a perfect net would gain.
- **Round 2's net, 15:48 to 16:02 UTC** (`train-r2/` on azure5's branch, sha256 `fa5df4e1a7f8...`; 1,814 tables, 150
  held out, selected epoch 1). Log-loss on pure Stu's cards 1.057 to 0.992. Tricks its first card gives up against the
  rollouts' values: lead 0.072 to 0.067, tricks 1 to 4 0.062 to 0.063, tricks 5 to 8 0.087 to 0.088, tricks 9 to 13
  0.060 to 0.058. `8s-32` log-loss 0.4581 to 0.4685. **The choices did not move**: the net predicts Stu's cards better
  and chooses no better, and forgets a little of Gen 8. Three reasons this is not yet a verdict on the method: v2 was
  trained on about 150,000 tables and this is 1,814; the epoch is chosen by the loss over every bot's rows, which
  picks the least-trained epoch; and "given up" is against the best of a few noisy means, which a perfect net could
  not bring to zero.
- **Its bots** (`make_bots.py`): `stu2-p` (the net in the rollouts), `stu2-pt` (also at the table: its lead and first
  choices), `stu2-pv` (the simulated seats play by its value head, `seat: blend`), `stu2-n` (the net alone), with
  controls `stu0-pt`, `stu0-pv`, `stu0-n`. Rungs on the gate's deals 500 to 699 against `l0b-p` (`jobs-azure5-r2.txt`,
  `jobs-azure6-r0c.txt`, `jobs-azure6-r2.txt`), and the two nets alone on 500 deals: the plainest read of whether the
  net learned to choose.
- **At the table (17:55 UTC):** by deal against pure Stu with v2 on 200 deals: the net in the rollouts -0.11 +- 0.32, in
  the rollouts and at the table -0.15 +- 0.34, its value head steering the seats -0.01 +- 0.28 (controls with v2: at
  the table -0.20 +- 0.32, value head -0.04 +- 0.35). The net alone on 500 deals: +0.20 +- 0.17 over v2 alone. A
  longer-trained variant (`train-r2s/`: epoch 5 of 6 under the trainer's new `--select stup0 --forget 0.02`; held-out
  first-card regret at the lead 0.058, tricks 5 to 8 0.083, tricks 9 to 13 0.055) alone: +0.18 +- 0.21 over v2 at 358
  deals. So more epochs on the same tables do not show at the table either.
- **What follows from it:** the loop needs tables before anything else. From about 17:45 UTC three boxes collect
  (azure5, azure6 borrowed, azure3 after the matches against BEN): about 2,300 tables an hour, some 30,000 by 07:00
  UTC on 14 November. Round 3 trains on those, with the epoch chosen on pure Stu's held-out choices and the other
  bots' loss as a limit.

## Round 3

- **The interim net, r3a (21:16 to 22:06 UTC, `train-r3a/`, sha256 `a9c1d1474ff7...`):** 17,350 pure-Stu tables (all of
  azure5's, every block and cut file of the other four boxes), 150 held out, 4 epochs, epoch 4 selected. Indicator 1
  against the start (paired, SE by deal): lead -0.0002 +- 0.0021, tricks 1 to 4 -0.0067 +- 0.0021, 5 to 8 -0.0027 +-
  0.0023, 9 to 13 -0.0017 +- 0.0042, all -0.0039 +- 0.0016; against round 2's net, all -0.0022 +- 0.0015. The value head
  moved more (lead 0.058 to 0.044, tricks 1 to 4 0.065 to 0.058). Gen 8's log-loss 0.458 to 0.476. Pure Stu's log-loss
  1.065 to 0.936, against 1.057 to 0.992 at round 2: 0.020 a doubling of tables, as the morning's learning curve said.
  The 150 held-out tables also chose the epoch, so these are validation numbers (slightly optimistic); from round 3 on,
  indicator 1 is read on a test set that makes no choice (`round2.sh` TEST). Alone on gate deals 500 to 999: minus v2
  alone +0.14 +- 0.20, minus round 2's net -0.06 +- 0.19 (the -0.002 tricks a decision over round 2 is about 0.06 tricks
  a board: far below what 500 deals resolve).
- **The cut, 23:00 UTC.** Round 3 trains on every table to then (`round2.sh r3`, TEST 300), on azure5 with its
  collection paused. From the cut the collection is pure rollout (Max, 22:19 UTC: "My instinct is to just go pure
  rollout"): all eight workers of every box play `stu0-ps`, whose lead is rolled out on the settings of every other
  card (at most 4 candidates by prior, 32 then up to 128 layouts with the race), so every table has a rated lead and
  the lead improves as the net does. 17.2 CPU-s a table on 8 test tables, against 18.8 for the net's lead and about 26
  for the 512-layout lead. The 512-layout lead stays a play-time setting (`stu0-pr`), to be measured against BEN and Gen
  8 apart from training (Max, 22:29 UTC).
- **Experiments on azure6 (Max, 22:26 and 22:31 UTC; `exp_labels.sh`):** label quality against volume (labels and the
  card learned as a bot with only 8, 16 or 32 layouts would have had them, from the per-layout records), tables against
  positions (every decision of half the tables against half the decisions of all of them), and the learning curve on
  the same tables, all scored on the test split of every published block. Then, for play, the rollout budget swept on
  replayed decisions (tricks given up against CPU), confirmed by a match.

- **Round 3's net (23:29 UTC, `train-r3/`, sha256 `a8cf8a94ebcf...`), about 28,000 tables.** Indicator 1 on the test
  set (300 tables that make no choice), start to round 3: tricks 1 to 4 -0.0057 +- 0.0014, 5 to 8 -0.0023 +- 0.0021, 9
  to 13 +0.0019 +- 0.0030, all -0.0025 +- 0.0012; round 2's net to round 3's, all -0.0013 +- 0.0011. Indicator 2, alone
  against Gen 8 on deals 0 to 999: minus v2 alone +0.18 +- 0.14 (1,000), minus round 2's net -0.14 +- 0.18 (500).
  Indicator 3, pure Stu with round 3's net minus with v2, deals 500 to 999: -0.09 +- 0.19 (500). Indicator 4, the same
  against BEN (64): +0.21 +- 0.22 (255). Guard rail: Gen 8's log-loss 0.458 to 0.473.
- **Reading it:** by the letter of the rules below, "1 falls and 2 does not". But the rules did not reckon with power:
  0.0013 tricks a decision over round 2 is about 0.07 tricks a board, some 0.1 IMPs, against +-0.14 to 0.19. So the
  nets alone now meet each other head to head on 4,000 new gate-seed deals (`jobs-azure5-h3.txt`: round 3 against v2,
  round 3 against round 2), about +-0.05. Flat there, and the rule applies: the next lever is the rollouts' values.

- **The powered tests (00:20 to 02:40 UTC on 14 November), head to head on new gate-seed deals:** SiD (net) Stu R3
  against SiD (net) Stu R0 +0.40 +- 0.07 and against SiD (net) Stu R2 +0.19 +- 0.06 (4,000 deals each); against SiD
  (net) v4.1, the table net of every SiD (rollout) bot, +1.36 +- 0.07. But SiD (rollout) Stu R3 against SiD (rollout)
  Stu R0: -0.13 +- 0.09 (2,000 boards). Indicator 2 rises; indicator 3 does not.
- **Max's reading (02:21 UTC):** the loop's tables taught the net Stu's habits, a weaker player than the search bots v2
  learned from, so the simulated seats imagine weaker play. The sandbox control fits it: a net that imitates the search
  bots better lifts the rollout bot (v4.1 against v4, +1.18 alone: +0.29 +- 0.15 inside, +0.79 +- 0.27 as the whole
  bot). **His plan (02:31 UTC):** generate the best data the strongest bots can make, add its volume to Stu's net, and
  ramp Stu's own rollout data in (or build a lot of it and restart) once a net that imitates the rollouts beats one
  that imitates the other bots inside the rollouts.
- **Running on it:** `exp_strong.sh` (a net from Gen 8 card play's rows of v2's set only, 3.67 million, against one from
  as many rows in v2's mix, each from scratch at 512 and 768 wide; then head to head alone and inside the rollouts), and
  the table net (`stu3-pst`, round 3's net inside and at the table, against SiD (rollout) Stu R0 on 2,000 boards).
  Gen 8's data costs about 6 CPU-s a table side (fp32) against SiD (rollout)'s 9 (bf16) to 12 (fp32), so its self-play
  makes about 1.5 to 2 times the tables a box-hour; the arena's feeds already hold about 25,000 Gen 8 and 9 episodes
  newer than v2's set. From 02:50 UTC azure1 makes Gen 8's self-play records (`sg8e`, `g8a~g8b`).

## Max's decisions, 14 November (UTC), from 02:30

| When | His words | What follows |
| --- | --- | --- |
| 02:43 | "we should only be doing enough self play to see where we are" | Gen 8's self-play as data; Stu's own only as much as tells where we are |
| 03:35 to 03:50 | personalities, "mostly directed... a bit of random", "Average in a mixed pop. Half an imp... was too much" | `style.py`; doses set for about a quarter IMP a board across the population |
| 04:02 to 04:10 | partners' knowledge and disclosure random (knowledge 0 to 80%, disclosure usually 75% of it, 0 to 150%), per dimension, correlated (centred 0.6, -0.2 to 0.8) | the population's dials (not built yet) |
| 04:10 | "Simpler to have one not two" | one net at the table and in the rollouts (`stu3-pst`) |
| 04:17 | "test with 4.1 everywhere vs Ben, but let's settle the other issues first" | `b41-ps200` last in azure3's BEN queue |
| 04:23 | "the gate should be on Ben" | the verdict on a bot is its by-deal difference on BEN (200) |
| 04:28 | "don't go down in a cold game or slam" | the IMP objective (`stu3-psti`, `h3-pi`); the guarantee already covers certain contracts |
| 04:30 | BEN's share of training "low" | BEN tables out of the arena feeds; out of the replay from round 4 |
| 04:34 | Pavlicek's trump strip squeezes, "do not train the net on them" | `tests/test_squeeze_endings.py` |
| 05:24 to 05:32 | two boxes of each self-play, one for tests; go longer before the release; one box measuring BEN through it; borrow 3 hours for styles | box roles above; round 4 at about 6 hours |
| 05:31 | arena boards from Gen 9 | the feeds go into round 4 without BEN |
| 05:37 | noise in the data now | Gen 8's personalities at margin 0 in its self-play |
| 06:22 | "We should only grade the bot on 'blind' opponents"; BEN's share "about the same" | the gate is blind (`stu3-put`); BEN at round 3's share |
| 09:25 to 09:45 | train a net on the USBC's adult boards against one on as many bot boards; "you can take a machine"; "this is the big question" | `exp_human.sh` on azure5: the human tables help at every dose (README) |
| 09:39 | "If we aren't sure we can do a R4a and an R4b" | round 4 in two nets: `stu4` with every human table, `stu4c` without |
| 09:37 | the USBC analysis waits until this and round 4 are driven | the claims-played-out rescoring is paused at 99 of 270 sessions |
| 15:39 | "If there is not a clear gain from the human boards that makes it through, I would rather not use them" | `stu4c` is round 4's net unless `stu4` leads it by more than two SEs inside the bot (`h4c-pst`, or the gate's first 512 deals each); then the gate's time goes to `stu4c` alone |

## What should move, and what would say we are off path (Max asked, 18:41 UTC on 13 November)

Earliest to latest. Log-loss on Stu's own cards falling is not one of them: in round 2 it fell (1.06 to 0.99) while the
choices did not improve.

| | Indicator | After round 2 | Good path |
| --- | --- | --- | --- |
| 1 | Tricks the net's first card gives up against the rollouts' values, on held-out pure-Stu tables, by phase | lead 0.067, tricks 1 to 4 0.063, 5 to 8 0.088, 9 to 13 0.058 (before: 0.072, 0.062, 0.087, 0.060) | falls by more than its standard error, at every phase, not only the lead |
| 2 | The net alone against Gen 8 card play, by deal against v2 alone | +0.20 +- 0.17 (500 deals) | rises round over round; from round 3 on 1,000 deals (about +- 0.12) |
| 3 | Pure Stu with the round's net inside, by deal against pure Stu with v2 | -0.11 +- 0.32 (200 deals) | turns positive; moves last, because rollouts dilute a better net (the control: +0.29 +- 0.15 for a better net inside) |
| 4 | Pure Stu against BEN (64) | -0.27 +- 0.28 (256 deals) | rises: the check that the gain is not only learning Gen 8 |
| guard | The other bots' held-out log-loss (the rollouts play the opponents with the same net) | Gen 8's 0.458 to 0.469 | stays within +0.02 of the start |

Off path, read at round 3 (about 30,000 tables, 16 times round 2's):
- 1 does not fall and 2 does not rise beyond its noise: the rollouts' values are not teaching the net at this volume.
  Before collecting more, change what it learns from (more layouts a decision so the values are less noisy, the IMP
  objective, or the line finder's labels).
- 1 falls and 2 does not: the net learns to match the rollouts' values and that does not carry to the table, so the
  values themselves are the problem (noise, or the opponent model inside them).
- 2 rises and 3 does not: the rollouts are not passing the net's gain through; the levers are the net at the table
  and its value head in the simulated seats (both measured in round 2, both nothing yet).
- The guard rail breaks: more replay rows of the other bots in training, or train only the parts of the net Stu uses.

The starting hole: head to head, pure Stu is -0.65 +- 0.14 against Gen 8 card play (1,000 deals); against BEN (64)
it is -0.36 +- 0.31 behind Gen 8's result.

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
- The collection's split since 14:29 UTC: six workers on volume with the net's lead, two on rolled-out leads (a table
  with a rolled-out lead measured 55 CPU-s, not the 46.5 first estimated, against 28). Yours to change either way.
- azure3 collects after the matches against BEN and the ladder's leftover rungs are shelved (`jobs-azure3-later.txt`):
  my call at 16:10 UTC on round 2's result. Yours to reverse.
- Stu in partscores gives up a guaranteed contract about as often as Gen 8 (the ledger). Its rule is off there by your
  instruction to the 8X session (13 November 01:42 UTC: act on claims outside undoubled partscores). A rung with the
  rule on everywhere would say what that costs or gains for pure Stu; it is not queued.
- A yardstick that rewards modelling good play, not Gen 8's habits: the single-dummy count is one; a second outside
  opponent or strong people on the play server would be another.

## Speed of a table (13 November, evening UTC)

CPU seconds per table on the collection (pure Stu, `sp0`; with the pooled lead, `spr0`), all five boxes from 57eb87c:

| Change | sp0 | spr0 |
| --- | --- | --- |
| before | 32.5 | 55.9 |
| forward pass as 2-D products, decoder trunk term once a row (ecb813a) | 23.6 | 36.1 |
| card-play nets in bf16 (3b37f15, `~/work/loop/BF16`) | 20.3 | 28.0 |
| hand-fit scorer shared in a process, bf16 hidden layers (57eb87c) | 18.8 | 26.1 |

bf16 against fp32 on held-out rows: same first card 99.7%, total variation 0.0023, trick head error 0.0232 against 0.0231.
Not adopted:
- int8 (dynamic, one scale a column): 3.0x on one core, but same first card 97.1%, total variation 0.024. It would need
  training that knows about the quantization.
- a uniform proposal in place of scoring every class: median efficiency 7%, tenth percentile 1% (`bench/proposal.py`).
- a layout pool kept through the hand (`bench/pool_survival.py`, 490 decisions of sp0): 49% of the pool is still
  possible at the same player's next decision, so it would save at most 37% of the play-reading rows. Play reading is
  about 14% of a table's CPU, so the saving is at most about 5%, below the 2-3 s a table I had estimated.

Memory: with bf16 on, a collection worker's resident memory grew to 3-4 GB, the boxes ran out and a worker was killed
about six times between 20:15 and 21:30 UTC (the run restarts; the boards in hand are lost). One process alone
(`bench/memory.py`): 1.1 to 1.4 GB over its first 22 boards in bf16, 0.34 to 0.39 GB in fp32. Since 21:30 UTC the
collection's workers are replaced every 30 boards (`gen8_match --recycle`, `~/work/loop/RECYCLE`); play is unchanged.

Where the CPU goes now (py-spy, one pure Stu worker): the net's forward pass about two thirds, the hand-fit scorer 17%,
play reading 14% (both inclusive of their share of the forward pass).

## Where things are

| What | Where |
| --- | --- |
| Source | `research/rollout-loop-20261113` (built on `research/sid-net-s0-20261113`): `training/rollout-loop-20261113/`, `configs/loop-bots.json`, `scripts/gen7_build_dataset.py`, `scripts/train_rollout_net.py`, `tests/test_loop_dataset.py` |
| The first design note | `experiments/sid_loop/SPEC.md` (the line finder as teacher; the sidnet session builds its labels and `S_0`) |
| Rows and logs | `transfer/rollout-loop-azure3-20261113`, `transfer/rollout-loop-azure5-20261113`, `transfer/rollout-loop-sandbox-20261113` |
| Full records | on the boxes, `~/work/loop/runs/<run>/episodes` |
| Every command run on a box | `box/azure3/control`, `box/azure5/control` (`commands/*-loop-*.sh`) |
