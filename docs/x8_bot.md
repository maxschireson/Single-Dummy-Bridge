# The 8X bot (work in progress; 8X v3 has an arena plan)

Branch `feature/gen8x-rollout-bot-20261113`. Engine `gen8x`, `bridge_harness/x8_player.py`. Session `x8` on the
coordination board. Max, 13 Nov 06:40 UTC: 8X v3 goes into the arena mix (plan `configs/round8x-v3.json` on
`feature/gen8x-arena-20261113`, which adds the Gen 8 launch line; see "In the arena" below). Nothing is merged.

## What it is for

Max's plan of 12 November 2026 (23:40 UTC, the plan-leverage chat):

1. a rollout net trained on all the matches from Gen 7 on (the plan session builds it:
   `training/rollout-net-v1-20261113`);
2. an 8X bot that uses the single-dummy winning-line logic out to ten tricks (declarer does not give away a made
   contract; a defender minimises the odds of handing declarer a claim), rolls out on the rollout net as broadly as
   calibration tests allow, uses PIMC only where it must, and records inside-rollout data;
3. let it play, retrain the rollout net on the results, repeat, always with a varied population.

Later the same night: rollouts need not run to trick 13, nor start at trick 1, where other methods test better;
prune candidates that look bad, without merging transpositions (the order of play is information); play randomly
among equal cards so the bot is hard to read.

This page is the bot of step 2. Until the rollout net exists, policy net v4.1 stands in for it.

## One decision

The trick decides the mode (`x8.stages`; tricks in no stage, and the opening lead, use the search):

| Mode | What decides the card |
| --- | --- |
| `search` | the Gen 8 search as the spec's `gen6` and `gen7` blocks describe it: layouts from the auction (hand-fit scorer) and the play (the net's reading from trick 1), double dummy, the net among level cards; the spec's Gen 7 tree if it has one |
| `blend` | that search, then its near-best cards (within `margin`, at most `cards`) are rolled out and valued at (1 - `trust`) x the search's estimate + `trust` x the rollouts' mean. `layouts` above 0: fresh layouts drawn as the search draws its own; 0: the solved layouts |
| `rollout` | no double dummy. Candidates are the runs of touching cards the net gives at least `prior` of its probability (the two likeliest always), at most `cards`. All are rolled out on the first `first` layouts; the field doubles, and a card behind the leader by more than `race` paired standard errors plus `slack` gets no more rollouts. The value is the weighted mean of the rollouts |

A rollout (`bridge_harness/x8_rollout.py`) is one candidate card in one layout, then every later card of all four
seats from the rollout net, each seat seeing only its own view; all (card, layout) pairs advance in one batch. It
runs to trick 13, or `horizon` tricks and then double dummy. Each seat plays the net's most probable card
(`seat: top`), a card drawn from its probabilities (`draw`, `power`), or the net's card corrected by its gap head
(`blend`). Rows are never merged: two rows that reach the same cards by different orders are different positions,
because the order is part of what each seat has seen and the net reads it.

`objective: imps` makes a rollout stage choose by the swing in IMPs against the card with the best mean tricks,
layout by layout, in place of mean tricks.

## The winning-line logic

`bridge_harness/x8_claims.py`; the solver is `sure_cpp` from `experiments/sure_tricks/sure.cpp` on
`research/sure-trick-table-20261112` (the pooled-defender game: what the declaring side can guarantee against
every split of the cards it cannot see and every defence, given hand sizes and show-outs). Settings `x8.claims`,
active with `cards` or fewer cards in hand:

- **Declarer.** If some card guarantees the contract from the declaring side's own view, only such cards are
  candidates, in every mode.
