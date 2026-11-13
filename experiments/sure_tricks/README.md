# Strategy-fusion test set and single-dummy sure tricks

12 November 2026. Built against `maxschireson/Single-Dummy-Bridge` main (shallow clone of that day), using its `bridge_harness` engine, DDS build and model files. `mkreadme.py` assembled the tables and most counts from the result files; a few counts quoted in the text were read off script output by hand.

## Contents

| File | What it is |
| --- | --- |
| `fusion_deals.json`, `fusion_deals.pbn` | 9 sets, 17 deals. JSON fields load with `Board.from_dict`; extra fields: `set`, `layout`, `weight`, `avoid`, `critical`. |
| `fusion_test.py` | Runs a declarer over the sets against the oracle defender and scores by set. |
| `fusionlab.py` | `OracleDefender`, `run()`, bot factories (repo PIMC, local Gen 6, Gen 7 standard). |
| `exact.py` | Exact single-dummy value against best defence for a small set of layouts (Pareto fronts over layouts). Used to certify each set. |
| `sure.py`, `surebot.py` | Single-dummy sure tricks (pooled-defender search) and the rule "a card that guarantees the contract comes first" as a wrapper on any declarer. |
| `sure.cpp`, `SEARCH.md` | The same sure-trick search in C++ above a resident table of small endings, with its checks, timings and table sizes. Helpers: `csure.py`, `check_cpp.py`, `check_cpp_positions.py`, `bench_cpp.py`, `check_cpp_builds.py`, `runpos.py`, `split.py`, `ordtest.py`, `build_cost.py`, `gen_table_positions.py`, `table_size.py`, `table_size_shapes.py`, `mksearch.py`. |
| `TABLE_BUILD.md`, `pooled_ref.py`, `endtable_ref.py`, `endtable_vectors.jsonl` | Build specification for the resident ending table, with the reference for the game under shape knowledge, the reference index and test vectors. Checks: `check_pooled_ref.py`, `check_endtable_ref.py`, `make_vectors.py`. |
| `verify.py`, `scripted.py`, `trace.py`, `third_hand.py`, `families.py`, `report.py`, `to_pbn.py`, `check_sure.py`, `check_sure_reduction.py`, `run_surebot.py`, `sure_positions.py`, `lookup_gain.py`, `mkreadme.py` | Checks, generation and reporting. |
| `results/` | Raw runs and certification output. |

Run: `SDB_ROOT=/path/to/Single-Dummy-Bridge python fusion_test.py fusion_deals.json --bot gen6 --seeds 6` (DDS built with `scripts/build_dds.py`; hand-fit scorer v0, Gen 5 policy and Gen 7 policy v4 restored with their `restore` scripts).

## 1. How the error arises, in numbers

Set A6: 6♠, ♦AJ5 opposite ♦K104, one club loser, a sure strip-and-club-exit. Position after the heart lead and two rounds of trumps (10 cards left, North to lead). Two layouts, ♦Q with West (3 diamonds) or East (4), weighted 15:20. "Fused" is the PIMC value (share of layouts where the card is double-dummy good enough). "True" is the best any single line starting with that card can do against best defence (`exact.py`).

| Card | Fused | True |
| --- | --- | --- |
| ♠7 ♠Q ♥A ♣3 ♣7 ♣A | 1.00 | 1.00 |
| ♦4 | 1.00 | 0.57 |
| ♦10 ♦K | 0.57 | 0.57 |

The low diamond is rated the same as the cards that keep the sure line. It is not rated higher: in this family the error is a tie, not a wrong preference. The clubs are 1.00 true as well as the hearts because there is more than one sound order of play.

After ♦4 and a low card from East the two layouts give ♦J 0.57 fused and 0.57 true, ♦A 0.43 and 0.43. Gen 6's own sample at that card (same hands) read ♦A 11.60, ♦J 11.43, ♦5 11.00 mean tricks: rising with the far honour scores higher than the finesse because in part of the sample double dummy can still endplay the other defender. When it led the diamond, ♦4 and ♣7 were both 12.0.

Other ties the certification tables show (all 1.00 fused):

