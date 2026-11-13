# The SiD loop: a student of the line finder, a tree over the student, and self-play

Status: specification, 13 November 2026. Nothing in this document is built or adopted. Written to be implemented
without access to the conversation that produced it. Branch `research/sid-selfplay-loop-20261113`, stacked on
`research/conditional-claims-20261113` (`baa062c`).

"SiD" here is the line finder: the conditional-claims solver in [`../sure_tricks/cells/`](../sure_tricks/cells/README.md)
(`cells.cpp`, `pipeline.py`, [design](../sure_tricks/cells/DESIGN.md)), with the outright claim finder `sure_cpp` as
its cheapest question.

## 1. What Max asked for

Max, 13 November 2026, 06:31 and 06:35 UTC:

> What about a student teacher model: 1. Train a net to imitate SiD 2. Minimax over net-approximate SiD 3. Maybe
> that produces better than SiD; train a net to imitate that

> Have it play itself. I want to eventually build a bot that beats human experts.

Earlier in the same conversation: SiD should value a position as an average over the layouts the actor thinks
possible; a tree a few plies deep should see where the play lands after the other seats reply, each seat deciding
from what it knows; that is where the other seats' mistakes enter; and it should be free of strategy fusion.

What this document turns that into:

1. **Labels.** Exact SiD answers on the true deal of recorded decisions (Part A).
2. **Student.** The rollout net with heads that predict those answers from one seat's view (Part B).
3. **Tree.** In the 8X engine, own-side cards maximised per information state, the other seats played by the net
   from their own views (Part C). The exact solver stays at the root as the proof (Part D).
4. **Loop.** The tree bot plays a population that includes its own earlier rounds; its games are labelled and the
   next student is trained on them (Part E).
5. **Yardsticks** the loop never trains on (section 10).

Not in scope: bidding, the opening lead, carding agreements and the reading of other pairs' cards (Gen 9), the
arena's population management beyond the interface in section 9, and any change to the solver itself.

## 2. Terms

- **Cell, certified set, floor, ceiling.** As `cells/DESIGN.md` section 1. The floor of a card is the weight of a
  set of cells that one line starting with it wins against every defence. The ceiling adds up cells taken one at a
  time and is fused over cells.
- **Outright.** Every shape in one set: the card guarantees the target against every split. This is `sure_cpp`'s
  answer.
- **Target.** A number of tricks for the declaring side: the contract (j = 0), one fewer (j = -1), one more
  (j = +1). `need_j` = contract level + 6 + j - tricks the declaring side has won.
- **View.** What one seat has seen, as `bridge_harness.gen7_net.encode(o)` makes it from that seat's Observation.
  It is the capability boundary: no hidden card.
- **True layout.** The hidden hands of a row's deal. A label, never an input (`AGENTS.md`).
- **Row.** One decision of one seat, recorded or simulated.
- **Own side** of a deciding seat. Declarer or dummy to play: both declaring hands (one mind sees both). A
  defender to play: that defender alone. Partner is another seat with its own view.
- **Round.** Play, label, train, gate. Student `S_0` is trained on existing records, `S_n` after round n's play.

## 3. What is already measured

Everything the design leans on. "Makes" are contracts made. Errors are one standard error.