- **Defender**, with `defender_cards` (8) or fewer cards. For each candidate and each of `defender` (16) layouts the
  defender cannot rule out (`sample`: uniform, as tested; or the likeliest of the decision's own): would declarer, from
  its own view in that layout once the card is played, hold a guaranteed line? The share is the card's hand-over odds.
  In blend and rollout decisions the lowest odds win among candidates within `odds_margin` (0.125) of the best value.
  Elsewhere, with `guard`, the rule the strategy-fusion session tested on the Gen 8 feeds (13 Nov: 674 decisions,
  +0.225 +- 0.097 IMPs a decision; games, slams and doubled contracts +0.535 +- 0.198, undoubled partscores
  -0.035 +- 0.061): among cards the search rates within 0.125 of its own card, the one with the fewest hand-overs,
  its own card when tied.
- **Contract class** (`contracts`): by default the logic acts only in games, slams and doubled contracts, for both
  sides (Max, 13 Nov 01:42 UTC: act on claims outside undoubled partscores).
- **Inside rollouts.** For a side treated as keeping a guaranteed contract (this bot's side when it declares, `own`;
  opponents listed in `opponents`), the claim finder is asked at the start of each trick with `leaf` or fewer cards.
  Where the contract is guaranteed the row's result is floored at the contract and the rollout plays on, so the
  overtricks and undertricks it finds still count; where every trick left is guaranteed the row ends.

The plan session's `prc` bot (`match4`) had the simulated declarer play only the claim finder's card once the
contract was settled, and lost most of its gain (-0.092 +- 0.042 IMPs a board paired against `match1`). Here the
rollout's play is never replaced; only its result is floored.

Each question has a time allowance (`defender_ms`, `leaf_ms`, `each_ms`); a question that outlasts it is
abandoned and the answer is "not known", which never moves a card.

## Being hard to read

`x8.mix`. `declarer` / `defender`: that side plays any of its equal cards alike (equal = the cards the decision
leaves eligible: touching cards and cards rated exactly level). The spec's `exploration: 1.0` does the same for every
seat. `read_declarer` / `read_defender` list the opponents whose side mixes (and partner is read so when `defender`
is on): their cards are read as their run of touching cards, each card of the run equally likely, so which card of
a run was played carries no information and how long the run is still does. Cards rated level but not touching
are not pooled; telling them apart needs the mixer's own search.

A mixing defender misleads a partner that reads it as the net plays, so the v0 bots mix as declarer only. The Gen
9 lead's two azure4 matches (`e9-16-r-v-p`, `e9-16-r-v-x`) measure what mixing costs in play.

`declarer_power` / `defender_power` (Max, 13 Nov 04:33: randomize only where the net has no clear preference, the
randomization tied to the information given away against the value given up): equal card x is played with
probability proportional to p(x) ** power, p the net's probability. That choice maximizes power x E[log p] + H: value
given up, measured in log probability below the net's favourite, against information given away (the choice's
entropy H). Power 0 is the uniform mixing above; a card the net likes half as much as its favourite is played
2 ** -power as often. A mixer is read with the same power for its role. 8X v2 and v3 use 2 (declaring side) and 3
(defenders, whose partner reads the card). `capture.mix_share` forks a share of the decisions the mix alone changed,
chosen by a hash of the position (mixing-only forks roughly doubled the cost when all were forked).

## Forks on every feature that changes a card

