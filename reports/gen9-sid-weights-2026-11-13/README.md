# E9-24: conditional claims' floors with the scorer's weights and with Gen 9's (g9, 13 November 2026)

Gen 9 experiment E9-24 (`team/gen9:experiments/E9-24.md`), for [the SiD plan](../../docs/gen9/sid-integration.md),
section 2.1. Offline, on recorded play. No bot played with any of this.

## Question

A conditional claim's floor is the weight of the cells one line wins against every defence. The cells study
(`experiments/sure_tricks/cells/README.md` on `research/conditional-claims-20261113`, `baa062c`) weighted layouts with
the arena's hand-fit scorer, which reads every auction as a house auction. When the defenders bid another system, are
the floors worse, and do Gen 9's weights repair them?

## Data and method

- **Positions.** Native tables (each side bid with its own bidder) of the eight registered Gen 8 feeds that seat
  `8c-32` (Gen 8's card play with the Precision rule bidder), the first five board shards of each (cached by E9-20's
  collection, 07:14 UTC). The first declarer-side decision with 8 cards, and with 7, contract not yet settled
  (`arena_positions.positions` of the cells study, unchanged). Two populations from the same boards:
  - **Precision defends**: both defenders are `8c-32`, so the defenders' calls are Precision's. 1,240 positions at 8
    cards, 1,217 at 7.
  - **House defends** (control): the defenders are house bots. 1,137 at 8 cards, 1,110 at 7.
- **Weightings.** `b`: the hand-fit scorer for both hidden seats (`cells/belief.py`, scorer SHA-256 `56e6444079d1…`,
  the feeds' own). `g`: Gen 9's reading. A seat played by `8c-32` is read by replaying `8c-32`'s own rule bidder on each
  layout's hand type: P(call) = 0.98 if the bidder makes it, plus 0.02 over the legal calls, as `RuleReplay` on
  `feature/gen9`. The bidder is rebuilt from the Gen 8 launch source (`792c4cb`) with the settings in the feed's
  manifest, and its identity matches the arena's (`f50e95de…`). A house seat is read by the scorer, as Gen 9 reads a
  house bot, so on the control `g` equals `b` by construction.
- **Solver.** `cells.cpp` at `baa062c`, `--def ends`, shape level (no named cards), the study's joint step; a second run
  with two named cards on every other Precision-defended 8-card position (the study's `h2`, each weighting choosing its
  own two runs).
- **Scored.** Positions with no outright claim. Whether the actual layout's cell is inside the certified set of the
  best card (by floor), against the floor claimed.

Scripts: `e924_positions.py`, `e924_study.py`, `e924_report.py`. Results: `*.jsonl.gz` (one line a position),
`report_full.txt`. Sandbox, 2 cores, about 25 minutes in all.

## Results

**The scorer misreads the Precision auctions.** It gives the actual layout less than 1% of a uniform weight in 108 of
667 positions at 8 cards (16%) and 86 of 563 at 7 (15%), and in none of the control. Gen 9's weights do so in none.

**Overall calibration moves little.** Floor minus realised, floors of 0.25 or more (one SE):

| | Scorer, house defends | Scorer, Precision defends | Gen 9, Precision defends |
| --- | --- | --- | --- |
| 8 cards, shape level | +0.060 +- 0.025 (260) | +0.099 +- 0.024 (297) | +0.083 +- 0.023 (289) |
| 7 cards, shape level | +0.049 +- 0.029 (199) | +0.107 +- 0.029 (224) | +0.089 +- 0.027 (223) |
| 8 cards, two named cards | | +0.089 +- 0.030 (196) | +0.096 +- 0.029 (192) |

**At a threshold of 0.9 the weights decide which lines are taken.** A bot that commits to a conditional line when its
floor is 0.9 or more (the plan's starting rule), 7 and 8 cards, shape level:

| | Lines committed | Line covered the actual layout |
| --- | --- | --- |
| Scorer, house defends (control) | 180 | 0.950 +- 0.016 |
| Scorer, Precision defends | 231 | 0.913 +- 0.019 |
| Gen 9, Precision defends | 228 | 0.965 +- 0.012 |

Where both weightings commit (206 positions), they cover the same 200. The difference is all in the positions where
they disagree:
- 25 positions where only the scorer reaches 0.9 (Gen 9's floor there averages 0.649): the scorer's line covered the
  actual layout in 11 (44%). In 12 of the 25 the scorer had given the actual layout under 1% of a uniform weight.
- 22 positions where only Gen 9 reaches 0.9 (the scorer's floor there averages 0.777): Gen 9's line covered 20 (91%).

With two named cards, the same direction: committed lines covered the actual layout 0.889 +- 0.037 (72) with the
scorer, 0.932 +- 0.029 (74) with Gen 9.

**The chosen line, all positions.** The true layout inside the best card's set, Gen 9 minus scorer, paired: 8 cards
-0.004 +- 0.005 (453; best card differs in 37), 7 cards +0.009 +- 0.007 (341; differs in 24), two named cards
-0.022 +- 0.013 (272; the line differs in 88).

## Predictions as registered

1. The scorer overstates more against Precision than on house tables: in the predicted direction at both card counts
   (+0.099 against +0.060; +0.107 against +0.049), each difference under 1.5 SE. Not shown.
2. Gen 9's weights halve the overstatement against Precision: about a sixth less (+0.083, +0.089). Not met.
3. On house tables the two give the same table: by construction (Gen 9 reads a house bot with the scorer). Met.

## What it means for the plan

- Gen 9's weights do not make conditional claims better calibrated across the board. Shape-level cells pool the
  honours, and most of what the scorer misreads in a Precision auction is strength.
- They do matter where the plan's rule acts. With the scorer's weights, a floor of 0.9 against Precision defenders
  failed 8.7% of the time, against 5.0% on house tables, because the scorer certified 25 lines that covered the actual
  layout less than half the time. With Gen 9's weights it failed 3.5%. So Gen 9's weights keep the 0.9 threshold
  meaning what it says against another system, which is the condition for starting there (plan, section 3).
- 8X's own weights (the scorer plus the net's reading of the play) were not run. They add the play, not the auction's
  system, so they should not repair a misread Precision auction, but that is not measured.

## Limits

- One opponent system (the Precision rule bidder), the defenders' auction only; play reading not in either weighting.
- The first five board shards of each feed; positions are first declarer-side decisions at 8 and 7 cards.
- "Covered" means the line keeps the contract against every defence in the actual layout's cell. Contracts and IMPs
  are not measured; nothing was played.
- The replay reads 8c-32 as exactly its own bidder. For a guest whose bidder Gen 9 does not hold, the reading is the
  card or the scorer, which this does not test.