| Fact | Figure | Source |
| --- | --- | --- |
| SiD, shape level, one thread, no ending table, no outright claim: mean / median / 99th | 117 / 39 / 1,136 ms at 8 cards; 17 / 6 / 139 ms at 7 | `cells/README.md` 2 |
| Nodes per extra card | about 6 times | `cells/README.md` 6 |
| Mean nodes, claims included (per-shape searches + joint step) | 6 cards 15k; 7 cards 99k; 8 cards 621k; 9 cards 4,445k (about 0.5 s at 120 ns a node) | `cells/README.md` 6 |
| Three targets against the contract alone, 8 cards | 445k + 717k nodes: 2.6 times | `cells/README.md` 8 |
| Some card guarantees the contract outright | 44.6% of 8-card positions, 53.0% at 7 | `cells/README.md` 2 |
| No outright claim: best floor, mean; share at 0.9 or more | 0.356 and 17.8% at 8 cards; 0.324 and 15.9% at 7 | `cells/README.md` 2 |
| Scorer weights overstate the certified probability | by 4 to 15 points above 0.25 | `cells/README.md` 4 |
| Choosing by floor alone, against double dummy with the floor as tiebreak | -8.5 +- 3.2 makes over 803 positions at 8 cards; -1.2 +- 2.3 over 660 at 7 | `cells/README.md` 8 |
| The bot's card, by what the true layout was for it, 8 cards | inside its certified set: made 96.0%; double-dummy making, not certified: 82.1%; not double-dummy making: 4.7% | `cells/README.md` 8 |
| Tables with a sure make at 8 or 7 cards that went down | 32 of 1,520, counted one-sidedly | `cells/README.md` 7 |
| Knowing every card's real expectation, tricks 7 to 12, Gen 6 among Gen 6 | 0.07 +- 0.01 tricks a side | plan-leverage report, Answers |
| The bot simulating itself from trick 7 (the late rule) | 0.043 +- 0.012 tricks a side; played +0.175 +- 0.035 IMPs a board on Gen 7.1 and +0.198 +- 0.033 on Gen 8's card play, at about six times the CPU | plan-leverage report 6 |
| The claim finder replacing the simulated declarer's play | -0.092 +- 0.042 IMPs a board, paired | plan-leverage report 6 |
| Flooring a rollout's result at a guaranteed contract instead | takes a third of the loss of rollouts alone away | `docs/x8_bot.md`, Calibration |
| Net rollouts alone, tricks 7 to 12, on the calibration pairs | v4.1 top card -0.274 +- 0.058; v4.1 sampled -0.159 +- 0.031; v1 ft sampled -0.126 +- 0.028 tricks a side | `docs/x8_bot.md`, Calibration |
| Defender's hand-over rule on the Gen 8 feeds | +0.225 +- 0.097 IMPs a decision (674); games, slams, doubled +0.535 +- 0.198; undoubled partscores -0.035 +- 0.061 | `docs/x8_bot.md` |
| Policy v4.1: an equal-best card first / in top 2 / in top 3 | 91.1% / 97.3% / 99.0% | v4.1 `final_eval.txt` |
| Policy v4.1: cards kept to probability 0.98 / 0.90 / 0.90 with at most two | 2.74 / 2.04 / 1.66 (the last keeps an equal-best card 96.9%, the card played 92.0%) | v4.1 model README |
| A head fitted on fork outcomes | explains 7% of what real play adds to double dummy, 2% at close decisions (77,000 forks) | plan-leverage report 4 |
| Reading gains | measured for a bot read by a copy of itself; the report says they are not there against BEN | plan-leverage report, Limits |
| Rollout net v2's stated limit | "Targets better than the bot (...the claim finder's per-card guarantees) are not in v2" | `training/rollout-net-v2-20261113/README.md` |
| 8X's stated gap | branching inside rollouts, own side maximised per information state, "is not built" | `docs/x8_bot.md`, Not done |

Two readings that shape the design:

- The exact floor is a proof and a poor evaluator on its own. Uncertified layouts still made 82% when double-dummy
  making, and the floor counts them as nothing. So the floor constrains and informs; it does not decide alone.
- Replacing a simulated player's cards with guaranteed-tricks play lost the gain; flooring the result while the
  simulated play continues kept it. Over- and undertricks carry much of the IMP gain late in the hand. So the loop
  never substitutes solver cards for a simulated seat's play, and labels cover three targets.

## 4. Overview

```
recorded games
  -> Part A: exact SiD on the true deal                 -> labels
  -> Part B: the rollout net plus heads, trained on them -> student S_n
  -> Part C: the tree in the 8X engine, S_n inside it
     Part D: exact SiD at the root (the proof)
  -> Part E: the tree bot plays a population that includes earlier rounds
  -> new recorded games -> Part A ...
```

SiD plays the part an endgame table plays for a chess engine: exact where it reaches, and the source of exact
training targets. The student carries its judgments to places it cannot reach: the many leaves of a tree at 7 to 9
cards, and positions with more cards than the solver can afford. Each round's policy head is trained on the cards the previous round's tree chose, so the
other seats in round n's tree play as round n-1's searcher would from their own views. That is how the loop gains a
level of "what he thinks I think" a round without nesting solver calls.

