# Conditional claims: cells, the search, and their use in play

Status, 13 November 2026: a design, a reference solver (`cells.cpp`) and measurements on recorded Gen 8 arena
positions (`README.md`). Nothing here is in a bot or in `sure.cpp`. Written so that the search owner and the 8X
session can implement it without the conversation that produced it.

It answers two asks:

1. use whole-shape guarantees in actual play (the 4-card ending table already stores them);
2. extend guaranteed lines to lines that hold when named cards lie in a named hand.

## 1. Terms

- **Cell.** A condition on the two hidden hands: East's number of cards in each suit and, for each *named* card,
  which defender holds it. Every other unseen card stays pooled, as in `sure.cpp`.
- **Cell set.** Any set of cells. The declaring side's knowledge at a point of the search is the set of cells still
  consistent with the cards the defenders have played (the *live* set).
- **Question.** For a position, a card, a trick target and a cell set: does one line starting with that card take the
  target in every layout of every cell of the set, against every defence. Yes or no.
- **Ceiling** of a card: the weight of the cells in which it wins when each cell is asked alone. Different cells may
  need different lines, so this is fused over cells in the same way PIMC is fused over layouts.
- **Floor** of a card: the weight of a set of cells that passes as one question. It is a lower bound on the
  probability of making under the weights used, against best defence.
- **Certified set**: the set behind the floor.

Special cases: every shape consistent with hand sizes and show-outs, no named card, is the game `sure.cpp` plays
today. One shape and no named card is a whole-shape entry of the ending table.

## 2. The game

`cells.cpp` is the definition; `celllib.Brute` is an independent statement of the same thing over explicit layouts.

- A defender may play an unnamed card of suit `s` when some live cell gives him an unnamed card of `s`; a named card
  when some live cell pins it to him. If the card does not follow suit, the cell must also give him no card of the
  suit led (no unnamed card of it left, and no named card of it pinned to him).
- After his card the live set is the cells in which that play was legal.
- The declaring side sees its hands and the cards played, so the game has perfect information. Minimax on the
  target answers the question, and a yes is one line for the whole set.

## 3. What changes in the search

1. **Knowledge.** A list of root cells, a bit set of live cells, and per suit the number of unnamed cards each
   defender has played since the root. The legal set of a play is an AND of precomputed bit sets (cells with exactly
   or at least so many unnamed cards in a suit, cells pinning a named card to East).
2. **Table key.** The card code marks named cards. The knowledge enters as an order-free hash of the live cells'
   residual lengths and pins. The value depends only on the key, so entries stay valid across questions, across
   levels of naming and across decisions.
3. **Defender's cards.** Per run of touching unnamed cards: one card, or the lowest, a middle and the highest when
   his partner is still to play to the trick and may hold the suit. `sure.cpp`'s lowest-and-highest rule is wrong
   (section 3 of `README.md`). A middle card alone also passed every check and is cheaper to search; it is an
   option (`--def mid`), not the default.
4. **Bounds.** The declaring side's sure-winner bounds hold for any split and stay as they are. The defenders'
   bounds in `sure.cpp` (`defCash`, `defTrumpSure`) assume the leader can be given any masters his hand size and the
   show-outs allow. Under a cell he may not have the length, so those bounds are unsound here until they read the
   cells. The reference solver uses none.
5. **Ending table.** One cell with no named card is a whole-shape entry: read it. The set of every shape consistent
   with per-suit exact-or-unknown lengths is the entry read today. For other sets: the entry for the hull (exact
   where the live cells agree, unknown elsewhere) is a lower bound, and the minimum of the live cells' whole-shape
   entries an upper bound; search on when they disagree with the target. With named cards still unseen, the entry
   with the names dropped is a lower bound only. Not implemented; the gain is estimated in `README.md` from node
   depths.

## 4. One declarer-side decision

Applies with `cards` or fewer cards, the contract not yet settled, after the outright question has said no.

1. **Cells and weights.** The shapes consistent with hand sizes and show-outs. A cell's weight is the summed weight
   of its layouts in the decision's layout list (`X8Player.read_layouts`: every card-fit layout from trick 6,
   weighted by the hand-fit scorer and the net's reading of the play). Take cells heaviest first until 99% of the
   weight is covered; the rest counts as not certified.
2. **One question per cell**, for the candidate cards only. This gives each card's ceiling. A cell no card wins
   alone is lost whatever is played.
3. **Joint step**, for cards in falling order of ceiling, stopping when a card's ceiling cannot beat the best floor
   so far. Ask the card's whole winning set as one question. If it fails, grow a set heaviest cell first, keeping a
   cell when the enlarged set still passes. Keep the certified set and the floor.
