# Gen 9 and SiD: bringing the conditional claims and the line finder into Gen 9 (plan, G9-A9)

> **Plan, g9, 13 November 2026. Nothing here is built or adopted.** Max, 13 Nov 07:48 UTC: "please work out a plan to
> integrate the contingent claims / sid logic in gen 9, with whatever weight you think makes sense."
>
> "SiD" is the line finder: the conditional-claims solver (`experiments/sure_tricks/cells/`, design `DESIGN.md`,
> measurements `README.md`, on `research/conditional-claims-20261113` at `baa062c`) with the outright claim finder
> `sure_cpp` as its cheapest question. The loop around it (student net, tree, self-play) is specified in
> `experiments/sid_loop/SPEC.md` on `research/sid-selfplay-loop-20261113` at `183980c`. Neither is in a bot yet.

## Summary

1. **Gen 9 supplies what SiD's answers depend on: who holds what.** A conditional claim's floor is the weight of the
   cells one line wins. The study weighted cells with the hand-fit scorer alone, which overstates the certified
   probability by 4 to 15 points above 0.25 and reads every opponent as a house bidder who signals nothing. Gen 9's
   readers (auction by profile, cards by declared scheme and honesty, experience per opponent) are built to replace
   exactly those weights.
2. **The way in is the 8X engine.** SiD's conditional claims are designed into 8X (`DESIGN.md` section 6). The Gen 9
   shell and the 8X player share a base class and the hooks that set layout weights, so a Gen 9 bot on the 8X engine
   (`X9`) hands Gen 9's weights to 8X's rollouts, claims and, once built, conditional claims and the tree, without
   changes to 8X's decision code.
3. **Weight in play: SiD is a proof, not an evaluator.** Outright claims as 8X has them. Conditional claims as floors
   on the rollouts where the certified probability is 0.9 or more, with the commitment rule and a fork on every card
   they change. The threshold comes down (0.75, then 0.5) only when the forks at the current threshold show a gain.
   No blend weight, and SiD never chooses alone.
4. **Weight in Gen 9's work: about a third of one day (13 November).** Four pieces where Gen 9 is the natural owner:
   weights for the cells, the `X9` composition, the arena for SiD's self-play loop, and defenders' conditional lines
   read through partner's signals. The solver, the labels, the student net and the tree stay with their owners (the
   solver session, x8, plan).

## 1. What exists

| Piece | Where | State | Owner |
| --- | --- | --- | --- |
| Outright claims (`sure_cpp`), declarer and defender hand-over rule | 8X engine (`x8_claims.py`) | In 8X; defender rule +0.225 +- 0.097 IMPs a decision on Gen 8 feeds (674), games, slams and doubled +0.535 +- 0.198 | x8, solver session |
| Claim floors inside rollouts | 8X | Takes a third of the loss of rollouts alone away on the calibration pairs | x8 |
| Conditional claims (cells): reference solver, measurements, design for 8X | `research/conditional-claims-20261113` | Measured on 1,520 recorded Gen 8 tables; not in a bot | solver session |
| SiD loop: labels, student net, tree, self-play rounds | `research/sid-selfplay-loop-20261113` | Specification; labels and `S_0` running on azure6 since 07:48 UTC (sidnet, `research/sid-net-s0-20261113`); round 1 of a self-play loop on the rollout bot waiting for boxes (loop, the SPEC's author) | sidnet (labels, student), loop (rounds) |
| Gen 9 readers and player models | `feature/gen9` (`gen9.py`, `player_model.py`) | In the Gen 9 shell on Gen 8's prototype engine | g9, bill, sam |

What the measurements say about weight (`cells/README.md` sections 2, 4, 7, 8; 8-card decisions, scorer weights):
- With no outright claim, the best card's certified probability averages 0.356; 17.8% of positions reach 0.9.
- Choosing by certified probability alone loses 8.5 +- 3.2 makes over 803 positions against double dummy, all of it
  where certification is partial; in the 143 positions at 0.9 or more it changes expected makes by +0.2.
- A card inside its certified set made 96.0% of the time; double-dummy making but not certified, 82.1%. So an
  uncertified layout is not a lost one, and the floor alone undervalues it.
- 32 of 1,520 tables had a sure make at 8 or 7 cards and went down (a one-sided count: what keeping to the line costs
  elsewhere is not in it).
- 8X: replacing a simulated player's cards with the claim finder's cut the gain (-0.092 +- 0.042 IMPs a board);
  flooring the result while the simulated play continues kept it.

## 2. Where Gen 9 meets SiD

### 2.1 Weights for the cells (Gen 9's main contribution)

`DESIGN.md` section 4 takes a cell's weight from the decision's layout list (`X8Player.read_layouts`): the hand-fit
scorer for the auction and the net's reading of the play. Gen 9 changes that list's weights through three hooks
`read_layouts` already calls: `type_log_weights` and `layout_log_weights` (the auction: the mixture over profiles,
the card, the replayed bidder) and `play_log_likelihood` (cards read by declared scheme, honesty and class).

Why it matters most against the opponents Gen 9 is for: the scorer reads every auction as a house auction. Against
`8c-32`'s Precision or a guest's system, the cells' weights and so the floors are wrong, and a 0.9 threshold no longer
means 0.9. Against house bots Gen 9's weights equal the scorer's (E9-9: they signal nothing; same system), so this
changes nothing there.

**E9-24 (13 Nov, `reports/gen9-sid-weights-2026-11-13`).** On native Gen 8 tables where `8c-32` (Precision) defends,
the scorer gives the actual layout under 1% of a uniform weight in 15% to 16% of positions; Gen 9's replay of the
defenders' own bidder never does. Overall calibration moves little (floor minus realised above 0.25: +0.099 to
+0.083 at 8 cards, +0.107 to +0.089 at 7). At the 0.9 threshold the weights decide which lines are taken: committed
lines failed 8.7% of the time with the scorer's weights (231 lines; house control 5.0%) and 3.5% with Gen 9's (228).
The scorer alone certified 25 lines that covered the actual layout 44% of the time; Gen 9 alone certified 22 that
covered it 91%. So Gen 9's weights are what keeps a 0.9 floor meaning 0.9 against another system.