Build on the branch that carries the 8X engine when work starts (today `feature/gen8x-rollout-bot-20261113` at
`1a779a9`; the trainer and dataset builder of rollout net v2 are on `research/plan-leverage-g8-20261112` at
`b54d6ca`).

## 5. Part A: labels from the exact solver

### 5.1 Rows

Every decision `scripts/gen7_build_dataset.py --policy-only` keeps (more than one legal card, its `SKIP` kinds left
out) in which the actor holds `K_A` or fewer cards. Start with `K_A` = 8. Section 11 has the cost of 9.

For each target j in (-1, 0, +1): if `need_j` <= 0 every label of that target is 1; if `need_j` exceeds the tricks
left every label is 0; neither needs a search. Otherwise the labels below.

Answers are per run of touching cards (`pipeline.runs_of`) and copied to every card of the run.

### 5.2 Declaring-side rows (declarer or dummy to play)

The position is the declaring side's own view, turned so that it sits North-South, as `x8_claims.root_line` and
`cells/arena_positions.py` build it. Shape level only (`named` = 0) in the first version.

| Label | Per (card, target) | How |
| --- | --- | --- |
| `guar` | 1 if the card guarantees the target outright | `Level.outright()` |
| `single` | 1 if the card wins the true layout's cell taken alone | `Level.singles()`, read at `Level.cell_index(true East hand)` |
| `cert` | 1 if the true layout's cell is in the card's certified set | `Level.floors(key, must=every run)`, then membership |
| `floor`, `ceil` | the card's floor and ceiling under the weights | the same calls |

- `guar` and `single` do not depend on any weights. `cert`, `floor` and `ceil` do: which line a card's set
  follows is chosen heaviest cell first.
- Weights, recorded per row as `w_src`:
  - `scorer`: the hand-fit scorer from the auction, through `cells/belief.py`. This is what `cells/README.md`
    measured, and the only choice for records that carry no layouts.
  - `bot`: the deciding bot's own layout list and weights (the `x8` capture at level 2, or the root's recorded
    answers of Part D). Use it for every row the loop's own bots produce.
- Cells are taken heaviest first to 99% of the weight, as `DESIGN.md` section 4, step 1. A true layout outside
  them has `cert` = 0.
- `must` is every run, so that every card has a set. If the joint steps for every run cost too much at 8 and 9
  cards, restrict `must` to the card played and the two highest ceilings, mask the rest, and report the masked
  share.
- A question that reaches the node cap (20 million, as the study) leaves its labels masked.

### 5.3 Defender rows

For each run of the defender's legal cards x and each target, on the true deal: the position once x is played, as
declarer sees it (`x8_claims.after_card(o, world, x)` with `world` the true hands; it needs a `need` argument
added for j other than 0).

| Label | Per (card, target) | How |
| --- | --- | --- |
| `guar` | 1 if the declaring side then holds a guaranteed line | `x8_claims.holds(answer, declaring_next)`; states `made` and `lost` give 1 and 0. For j = 0 this is the hand-over the 8X defender rule counts |
| `cert` | 1 if the true layout is in the certified set of the declaring side's best-floor card there | the shape-level pipeline at that position, `scorer` weights from the declaring side's view; only where the declaring side plays next, masked otherwise |

`single` is not defined for defender rows.

### 5.4 Storage

A sidecar file per episode file, aligned to the builder's rows by (table key in `unique_tables`, table index, action
index). Arrays: `guar`, `single`, `cert` as int8 [rows, 52, 3] with -1 for no label; `floor`, `ceil` as float16.
A manifest per run: solver source commit and binary hash, flags (`--def ends`), node cap, `K_A`, `w_src`, scorer
hash, repo commit. The run is resumable and never recomputes an episode labelled under the same manifest. Labels
are bulk records: they go to a `transfer/` branch with the manifest, not into source.

### 5.5 Done when

- `guar` for j = 0 at declaring rows equals `sure_cpp` on the same positions (the study's cross-check: 14,623 card
  answers, 0 differences).