4. **Named cards, by refinement** (section 5), when the best floor leaves weight uncertified. A level with more
   named cards inherits from the level above: a card that wins a cell alone wins each of its sub-cells alone, and
   the sub-cells of a certified set are certified by the same line. Only failing cells are searched again, and the
   refined set is the seed of the joint step.

A search that returns the winning set in one pass (declarer takes the heaviest child set, a cell survives a
defender's node if it survives every card it allows) was built and dropped: on the
7 pilot positions without an outright claim it took more nodes than step 3 in 6 (1.9 times to well over 10 times) and
fewer in one small position, and its floor for the best card was never higher. It is in `cells.cpp` as the `W` query.

## 5. Which cards to name

- Rank is relative to declarer's cards. The unit is a **run**: unseen cards of a suit with no North-South card
  between them. Cards of a run are interchangeable, so naming any one of them is the same condition.
- Classes: *top* (no North-South card of the suit above the run), *middle* (North-South cards on both sides),
  *bottom* (none below it: the two under declarer's three), *free* (North-South hold none of the suit).
- Measured on 300 positions per card count: top and middle runs carry nearly all of the gain; a bottom run added
  0.05 or more in about 3% of positions and never 0.20; the card of the best run was a nine or lower in 7 of 120
  cases at 8 cards. Naming a third card added 0.002 to the mean floor.
- A fixed rule for choosing the card missed the best run by more than 0.02 in 37 of the 120 positions at 8 cards
  where naming a run added 0.05 or more. The better source is the failed question: its refutation shows which card the defence needed in
  which hand. Not built.
- Naming one card of a run of several says less than it could. The fuller form is a cell that carries East's count
  in each run it splits (a suit cut at one of declarer's cards). A named card is the one-card case. In the solver
  this replaces "suit" by "segment" in the unnamed-card counts. Not built, not measured.

## 6. In the bot

All in `bridge_harness/x8_player.py` and `x8_claims.py`; nothing new in the rollout code.

- **Where.** `choose` already calls `root_claim`. When its state is `open`, run section 4 for the stage's
  candidates and keep `{card: certified set}` for the decision.
- **Candidates.** As today, plus the card with the best floor when the stage's own candidates leave it out.
- **Floors.** `first_floor` returns `floor0[layout, card]`, and `roll` and `means` already apply it per layout and
  per card. Set it true where the layout's cell is in that card's certified set. The rollouts then value the
  uncertified layouts and the overtricks, and no blending weight is added.
- **Commitment.** Store the chosen card's certified set. At the declaring side's next decision ask one question:
  which cards keep the cells of that set that are still live. Cards that do not are dropped unless the new
  decision certifies a heavier set. Without this the bot can leave the line the floor assumed.
- **Contract class.** As `claims.contracts`: games, slams and doubled contracts first.
- **Time.** As the other claim questions: an allowance per decision, a question that outlasts it is "not known" and
  moves nothing.
- **Defenders.** Unchanged. Handing declarer a conditional line is not a hand-over.
- **Settings to add to `ClaimUse`.** `conditional` (cards or fewer at which section 4 runs; 0 = off),
  `conditional_mass` (0.99), `named` (0 to 2), `conditional_ms`, `conditional_min` (a floor below this is recorded
  but does not set `floor0`).
- **Record.** Per decision: the cells asked with their weights, each candidate's ceiling, floor and certified set,
  the chosen card, timings. After the deal, the true cell is known, which gives without any fork:
  claimed probability against how often the true cell was inside (the beliefs' calibration);
  a certified cell that was lost with the line kept (a solver or bot bug).
- **Forks.** `guarantee`-style feature name (`conditional`) in `audit_features`, so every decision the feature
  changes is forked against the card the bot would otherwise have played.

## 7. Order of work

1. `sure.cpp`: the defender-card rule (section 3.3). Independent of everything else, and it affects the bots
   running today.
2. `sure.cpp`: cells without named cards (sections 3.1, 3.2, 3.4), checked against `cells.cpp` and the ending
   table's whole-shape entries.
3. 8X: section 6 with shapes only, recording on, `conditional_min` high (0.9), forks on. Price it by forks.
4. Named cards (sections 3 and 5), then segments.
5. Table bounds for sets (section 3.5).

## 8. Not done, and unknown

- No bot has played with this. The counts in `README.md` of contracts that "would have made" assume the certified
  line is followed and say nothing about what the same choice costs elsewhere.
- The weights in the measurements are the arena's hand-fit scorer alone. The bots' reading of the play is not
  included, so neither the floors nor their calibration are the bot's own.
- The joint step is greedy. Ceiling minus floor bounds what an exact joint search could add.
- Table use above the frontier for cell sets and named cards (section 3.5) is unmeasured.
- Defender-side bounds that read the cells: not written.
- Refutation-driven naming and segment cells: not built.
- A defender's own conditional lines ("we beat it if partner holds X") are a different game: two hands that cannot
  see each other. Not covered.