- A4 (4♠): a club before the second top heart is cashed is 0.57 true. The defenders take their clubs and get off lead in hearts.
- B6 (master trump with West): the trump exit before the strip is 0.57 true. ♦5 to the king stays 1.00, because West will be the one on lead and must lead into the ace-jack; ♦A is 0.43.
- B6m (master trump with East): the reverse. ♦5 to the king is 0.57 true, ♦A stays 1.00. A heart to the queen at that point (dummy's entry, needed later for the club ruff) is 0.57.
- S6: the club exit before the hearts are eliminated is 0.50 true.
- L6 (the A6 hands on a low diamond lead, trick one): low or the ten from dummy is 1.00 true, the king 0.57 fused and 0.57 true.

## 2. The queen in the three-card hand

Hypothesis: the declarer misses the endplay, falls back on the guess, takes it with the odds and so fails when the queen is in the shorter holding. Tested on the A6 hands in four layouts (136 runs: repo `PIMCPlayer` with the make objective and random ties, local Gen 6, Gen 7 standard with and without the tree), before the sets were finalised.

- Declarer broke diamonds itself in 134 of 136 runs.
- Low to the ace first (leaves only the finesse through West): made 27/27 with the queen West, 0/32 with the queen East.
- Low to the king first (leaves only the finesse through East): made 1/31 with the queen West, 25/26 with the queen East.
- Immediate finesse: made 5 of 18.

| Layout | PIMC make | Gen 6 | Gen 7 std |
| --- | --- | --- | --- |
| Q West, 3 diamonds | 9/20 | 2/2 | 4/10 |
| Q East, 4 diamonds | 9/20 | 0/2 | 4/10 |
| Q East, 3 diamonds | 11/20 | 0/2 | 4/10 |
| Q West, 4 diamonds | 6/20 | 2/2 | 5/10 |

The length of the queen's suit did not decide the result. Which top honour was cashed first did, and that was set by which hand was on lead when the tie was broken (Gen 6: always dummy, so always the ace). The odds were not consulted at that point: the fused value of rising with the far honour was higher than that of either finesse.

Reference pair G7 (7♠, the same diamond suit, nothing can be thrown in, and the count shows diamonds 3-4 once hearts and clubs have been played): Gen 6 made 6/6 with the queen in the three-card hand and 0/6 with it in the four-card hand; Gen 7 standard 6/6 and 0/6; random-tie PIMC 11/20 and 15/20. Gen 6 led low to the ace at trick 9 in all twelve runs and finessed West. The direction is habit, not count.

Consequence for test design: one layout with the queen in the short hand is decided by tie-breaks. A pair of layouts that differ only by exchanging the queen with a spot card fails any line that needs the guess in at least one of the two. Each set is such a pair; within a set the layouts share one random stream per seed.

## 3. The defenders

A plain double-dummy defender is not a usable opponent for these deals. Once the contract is "cold" because double dummy guesses the queen, every defensive card is double-dummy equal. Against a defender that plays its lowest double-dummy-optimal card, Gen 6 made A6-QE in 2 of 2 runs (after winning a club at trick 8 East led a diamond round to the tenace); against `OracleDefender`, 0 of 6. An intermediate version that only refused to lead the suit threw club winners until declarer's third club stood up.

`OracleDefender` plays double-dummy optimally on the true deal and breaks ties, in order: best in the deal where the queen is promoted above declarer's honours (so the guess cannot succeed), not leading the critical suit, keeping length with declarer and dummy when discarding, lowest card. On the A6 and S6 hands scripted guessing lines were checked to be down against it in the wrong layout. The same indifference applies to a PIMC defender at the table.

## 4. The sets and what the bots did

Bold = sets passed out of seeds (every layout made in the same seed); in brackets, makes per layout in the order listed. Gen 6 = local 6-32 built as in `scripts/gen7_check.py`. Gen 7 std = the `7s-32` block of `configs/round7-candidate-phase1.json`. PIMC = repo `PIMCPlayer`, make objective, 32 uniform layouts, random ties; its seeds were not coupled within a set except on S6, so only makes per layout are shown.

| Set | Kind | Contract, layouts | Gen 6 | Gen 7 std | PIMC make |
| --- | --- | --- | --- | --- | --- |
| A6 | tie | 6♠. DQ West (3 diamonds, 2 trumps); DQ East (4 diamonds, 1 trump) | **0/6** (6/6 0/6) | **0/6** (5/6 1/6) | 3/10 3/10 |
| A6m | tie | 6♠. DQ East (3 diamonds, 2 trumps); DQ West (4 diamonds, 1 trump) | **0/6** (0/6 6/6) | **1/6** (2/6 5/6) | 9/10 3/6 |
| A4 | tie | 4♠. DQ West (3 diamonds); DQ East (4 diamonds) | **0/6** (1/6 5/6) | **1/6** (3/6 4/6) | 5/6 6/6 |
| B6 | tie | 6♠. master trump West, DQ West (3 diamonds); master trump West, DQ East (4 diamonds) | **0/6** (0/6 6/6) | **0/6** (0/6 0/6) | 2/6 5/6 |
| B6m | tie | 6♠. master trump East, DQ East (3 diamonds); master trump East, DQ West (4 diamonds) | **0/6** (6/6 0/6) | **0/6** (0/6 4/6) | 2/6 3/6 |
| S6 | strict | 6♠. DQ West, diamonds 3-3; DQ East, diamonds 3-3 | **0/6** (6/6 0/6) | **0/6** (3/6 3/6) | **0/6** (3/6 3/6) |
| G7 | reference | 7♠. DQ in the three-card hand (West); DQ in the four-card hand (East) | 6/6 0/6 | 6/6 0/6 | 11/20 15/20 |
| C1 | control | 4♠. DK West, DA East | **6/6** (6/6) | **6/6** (6/6) | 6/6 |
| L6 | tie | 6♠. DQ West (led from the queen); DQ East | **6/6** (6/6 6/6) | **6/6** (6/6 6/6) | 6/6 6/6 |

On the six trap sets (A6, A6m, A4, B6, B6m, S6) Gen 6 passed 0 of 36 set-seeds and Gen 7 standard 2 of 36. Both passed the control C1 (frozen suit: double dummy itself needs the exit) and L6 every time.

- Gen 6 led diamonds itself in all 72 trap-set runs: low from dummy to the ace on A6, A6m and S6, low from hand to the king on B6 and B6m and mostly on A4. At those decisions the diamond and the sound cards were exact ties in mean tricks (A6: ♦4 12.0, ♣7 12.0), so the selector net chose.
- Gen 7 standard also led diamonds itself in all 72. The first diamond lead came at tricks 5 to 11, at trick 7 or later in 64 of 72; the tree (tricks 3 to 6) was consulted at that decision in 8.
- S6 is the strict case. Keeping the guess averages above 12 tricks over sampled layouts (a thirteenth trick when the queen is picked up and the fourth diamond takes the club), the exit exactly 12 (Gen 6 at trick 5: ♦2 and ♥A 12.69, ♣6 12.00), so a mean-tricks ranking puts the exit below the rest and the tie-break never sees it.

**A6. Two-way queen, strip and club exit, 6S.** AJ5 opposite K104. Every card that does not commit the diamonds is double-dummy equal, including the low diamond lead and extra rounds of trumps that destroy the ending. Sound line: Win the heart, draw trumps in two rounds, cash the other top heart and the two top clubs, exit with the third club. Whoever wins must lead a diamond (three diamond tricks whatever he leads) or give a ruff and discard (ruff in one hand, throw a diamond from the other, ruff the third diamond).

**A6m. Two-way queen, strip and club exit, 6S (East-West hands exchanged).** Mirror of A6, so a declarer with a fixed habit in the diamond suit is caught on the other side as well. Sound line: Win the heart, draw trumps in two rounds, cash the other top heart and the two top clubs, exit with the third club. Whoever wins must lead a diamond (three diamond tricks whatever he leads) or give a ruff and discard (ruff in one hand, throw a diamond from the other, ruff the third diamond).

**A4. Two-way queen, strip and club exit, 4S.** A105 opposite KJ4 with three club losers. Declarer gives up the clubs only after hearts are gone. Sound line: Win the heart, draw trumps, cash the other top heart, play a club. The defenders take their three clubs and the one on lead must open diamonds or give a ruff and discard.

**B6. Two-way queen, throw-in with the master trump, 6S.** The only loser is the master trump, so it is also the exit card. Cashing the wrong top diamond first leaves the defender a safe diamond lead through the remaining honour. Sound line: Win the club, cash the two top trumps (one defender keeps the master trump), cash the other top club and three hearts ending in dummy, ruff dummy's last club, exit with a trump. The defender with the master trump must lead a diamond or give a ruff and discard.

**B6m. Two-way queen, throw-in with the master trump, 6S (East-West hands exchanged).** Mirror of B6: the master trump is with East. Sound line: Win the club, cash the two top trumps (one defender keeps the master trump), cash the other top club and three hearts ending in dummy, ruff dummy's last club, exit with a trump. The defender with the master trump must lead a diamond or give a ruff and discard.

**S6. Two-way queen where keeping the guess looks worth an overtrick, 6S.** K1042 opposite AJ5, club lead taking out the ace. If the queen is picked up and the suit runs, the fourth diamond takes care of the club and thirteen tricks make, so every card that keeps the guess averages above 12 over the sampled layouts; the club exit concedes a trick and is exactly 12. On tricks or score the exit is strictly below the rest. A wrong view of the queen loses a diamond and a club. Sound line: Win the club, draw trumps, cash the top hearts and ruff the third, exit with the club. The defender on lead must open diamonds or give a ruff and discard.

**G7. Two-way queen in a grand slam with a full count available, 7S (reference, not scored).** Nothing removes the guess. After trumps, hearts and clubs the count is complete: diamonds are 3-4, so the queen is 4:3 to be in the four-card hand. A declarer who guesses with that count makes G7-QE and fails G7-QW; one who guesses before the count is at even money on both. Sound line: None. The percentage line is to take the count and play the four-card hand for the queen.

**C1. Frozen suit (Q42 opposite J53), strip and club exit, 4S.** Control. With the diamond honours split, leading the suit loses three tricks in it even double dummy, so the sampled layouts themselves show that the exit is needed. A search on double-dummy values should pass. Sound line: As A6: draw trumps, cash hearts and top clubs, exit with the third club; the defenders must open diamonds or give a ruff and discard.

**L6. The A6 hands on a low diamond lead.** The lead comes round to the tenace. Low or the ten from dummy gives three diamond tricks whatever East does. The king is double-dummy equal to both and leaves the same guess as before. Sound line: Play low (or the ten) from dummy and win as cheaply as possible in hand; then draw trumps and cash the other two top diamonds.

## 5. Single-dummy sure tricks (the pooled-defender search)

The tricks declarer can guarantee against every split of the unseen cards are the value of a perfect-information game: the defenders' cards form one pool, and who holds a card is settled only when it is played, subject to hand sizes, show-outs and any cards pinned to one defender. `sure.py` searches that game. Nothing is sampled. Pinning cards or voids gives the guarantee under that much knowledge ("1.x dummy"); pinning everything is double dummy.

Guaranteed total tricks by card at positions from the sets (Python prototype, no layouts sampled):

| Set | Cards left | Pinned | Guaranteed total | Time |
| --- | --- | --- | --- | --- |
| A6, after hearts and one top club | 8 | nothing | ♠9 ♣4 ♣6 → 12; ♦5 ♦J ♦A → 11 | 182 s |
| A6, after hearts and both top clubs | 7 | nothing | ♠7 ♠Q ♣7 → 12; ♦4 ♦10 ♦K → 11 | 31 s |
| B6, after two top trumps, top club, heart ace | 8 | nothing | ♠3 ♥3 ♥K ♦5 ♦J ♦A → 11 | 128 s |
| B6, same position | 8 | HT H9 CJ to West | ♥3 ♥K ♦5 → 12; ♠3 ♦J ♦A → 11 | 85 s |
| S6, after the third heart is ruffed | 7 | nothing | ♠8 ♠Q ♣7 → 12; ♦2 ♦4 ♦10 ♦K → 11 | 107 s |

- A6 and S6: the cards of the sound line guarantee the contract and every diamond card one trick fewer. Double dummy rates them equal (A6) or the diamond cards higher (S6, on mean tricks).
- B6: with nothing pinned every card guarantees only 11, because the defender with the master trump might be short in a side suit and ruff in. The plain sure-trick number separates nothing there. With three of that defender's side cards pinned it gives the same answer as the certification table, including which top diamond is safe to cash. That is the conditional form ("12 tricks whenever West follows to the hearts and clubs"), and the conditions then need weights.

The rule "a card that guarantees the contract beats one that does not" (`surebot.py`, nothing pinned, applied from 8 cards left) on top of Gen 6, one seed per layout:

| Layout | Gen 6 alone | Gen 6 + rule | Cards the rule changed |
| --- | --- | --- | --- |
| A6-QW | 6/6 | made, 12 tricks | trick 6 ♠10→♥3, trick 7 ♠Q→♣3, trick 7 ♣6→♣K, trick 8 ♠10→♣4, trick 9 ♠Q→♣7 |
| S6-QW | 6/6 | made, 13 tricks | none |

On A6-QW the rule kept Gen 6 from the fifth round of trumps and made it cash the clubs and exit; the first diamond was then led by East at trick 10. On S6 Gen 6 leads the diamond at trick 5 with 9 cards left, before the rule applies in this prototype (8 cards, for speed), so nothing changed. A6-QE and S6-QE were not run with the corrected search: the first attempt died (two searches in parallel, probably out of memory) and the rerun was stopped. The rule has therefore not yet been shown to pass a whole set.

Speed. The prototype searches 24 to 65 thousand nodes a second and keys its table on exact cards. The repo's DDS build on the same machine ran a full 13-card solve of A6 at 2.6 million nodes a second (556 thousand nodes, 0.21 s). A C++ version with a rank-relative table, bounds and move ordering is in `sure.cpp`; its timings are in `SEARCH.md`. Known inefficiencies of the prototype: no rank-relative transposition table, a yes/no search per trick target instead of stored bounds, no sure-winner bounds, no use of the symmetry between the two defenders when nothing distinguishes them, a fresh table for every decision, and it is asked about every legal card rather than only the cards tied under double dummy.

A lookup of small endings (`lookup_gain.py`, counting nodes in the prototype, a perfect table assumed): from 7 cards left (A6) 2,005,757 nodes become 98,705 with a 4-card table (73,471 above it plus 25,234 distinct table positions, 20×) and 9,639 with a 5-card table (208×); from 8 cards left (B6) 5,197,871 nodes become 687,604 with a 4-card table (552,952 above it plus 134,652 distinct table positions, 8×) and 115,118 with a 5-card table (45×). These are node counts in an unoptimized search. A search with a rank-relative table would already repeat less near the bottom, so the gain on top of that is unmeasured, and a probe is not free.

Checks on `sure.py`. It agrees with `exact.py` run over every layout on 300 random 3-card and 60 random 4-card endings drawn from short suits so that touching cards are common (0 mismatches), and its touching-card reduction agrees with the unreduced search on 1,500 4-card and 300 5-card endings. A first version pruned a defender's touching cards to the lowest one before his partner had played to the trick. That is unsound in a pooled game (the eight leaves partner only higher cards of the run, the queen only lower ones, which decides who is on lead) and it made the rule accept a diamond lead on S6-QE. On 9 endings where that pruning changed the answer, the corrected unreduced search matched `exact.py` on all 9; the two-ended reduction now used was then checked against the unreduced search as above. Random endings exercise this case rarely (1 in 1,500), so the checks are thinner there than the counts suggest.

Sizes, by my count (arrangements of the remaining cards as North / South / unseen, cut into suits, divided by suit symmetry, per side on lead): 3-card endings about 3.5×10⁵ at notrump and 1.4×10⁶ with a trump suit; 4-card 3.6×10⁷ and 1.5×10⁸; 5-card 3.4×10⁹ and 1.4×10¹⁰, before show-out and pinned-card variants. Three and four cards tabulate easily. Five is large as a full table; solving on demand and caching by rank-relative position avoids it, and the search is not limited to five cards. Python timings above are for 7 and 8 cards.

## 6. Limits

- The exact tables cover only the layouts in each set (two), from the stated position (after 0 to 3 tricks). "True 1.00" means one line makes in both layouts, not in every layout a sampler would draw.
- Gen 6 and Gen 7 are local builds from the repo recipe (hand-fit scorer for layouts at every trick, lead net not loaded), not the frozen arena actors. Six seeds per layout; one seed, and two layouts only, for the rule runs.
- The auctions are hand-written, not produced by the bidder, so the scorer may be off its training distribution.
- The oracle defender is double-dummy optimal with tie-break rules. It is not proven to be the strongest defence against each declarer.
- The sure-trick search at 7 and 8 cards has no independent check beyond agreeing with the exact tables' ordering (see the checks in section 5) and with the C++ version on the same positions (`SEARCH.md`).
- S6: the claim that the exit is also better on true expected tricks rests on a hand calculation for one guessing line (about 11.8 against 12), not on a solver.
- Dropped after certification: a nine-card-fit set (no line wins all four layouts: after the ruff and discard the guess remains) and a count-the-hand set (the low diamond lead itself exposed a void). Information gained before a guess is therefore not covered by a scored set.

## References

- Frank and Basin, "Search in games with incomplete information: a case study using bridge card play", Artificial Intelligence 100 (1998): strategy fusion and non-locality.
- Cazenave and Ventos, "The αμ search algorithm for the game of Bridge", arXiv 1911.07960: Pareto fronts over layouts, defenders with perfect information. `exact.py` is that idea run to the end of the hand on a few layouts.