- Defender `guar` for j = 0 equals `Finder.handovers` on the same positions.
- On the labelled tables, every table whose declaring side played a `guar` (j = 0) card at each of its decisions
  from the first such row on made its contract (`e2e_check.py`'s invariant).
- With `w_src` = `scorer`, mean floor against the share of `cert` = 1 by floor band reproduces the table in
  `cells/README.md` 4 on the same feed.
- The cost a row by cards held, for each label, is reported from the run itself.

## 6. Part B: the student net

**Base.** Rollout net v2 (`transfer/rollout-net-v2-20261113`, `runs/w768`): the `suit` kind, 768 wide, the two bot
vectors, its four heads (card played, the search's gap, holder of each unseen card, final tricks).

**Added outputs.**

- Per card, from the decoder's last layer (`wd1`, `bd1`: 5 outputs a card today): `guar`, `cert` and `single`,
  three logits each, one per target. The row's role says whether `guar` and `cert` are a declaring side's or a
  defender's.
- From the trunk, beside `wk`: `tricks14`, 14 logits for the actor's side's final tricks.
- `gen7_net.forward` returns them and `PolicyNet.heads` exposes them. A net file without the new columns behaves
  as today, as nets without `bot_vocab` do.

**Loss.** The existing terms unchanged (`ce + 2 gap + 0.5 owner + tricks`), plus binary cross-entropy on `guar`,
`cert` and `single`, each averaged over the labelled (row, legal card, target) entries, plus cross-entropy on
`tricks14`. Start each new weight at 1.0. They are settings and unmeasured.

**Training.** `scripts/train_rollout_net.py --init` from v2, v2's recipe (768 wide, five epochs, rate 2e-3 falling by
one cosine, batch 512, AdamW, weight decay 1e-4), v2's rows plus the sidecar labels. Rows without labels train the
old heads only. No resampling or reweighting of rows by difficulty in the first version; any later weighting is a
setting and is reported. Held out as v4.1 and v2 were: boards that reached the feeds after the fetch, minus deals
the set has.

**Release.** `models/cardplay/sid-net-<n>-<date>/` with README, restore script and hashes, as the other nets.

**Done when** the report of section 10, E1, exists for `S_0`. No pass mark is fixed in advance: how well a net of
this size reproduces the solver where the top cards differ is not known.

## 7. Part C: the tree

A new stage mode `tree` in `X8Player` beside `search`, `blend` and `rollout`, built on `x8_rollout.evaluate`. It
is the rollout stage with own-side branching. Nothing is minimised on behalf of a seat that lacks the information:
the other seats' cards come from the net from their own views.

### 7.1 Rows and groups

- Rows are (root card, layout) pairs advanced in one batch, as today. Layouts and weights are the stage's own
  (`X8Player.read_layouts`).
- Each layout is put in half 0 or half 1 at the root, alternating in falling order of weight.
- At a turn of any seat outside the root's own side, the row's card comes from the net from that seat's view in
  that row (`Seats`, the stage's `seat` setting). `draw` tested better than `top` for rollouts alone.
- At a turn of the root's own side, rows are grouped by information state: the root card and every card played
  since, in order. All rows of a group share the own side's view.
- Rows are never merged. Two rows that reach the same cards by different orders are different positions.

### 7.2 Branching

At an own-side turn, a group branches when the stage has branch points left (`branches`, default 2 after the root)
and the group has at least `min_group` rows in half 0 (default 8). Every row of the group is copied once for each
candidate card (7.4) and continues with it, with the same random stream for the other seats in each copy. A group
that does not branch plays the net's card as any other seat does.

`min_group` is what keeps this free of strategy fusion in practice. A choice made in a group of one or two layouts
is a choice per layout. By arithmetic, not measurement: 256 layouts are 128 a half for each root card, and once the
two other seats have each played one of about three cards a group holds about 14. So the second branch point is
about the limit; measure group sizes before raising `branches`.

### 7.3 Values

After every row has its result:

1. Deepest groups first, the card chosen in a branched group is the one with the best weighted mean of
   `worth(result)` over its half-0 rows. Rows of that group that took another card are dropped.
2. A root card's value is the weighted mean of `worth(result)` over its surviving half-1 rows.

Choices are made on one half and values read on the other, as the late rule's bench did, so a value is not
flattered by the choices beneath it. `worth` and `objective` are the stage's, as today. Root cards are compared
as a rollout stage compares them (the race, `slack`).

### 7.4 Candidates

| Where | Rule | Why |
| --- | --- | --- |
| Root | the rollout stage's rule (`prior` 0.02, the two likeliest always, at most `cards` 4), plus the exact best-floor card when Part D gives one that is missing | a miss at the root removes a card that could be played; root breadth multiplies cost once |
| Own side below the root | runs until the net's probabilities add to `tree_mass` (0.90), at most `tree_cards` (2); plus the run with the highest predicted `cert` at j = 0 when the net has that head and it is missing | 1.66 cards and an equal-best card 96.9% of the time with v4.1; a miss here undervalues one line |
| Other seats | no cut: a card drawn from the net's probabilities | their rare cards are where their mistakes are; a 0.90 cut would drop replies under about 10% |

### 7.5 Leaves

- `leaf: rollout` (default): rows play on to trick 13 from the net with the claim floors, as rollout stages do.
- `leaf: net` (later, section 12): a row stops at the first own-side decision at or after the start of trick
  (root trick + `horizon`). The group's value is read once from the student at that view: the mean of
  `tricks14`, after raising its upper tails so that the probability of at least each target is no less than the
  best predicted `cert` for that target (a defender's `cert` bounds the other side's tails the same way).
  `objective: tricks` only. This is the literal "minimax over net-approximate SiD" and is unmeasured.

### 7.6 Unchanged

The winning-line logic (`x8.claims`), the mixing (`x8.mix`), the capture and the stage's `contracts` setting.
The tree adds to the `x8` note: per branched group its size by half, the candidates, their half-0 means and the
card chosen. `tree` joins the features `audit_features` may name, so every decision the tree changes is forked
against the card the same bot plays with the tree off.

### 7.7 Done when

- With `branches` 0 the stage gives a rollout stage's values on the same rows (test).
- On a constructed two-way guess, per-layout choice shows the fused value and the group choice does not (test).
- The calibration of section 10, E2, is run for "tree alone" beside "rollouts alone".
- Rows a second and CPU a decision are reported at tricks 7 to 12.

## 8. Part D: the exact solver in play

The proof is never replaced by a prediction.

- **Root, declaring side, outright.** As 8X today (`x8.claims.cards`): if some card guarantees the contract only
  such cards are candidates.
- **Root, declaring side, conditional.** `cells/DESIGN.md` section 6 as written: with `conditional` or fewer cards
  and no outright claim, the shape-level pipeline on the decision's own layout list; `first_floor` set where a
  layout's cell is in a card's certified set; the commitment rule at the next decision; `conditional_min` (start
  0.9) below which a floor is recorded and moves nothing; the feature name `conditional` in `audit_features`. In a
  `tree` stage the floors apply to rows exactly as in a `rollout` stage.
- **Inside rollouts and trees.** The boundary floors of `x8.claims.leaf`, unchanged. The simulated play is never
  replaced; only its result is floored.
- **Defenders.** The hand-over odds and rule as 8X has them, with `defender_cards` or fewer cards.
- **The record.** Every root where the exact solver ran writes its per-card answers, floors and certified sets
  with the layout weights used. After the deal the labeller adds the true layout's membership. Those rows are
  Part A labels with `w_src` = `bot` at no further solver cost.
- **The student's heads at the table.** Three uses, each a feature that is forked:
  1. below the root, to add a candidate (7.4);
  2. for a defender holding more cards than `defender_cards`: predicted `guar` at j = 0 as the hand-over odds,
     under the same `odds_margin` rule;
  3. as a recorded disagreement: wherever the exact solver ran, the student's `guar` and `cert` for the same cards
     are stored beside the exact answers. This is E1 measured in play.
  A predicted value is never a floor.

## 9. Part E: self-play rounds

One round:

1. **Play.** The current tree bot plays duplicate boards in the arena with capture on (level 1; level 2 on a
   sample for `w_src` = `bot` weights) and feature forks. The net is told who is playing through `x8.names`.
2. **Label.** Part A on the new boards.
3. **Train.** `S_{n+1}` from `S_n` (`--init`) on every round so far, with:
   - the card target as v2 has it (the card the bot played), using the record's `behavior_probabilities` as the
     target where a seat mixed;
   - the gap target from the tree's recorded candidate values on those cards, with a per-card mask (the trainer's
     gap mask is per row today);
   - every distinct bot (engine and net) under its own name in `bot_vocab`, as v2 does.
4. **Gate.** Section 10.
5. **Promote.** The new bot joins the population. Earlier rounds stay in it.

Rules for the population. The arena owns the mechanics; the numbers are Max's (section 13).

- A new bot does not play only its latest self. Best-responding to the latest self can cycle. A share of every
  round's boards is against earlier rounds and against bots outside the loop.
- Bridge is two partnerships, so the convergence results for two-player zero-sum self-play do not carry over.
  Convergence is checked (E3, E4), not assumed.
- Self-play teaches the net to read its own cards. Rows keep the bot names of both sides, so the reading stays
  conditional on who plays, and an unknown name reads as a generic player (v2 trains 15% of rows that way). The
  calibration of that reading against other pairs is Gen 9's work and outside this document.

## 10. Evaluation and gates

| | What | Gate |
| --- | --- | --- |
| E1 | Student against teacher, offline, on fresh boards: for each head, by cards held and role, log-loss, Brier score and a calibration table. Per decision: the exact floor of the card the student ranks first on `cert`, against the best exact floor (mean shortfall; share above 0.05). On positions where the two best exact floors differ by more than 0.05: how often the student ranks the better card first | Report only for `S_0`. From `S_1`: no worse than the previous student on the same boards |
| E2 | The calibration pairs of `docs/x8_bot.md` (tricks 7 to 12, `scripts/x8_bench.py`): rollouts alone and tree alone with the student as the rollout net | Rollouts alone above v1 ft's -0.126 +- 0.028 on the same pairs; the tree stage may decide alone only at zero or above. That ceiling is Gen 6 playing on: from round 1 build pairs from the loop's own feature forks as well |
| E3 | Played, `scripts/x8_match.py`, 1,600 fresh deals, duplicate, `--feature-forks`: against `8p-32-v41` (Gen 8's card play), against `pr75-8p-32-v41` (the late rule), against the same engine with the previous student. IMPs a board, CPU seconds a board, forks by feature and contract class (`scripts/x8_forks.py`) | Not behind the previous round's bot by more than one standard error; the comparisons with Gen 8 and the late rule are reported every round |
| E4 | Exploitability, from round 2: a bot whose rollouts simulate the frozen candidate with the candidate's own engine at the candidate's seats (as the late rule simulates Gen 7 itself), played against the candidate. The IMPs a board it wins over the mirror match is a lower bound on what an adapting opponent can take | Reported; should fall across rounds |
| E5 | Sets never trained on: the strategy-fusion test deals of `experiments/sure_tricks/README.md`; declarer problems with known solutions; recorded expert play (agreement, and where the bot's card differs, the exact verdict on the true deal) | Reported. The last two need sources from Max |

Every result is recorded as `CONTRIBUTING.md` asks: source commit, configuration, model hashes, the split, metric,
sample count, uncertainty, artifact locations, and whether the evidence is prediction, a double-dummy proxy or
played.

## 11. Cost

Labels, one thread, no ending table, from the nodes and times of `cells/README.md`. One target, declaring rows:

| Cards held | A row | A million rows |
| --- | --- | --- |
| 7 | 17 ms | about 5 core-hours |
| 8 | 117 ms | about 33 core-hours |
| 9 | about 0.5 s (from 4,445k nodes) | about 150 core-hours |

- Three targets cost about 2.6 times one (measured at 8 cards).
- Rows with fewer cards are about 6 times cheaper a card.
- Rows where a card guarantees the target outright stop at the first question.
- `must` = every run adds joint steps the study did not run for every card. Unmeasured.
- A defender row's `cert` is one pipeline per candidate card. Its `guar` is the outright question (`sure_cpp`:
  0.5 ms a decision from trick 7, plan-leverage report 6).
- The 8-card and 9-card rows are the budget. Label all rows of 7 cards or fewer and a sample at 8 (and 9, if
  chosen), by deal, not by position.

Training: v4.1's 768-wide five-epoch run took 46 minutes for 13.2 million rows on 8 cores; v2 expected about two
hours for 25 to 35 million.

The tree: rows = layouts x root cards x the product of candidates at each branch point reached. With 256 layouts,
3 root cards and two branch points of 2, at most 3,072 rows a decision before the race. Net calls a row a ply are
as a rollout stage's. Rows a second for this engine is not in any report read for this document; measure it first.

This document grants no machine. Ask on the coordination board (`box/coordination`, `BOARD.md`). Do not add or
resize a cloud instance: Max confirms the current and the proposed configuration first.

## 12. Order of work

| Step | Work | Depends on | Done when |
| --- | --- | --- | --- |
| 1 | Label builder (Part A), `K_A` = 8, `w_src` = `scorer`, on the feeds rollout net v2 used | the cells code, `sure_cpp` | 5.5 |
| 2 | Heads and trainer changes (Part B); train `S_0` | 1 | E1 report |
| 3 | E2 with `S_0` as the rollout net in the existing rollout stage | 2 | the "rollouts alone" row for `S_0` |
| 4 | Conditional claims at the root (Part D, `DESIGN.md` 6 and its order of work) | independent of 1 to 3 | its forks are priced in a played match |
| 5 | The tree stage with `leaf: rollout` (Part C) | 2 | 7.7 |
| 6 | E3 for the tree bot with `S_0` | 4, 5 | the three matches |
| 7 | Round 1 (Part E): play, label with `w_src` = `bot`, train `S_1`, gates | 6 | E1 to E3 for `S_1` |
| 8 | `leaf: net`; labels at 9 cards; the student's heads for defenders beyond `defender_cards` | 7 | each forked and priced |
| 9 | E4 and E5 | 7 | reported |

Steps 1 to 3 need no new engine code and answer the first open question: whether the solver's answers as
targets move "rollouts alone" on the calibration pairs.

## 13. Decisions left to Max

1. `K_A`: 8 cards only at first, or 9 as well (about 150 core-hours a million declaring rows for one target).
2. How many 8-card (and 9-card) rows to label in step 1.
3. The share of each round's boards against earlier rounds and outside bots, and which outside bots.
4. Whether the tree stage acts in games, slams and doubled contracts only, as the 8X stages were set after the
   partscore forks, or everywhere.
5. Whether a tree stage that passes E2 decides alone or enters as a blend at a trust.
6. The sources for E5: expert records and problem sets.
7. Which machines.

## 14. Not covered, and unknown

- Whether a net of this size reproduces the solver where the top cards differ. The fork-outcome head's result
  (7%, 2% at close decisions) was on noisy single-deal outcomes from 77,000 forks; these labels are exact and
  available in millions, so that result does not settle it.
- Whether the solver's answers as targets improve the net as a model of play at all (step 3 measures it).
- The tree's cost and its group sizes at the second branch point.
- `leaf: net`, the tail correction in it, and every loss weight: unmeasured.
- Named-card cells (`DESIGN.md` 5) as labels: later, as a second `cert` label.
- A defender's own conditional lines ("we beat it if partner holds X"): a different game, not covered, as in
  `DESIGN.md` 8.
- An ending table would cut the label cost (estimated 2.2 to 2.8 times at 8 cards for the outright and per-shape
  questions, `cells/README.md` 6); none is assumed.
- The `scorer` weights ignore the play. Labels made with them are the study's quantity, not the bot's own.
- Beating human experts is the aim and is not measured by anything here until E5 has sources.

## 15. Provenance

| Read for this document | At |
| --- | --- |
| `experiments/sure_tricks/cells/` (README, DESIGN, `pipeline.py`, `cells.cpp`, `celllib.py`) | `research/conditional-claims-20261113`, `baa062c` |
| `docs/x8_bot.md`, `bridge_harness/x8_player.py`, `x8_claims.py`, `configs/x8-bots.json` | `feature/gen8x-rollout-bot-20261113`, `1a779a9` |
| `reports/plan-leverage-2026-11-12/README.md`, `bridge_harness/gen7_net.py`, `scripts/gen7_build_dataset.py`, `scripts/train_rollout_net.py`, `training/rollout-net-v2-20261113/README.md` | `research/plan-leverage-g8-20261112`, `b54d6ca` |
| Policy v4.1 and v4 model READMEs, `training/policy-v4.1-20261112/final_eval.txt` | `transfer/gen7-policy-v4.1-20261112`, `7d1ce5e` |
| `AGENTS.md`, `CONTRIBUTING.md`, `docs/repository-map.md` | `research/conditional-claims-20261113`, `baa062c` |

No code was run for this document. Every figure in section 3 is quoted from the file named beside it; the cost
arithmetic of section 11 is from those figures.