### 2.2 `X9`: the Gen 9 shell on the 8X engine

`X8Player(Gen7Player)` and `Gen9Player(SignalPlayer(Gen7Player))` share a base, and 8X's decision code calls the
weight hooks through `self`. So `class X9Player(X8Player, Gen9Player)` runs 8X's decisions on Gen 9's readings.
Both branches use the same `bridge_harness/gen7.py`, so the work is to bring Gen 9's own files (`gen9.py`,
`gen9_play.py`, `player_model.py`, `experience.py`, the signal readers) onto a branch from the 8X engine: the base swap
of G9-A5, done against the 8X branch instead of main. Three things to settle in the composition:
- `meet`: 8X keeps `opponent_id` for its claim and mixing settings; Gen 9 passes a `PlayerModel` or an id. `X9`
  passes the id to 8X and the model to Gen 9.
- Reading a mixer: 8X pools a mixer's run of touching cards (`x8.mix.read_*`); Gen 9 reads randomizers by class
  (E9-16 part 2: scaling a reader down costs 0.29 +- 0.15 IMPs). One reading per seat: Gen 9's class reading where
  the opponent declares a scheme, 8X's pooling otherwise.
- `x8.names` (who each side is, for rollout net v2): for a newcomer, the profile the arrival mixture believes
  (E9-22) instead of the generic row.

Test, as every Gen 9 input: with nothing declared and empty experience, `X9` plays exactly as the 8X bot it wraps.
Built 13 Nov 08:30 UTC on `feature/gen9-x9` (ed2806f, from `feature/gen8x-arena-20261113` at 3d93d78): card for card
with 8X off, with rollouts and the blend, and with rollouts and the winning-line logic (`sure_cpp` from 2e6ed6d); the
8X and Gen 9 test files pass on that base. `x8.names` for a newcomer is not in it yet (E9-22).

### 2.3 Opponents inside the rollouts and the tree

SiD's tree (SPEC Part C) plays the other seats from their own views with the net, and that is where their mistakes
enter. Gen 9 supplies who they are (2.2) and, for opponents with a declared scheme, how their signals read, so that
the net's simulated defenders signal and read as those defenders do. Nothing beyond 2.2 is needed until the tree
exists.

### 2.4 Defenders' conditional lines through partner's signals