With `capture.audit: features` (the default) an audited 8X bot names as reference card the card plain Gen 8 (this
spec's search, the net's tie-break, no 8X feature) would have played, wherever a feature in `audit_features` changed
the card, and names no card anywhere else; `x8_features` in the action says which features changed it (`rollout`,
`blend`, `guarantee`, `odds`, `guard`, `mix`). The collector's audit forks (`fork_audit.collect_board`) then play
plain Gen 8's card out from the same position with the same bots. `scripts/x8_match.py --feature-forks` sets the
audit budget to fork every such decision, one level deep; `scripts/x8_forks.py` pools the forks by feature and
contract class (IMPs to the deciding side of the 8X card over plain Gen 8's, boards as the unit of the errors). So
every 8X match is also a post-mortem of each feature, at the cost of the forked decisions only. `mix` is left out of
`audit_features` by default: most of its changes are between touching cards. In the arena, the same setting means an
8X bot's audits fork only feature changes, not Gen 7's tie audits.

## The record

Every 8X decision writes an `x8` note into the action (`bridge_harness/x8_capture.py`): mode, candidates and their
runs, the net's prior, values, rollout means, layouts each candidate got, the race's rounds, hand-over odds, the
claim verdict, timings. `x8.capture.level`:

- 1 (default): inside-rollout forks. At a random later turn of a few rollouts the net's card and another legal card
  that does a different job (not a touching card) are both played out by the net. Each fork carries its layout, root
  card and line, so the seat's view at the fork can be rebuilt (`x8_capture.fork_view`) and the pair used as a
  training example at a position the real game never reached. `forks` per decision, default 8: about 160 a board.
- 2: also the layouts (as codes over the unseen cards) with their weights and every card's result in each.

## Bots

`configs/x8-bots.json`. Policy v4.1 is both the table net (`gen7_policy`) and the rollout net (`rollout_policy`).

| Bot | What |
| --- | --- |
| `8xr0-v41` | v0, as set by the calibration below: the Gen 8 search at tricks 1 to 2; from trick 3 that search blended with rollouts (sampled seats) on 256 fresh layouts at trust 0.25 for up to 3 candidates within 0.25 of its best; the declarer's guarantee from 10 cards and the defender's hand-over odds and rule from 8, in games, slams and doubled contracts; declarer mixes; inside-rollout forks recorded |
| `8xr0n-v41` | `8xr0-v41` without the winning-line logic |
| `8xr7-v41` | the first v0 layout: blend at tricks 3 to 6, rollouts alone from trick 7 (up to 4 candidates, 128 layouts, race from 32); for testing rollout nets |
| `8xl0-v41` | rollouts alone from trick 3 |
| `8xc0-v41` | `8x-32-v41` with only the declarer's guarantee (from 10 cards, games, slams and doubled contracts) |
| `8xg0-v41` | `8x-32-v41` with only the defender rule as tested on the Gen 8 feeds |
| `8xm0-v41` | `8x-32-v41` with only the declarer's mixing |
| `8xs0-v41` | `8x-32-v41` through this engine with nothing on: plays `8x-32-v41`'s game card for card |

8Z and the 8X versions of 13 November (`configs/x8-bots.json`, rollout net v1 = `ft1`):

| Bot | What |
| --- | --- |
| `8z-ft1`, `8z-v41` | 8Z: rollouts alone from trick 7 (up to 4 candidates, 128 layouts, sampled seats), the blend at 3 to 6, unless it has a claim (`claims.full`: a card that guarantees every trick left is played, any contract); on rollout net v1 / v4.1 |
| `8x1-ft1` | `8xr0-ft1` with the claim and defenders mixing too (uniform) |
| `8x2-ft1` | `8x1-ft1` with mixing tempered by the net (powers 2 and 3) |
| `8x3-ft1` | 8X v3: Gen 8 through trick 6 (its tree at 3 to 6 included); from trick 7 the blend in games, slams and doubled contracts only (`stage.contracts: games`); the claim; mixing as `8x2-ft1`. Every difference from Gen 8 is forked against Gen 8's own card |
| `n-ft1`, `n-v41` | the nets alone, every card (the leverage denominator) |

## Matches against Gen 8, 13 November

azure6, `scripts/x8_match.py --feature-forks`, seed 131 (the same deals in every match), against `8p-32-v41` (the
Gen 8 search with policy v4.1), IMPs a board for the 8X bot (common auctions):

| Match | Boards | IMPs a board |
| --- | ---: | ---: |
| `8xr0-ft1` (original 8X, at `bb85066`) | 246 | -0.07 +- 0.14 |
| `8x1-ft1` (uniform mixing) | 196 | +0.19 +- 0.19 (first 77: +0.60; the next 119: about -0.07) |
| `8x2-ft1` (8X v2) | 550 | -0.15 +- 0.12 |
| `8x3-ft1` (8X v3) | 459 | +0.02 +- 0.13 |
| `8z-ft1` (8Z, v1) | 541 | -0.38 +- 0.14 |
| `8z-v41` (8Z, v4.1) | 453 | -0.51 +- 0.15 |
| `8z-ft1` against Gen 7.1 (`7s-32-v41`) | 345 | -0.26 +- 0.21 |

Paired on common deals: 8Z v1 minus 8Z v4.1 -0.01 +- 0.15 (428), against the nets alone +0.49 +- 0.07 (`n-ft1` over
`n-v41`, 4,000 boards): leverage about -2% +- 30%. 8X v2 minus 8Z +0.22 +- 0.18 (540); uniform minus tempered mixing
+0.26 +- 0.31 (196); v3 minus v2 +0.06 +- 0.13 (459). Forks (IMPs a board, boards as the unit): in 8X v3, the games
blend at tricks 7 to 13 +0.17 +- 0.09, the declarer's guarantee +0.11 +- 0.07, mixing +0.01 +- 0.08; in every match
with rollouts or the blend in partscores those lost (8X v2 -0.16 +- 0.07), hence v3's games-only blend. Fork sums
ran above the match result in every run: after a fork both cards are played on by the 8X bot, whose later play suits
its own line, so forks lean toward its card; the match is the unbiased number. Inside rollouts the contract floor
applies in every contract while the bot keeps a guarantee in games only (not changed yet; v3 runs no rollouts in
partscores).

## Calibration

Scored as the plan session scores look-ahead (`reports/plan-leverage-2026-11-12`, units and method): on gap-fork pairs
of 1,561 fresh Gen 6 self-play boards, a rule plays the forced card B when its estimate of A - B is negative, and is
scored by the ceiling, the real Gen 6 bots playing on from both cards on 16 to 30 of the decider's layouts
(`ceilT712`, `ceilT712b`). Tricks gained over the bot's card, a side at one table; errors take deals as the unit.

Tricks 3 to 6 (plan session, section 2): v4.1 rollouts on 512 layouts gain +0.025 +- 0.015 at trust 0.25 and lose at
trust above 0.5.

Tricks 7 to 12, this session (2,990 pairs, 1,378 deals, about 119 layouts a pair; `scripts/x8_bench.py` and
`scripts/plan_bench.py` with seed 1, `scripts/plan_headroom.py --sims`):

| Rollout net, seats | Rollouts alone | 0.5 search + 0.5 rollouts | 0.75 search + 0.25 rollouts | Share of the correction in real results |
| --- | --- | --- | --- | --- |
| v4.1, top card | -0.274 +- 0.058 | -0.030 +- 0.019 | +0.010 +- 0.011 | 0.106 |
| v4.1, sampled, 4 a layout | -0.159 +- 0.031 | -0.012 +- 0.017 | +0.013 +- 0.007 | 0.146 |
| v4.1, top card, claim floors (`xc`) | -0.189 +- 0.038 | -0.017 +- 0.018 | +0.012 +- 0.011 | 0.126 |

Rollout net v1 (`transfer/rollout-net-v1-20261113`, `runs/ft`: v4.1 fine-tuned on the Gen 7+ bots' play), same pairs:

| Rollout net, seats | Rollouts alone | 0.5 search + 0.5 rollouts | 0.75 search + 0.25 rollouts | Share | Rollouts alone, minus v4.1's, same pairs |
| --- | --- | --- | --- | --- | --- |
| v1 ft, top card | -0.223 +- 0.055 | -0.016 +- 0.018 | +0.009 +- 0.008 | 0.124 | +0.051 +- 0.030 |
| v1 ft, sampled, 4 a layout | -0.126 +- 0.028 | +0.003 +- 0.010 | +0.010 +- 0.007 | 0.176 | +0.034 +- 0.027 |

The better net moves rollouts alone toward zero by 0.03 to 0.05 tricks a side (about 1.5 standard errors), and the
share of its correction that shows in real results from 0.11 to 0.12 and 0.15 to 0.18: the direction the plan needs,
far from enough for rollouts to decide alone.

So with v4.1 as the rollout net, rollouts cannot choose cards on their own late in the hand, and v0 blends at trust
0.25 from trick 3. The claim floors change 37% of the pairs' rollout values and take a third of the loss of rollouts
alone away; they do not change the blend. The same test, on the same pairs, is the gate for a rollout net:
`rollouts alone` moving to zero or above is what would let the bot roll out more.

The ceiling is Gen 6 playing on, while the 8X bot plays among Gen 7 and Gen 8 bots; a net trained on Gen 7+ play is
scored here against Gen 6's play.

## Running

```
python scripts/build_dds.py
g++ -O2 -march=native -std=c++17 -o sure_cpp sure.cpp      # experiments/sure_tricks on research/sure-trick-table-20261112
pip install h5py                                            # the capsule's bidder
SURE_BIN=$PWD/sure_cpp python scripts/x8_match.py --source CAPSULE/recovery --bots configs/x8-bots.json \
    --pair 8xr0-v41~8p-32-v41 --deals 1600 --seed 141 --workers 8 --out DIR [--episodes]
```

`CAPSULE/recovery` is the capture capsule's run folder (manifest and artifacts), as for `scripts/gen8_match.py`.
Rows of `results.jsonl` carry per-role counts of what the 8X decisions did (`search.<role>.x8`).

`scripts/x8_bench.py` is `scripts/plan_bench.py` with the 8X rollouts as simulated seats (`xt`: plain; `xc`: with
the claim floors), for `scripts/plan_headroom.py --sims`.

## In the arena

`feature/gen8x-arena-20261113` merges the Gen 8 launch line (`a4858f5`, with the plans' `792c4cb`) into this engine.
`ops/prepare_gen7_alpha.py` takes a bot entry with an `x8` block and a `rollout_policy` artifact (built as the Gen 8
bot it extends, played by the gen8x engine, the rollout net copied into the run and pinned); `ops/gen5_runtime.py`
plays gen8x specs with X8Player. `configs/round8x-v3.json`: `8x3-32` against `8s-32` (2), `71s-32`, `5RZ32` and `1`
(1 each); `8s-32` and `71s-32` are `round8-candidate.json`'s entries unchanged (identities `269fdf1854f4`,
`7b0f58b4c403`), and read 8X v3 at the default factor for an unknown bot (0.3). A collector needs:

1. this branch; `python scripts/build_dds.py`; `sure_cpp` built from `experiments/sure_tricks/sure.cpp`
   (`research/sure-trick-table-20261112`) with `SURE_BIN` pointing at it in the collector's environment;
2. the artifacts restored: policy v4.1, system scorer v1 (`restore_model.py`), rollout net v1 (`restore.py`);
3. prepare with `--exclude-families gen8x-v3-exclusions.json` from `transfer/rollout-net-v1-training-families-20261113`
   (50,818 families: v4.1's 34,092 and rollout net v1's 21,509, read from the 82 feeds it was trained on);
4. the usual preflight (`ops/smoke_gen7.py`). 8X v3 costs about 28 CPU s a board with feature forks in matches.

## Tested

`tests/test_x8.py` (with `SURE_BIN` set; the claim tests skip without it):

- the batched rollouts take exactly what plan_rollout's card-by-card playouts take; a horizon stops and solves
- forks replay to their seat, the net's card and the forced card, and to the recorded results
- layouts and results round-trip through the record
- with nothing switched on the engine plays Gen7Player's game card for card (and `8xs0-v41` played `8x-32-v41`'s
  game on 4 boards with the real nets)
- the three claim questions agree with the first claim wrapper (`claims.py`) and with the game; a hand-over is
  exactly a position where declarer's next decision is guaranteed
- a declarer holding a guarantee keeps it and makes; rollouts end where every trick is claimed
- the mixer reading equals a direct per-layout computation
- the solver process wrapper abandons a slow question and recovers

## Not done, and limits

- More rollout nets on the same calibration pairs as they come (v1 scratch, v2).
- No played result yet. With v4.1 as the rollout net there is no reason to expect a gain over Gen 8.
- Branching inside rollouts (the net's top two or three cards at chosen turns, opponents averaged, own side
  maximised per information state) is not built: each rollout is a single line.
- Other-side nets inside rollouts are by share of layouts (`x8.others`). A rollout net that takes who is playing
  (rollout net v2, `PolicyNet.vocab`) is told the bots of both sides in every row (`x8.names`: this bot's and each
  opponent's name in the net's vocabulary); tested with a stand-in net, not yet with v2.
- The time allowances make a claim answer depend on machine speed when a question nears its limit, so two runs
  of the same board can differ there. The limits are well above the measured times (median well under 10 ms).