`DESIGN.md` section 8 leaves "we beat it if partner holds X" as a different game (two hands that cannot see each
other). Partner's signals are how a defender learns whether partner holds X, so this is Gen 9's (sam's) question.
The bound (G9-S9, 13 Nov, `reports/gen9-defender-bound-2026-11-13`): at the first defender decision with 8 and with
7 cards (4,577 recorded positions, 48 uniform layouts each), the defender's card changes whether declarer gets a
guaranteed line in only 8.2% of positions. Knowing the whole layout would lower the hand-over probability by 0.004
a position (0.051 where the choice matters); knowing one partner honour gets 77% of that, and lowers it by 0.10 or
more in 0.7% of positions. So this piece gets low weight: no defender-side conditional-line solver now.

### 2.5 The arena for SiD's self-play loop

The loop session is starting round 1 on the rollout bot now (board, 07:56 UTC). SPEC Part E leaves the population to the arena: a share of each round against earlier rounds and outside bots,
exploitability from round 2 (E4), yardsticks never trained on (E5). These are the roles of
[the arena note](arena-selfplay.md): each SiD round enters as a league member and stays as a past champion;
exploiters and the informed reader of 6.1 are E4; held-out styles and outside panel are E5. Promotion uses the arena
test at a lead of 0.10 IMPs (issue #24), with smaller gains through the bench.

### 2.6 Leakage and disclosure

The commitment rule makes declarer's cards follow one line, and the line chosen depends on declarer's hidden hand.
The informed-reader report (E9-23) runs on `X9` as on any champion. Randomizing among exactly equal cards stays on,
restricted to cards with equal floors and equal rollout values so it costs nothing.

## 3. Weight in play

| Answer | Gen 9 uses it as | Starting setting | How the weight moves |
| --- | --- | --- | --- |
| Outright claim (declarer) | Only guaranteeing cards are candidates | Games, slams, doubled (8X `contracts`) | As 8X |
| Defender hand-over odds | 8X's rule, on the defender's own weighted layouts (Gen 9's) instead of uniform ones | 8X's `odds_margin` 0.125 | A fork feature: kept if the forks show a gain |
| Conditional claim (declarer) | Floor on the rollouts for layouts inside the chosen card's certified set; commitment at the next decision | Shape level (no named cards), 8 cards or fewer, floor of 0.9 or more, games, slams, doubled | Down to 0.75, then 0.5, each step only when the forks at the current threshold show a gain of 2 SE in IMPs |
| Named cards, segments | As above, second level | Off | After the shape level is priced |
| Student net's heads (SPEC Part B) | Candidates and odds, never a floor | Off | SPEC's gates |

Why not a blend weight: the floor already counts certified layouts as made and leaves the rest to the rollouts, which
is what the measurements reward (certified alone loses where certification is partial; flooring kept 8X's gain,
substituting lost it). Why 0.9 first: at 0.9 or more the certified choice was neutral in expected makes on recorded
play, so the threshold starts where the floor cannot do harm and moves on played evidence.

## 4. Weight in Gen 9's work

About a third of the team's effort for one day, 13 November (Max, 08:02 UTC: "a third for a day, or less"), each
piece in a lead's own session (no sub-agents, Max, 07:48 UTC), all in the review package:

| Piece | Who | Aim (UTC, estimates) |
| --- | --- | --- |
| E9-24: calibration of floors by weight source | g9 | done 08:20 |
| `X9`: the Gen 9 shell on the 8X engine, inert by default, with tests | g9 | done 08:30 (`feature/gen9-x9`, ed2806f) |
| Defenders' conditional lines: the bound of 2.4 | g9 (sam away) | done 09:05 |
| The arena interface for SiD's rounds (2.5) | dave, g9 | posted on the board at 07:57 |

Not Gen 9's: `sure.cpp` and `cells.cpp` (solver session), conditional claims inside the 8X engine (`DESIGN.md`
section 6; x8, or g9 on a branch of the 8X engine offered back to x8 if x8 prefers), the labels and student
(sidnet), the tree and the rounds (loop, x8). The other two thirds of the day stay on the arena and the readers.

## 5. Order

| Step | What | Needs | When |
| --- | --- | --- | --- |
| 1 | E9-24 on recorded positions | `cells.cpp`, Gen 8 feeds, the Gen 9 shell | Done 08:20 UTC |
| 2 | `X9` with tests | the 8X engine at its current commit | Done 08:30 UTC: `feature/gen9-x9` at ed2806f |
| 3 | Conditional claims in 8X (`DESIGN.md` 6) | owner agreed with x8 | x8's call |
| 4 | `X9` with conditional claims against the 8X bot it wraps, forks on, on a Gen 9 box | 2, 3 | After 3 |
| 5 | Defenders' bound (2.4) | 8X's hand-over code, recorded defender decisions | Done 09:05 UTC: little to unlock |
| 6 | SiD rounds in the arena (2.5) | SPEC steps 1 to 7 by their owners | When the first round exists |

## 6. Unknown

- How the 0.9 rule's failures translate into IMPs: E9-24 counts lines, not contracts.
- The cost of SiD at 8 cards (mean 117 ms, 99th percentile 1.1 s, one thread, no table) inside a Gen 9 bot that also
  runs the profile mixture; measured in step 4.
- Whether conditional claims gain in play at all: nothing has been played.
- Defenders' own guaranteed defeats (a solver for two hands that cannot see each other), and earlier decisions than
  the bound covered.

## Tasks

`team/gen9`: G9-A9 (this plan), E9-24, G9-A10 (`X9`), G9-S9 (defenders' bound), and the SiD rounds in G9-D10's
arena work.
