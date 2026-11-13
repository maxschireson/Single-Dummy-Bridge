# Spec: does acting on the claim finder gain? A fork test on the changed decisions

**Status: spec, not run.** Written by the plan session on 13 November 2026 (01:55 UTC) for x8 (the 8X engine), at
Max's request. Max (01:42 UTC): act on claims for contracts that are not undoubled partscores, "small gain but also
feels right on principle".

## The question

When the declaring side has a card that guarantees the contract (`sure_cpp`: against every split of the unseen cards
consistent with hard knowledge, and every defence) and the bot would play a card that does not, what does playing a
guaranteeing card instead gain, in IMPs, by contract class?

## What is known

| Source | Result |
| --- | --- |
| Strategy-fusion session, one Gen 8 feed (1,052 boards, 2,656 tables), offline, from 9 cards left | 298 tables played off a guarantee; 18 went down (134 IMPs). Always taking the best-rated guaranteeing card, overtricks priced from the bot's own estimates: about +14 IMPs on undoubled partscores (122 tables), about +70 on games, slams and doubled contracts (176 tables): about 0.03 IMPs per table declared |
| The same, 10 cards left (600-table sample) | 32 tables played off a guarantee, 1 down (13 IMPs); net about +8 IMPs |
| `match6` (plan): claims at the root, tricks 7 to 12 only, all contracts, against the same bot without them, 929 deals | +0.001 +- 0.023 IMPs a board: cannot resolve 0.03. Ran with the tie bug below |
| `match4` (plan): claims also inside the playouts | -0.092 +- 0.042: inside a playout a settled contract stopped the search, hiding the finesses and guesses that decide over- and undertricks. Do not use claims inside rollouts except as a floor (x8's design) |

**The tie bug** (fixed in `983aa39`, `bridge_harness/plan_player.py`): when the search's own card guaranteed the
contract but was rated exactly level with cards that did not, the tie-break could still choose one of those. Ties were
14 of the 31 misses at 10 cards, but only 2 of the 18 tables that went down from 9 cards.

## Design

A whole match spends its variance on every board; this measures only the decisions the rule changes.

1. **Decisions.** Recorded episodes of the bot under test (Gen 8 feeds; later 8X's own), depth-0 tables. Replay each
   table; at every declaring-side decision from trick 4 (10 cards left), ask the claim finder from the declaring side's
   view (`bridge_harness/claims.py`: `verdict(o, exact=False)` before trick 7, the contract question; `verdict(o)` from
   trick 7). A **changed decision**: some legal card guarantees the contract and the card the bot played does not.
2. **The rule's card.** Among the guaranteeing cards, the one the bot's search rated highest (its recorded
   `estimates`), ties by the policy net (what `PlanPlayer.claim_decision` does, with the fix).
3. **Fork.** From the position, play the rule's card and continue with the same bots at all four seats
   (`bridge_harness.runner.play_table(..., prefix=history + [card])`, as `PlanPlayer.real_values` does), and play the
   bot's own card the same way with the same seed. Use the fork's fresh continuation for both branches (not the recorded
   one), so the two differ only by the card. Two or more seeds per fork if CPU allows (bots draw layouts).
4. **Score.** Each branch's declarer tricks and score; IMPs against the other table's recorded score (held fixed);
   the difference rule minus bot. Also, double dummy on the true deal after each card (does the bot's card still make
   double dummy?): an upper bound on what better defenders would punish.
5. **Only the first changed decision per table** in the main figure (later ones depend on the first). Report later
   ones separately.

## Breakdowns to report

- Contract class: undoubled partscore / games, slams, doubled. This is the decision Max wants: act outside undoubled
  partscores only, or everywhere.
- How the bot rated its card against the rule's card: higher / exactly level (the tie cases) / lower.
- Cards left at the changed decision (10, 9, 8, 7 or fewer).
- Declaring bot, and the defending bots (bot defenders seldom punish, so the gain is a lower bound).

Per fork: mean IMPs, with errors clustered by deal. Scale to IMPs per table declared = mean x forks / tables
declared, to compare with the 0.03 estimate.

## Size and cost

One Gen 8 feed gives roughly 300 to 400 first changed decisions from 10 cards (scaled from the counts above). Each fork
is two continuations of about 5 to 9 tricks with the real bots: roughly 10 to 20 CPU seconds a fork, so about 1 to 2
CPU hours a feed, 10 to 15 minutes on an 8-core box. Two or three feeds give about 1,000 forks.

Claim finder cost by trick (plan's measurement, 150 hands, sandbox CPU, `--keep`): each card's guarantee averages
3.2 s at trick 4 (99th percentile 76 s), 0.16 s at trick 5, 13 ms at trick 6, under 2 ms from trick 7; the contract
question averages 0.12 s at trick 4 (99th 3.3 s), 12 ms at trick 5, 3 ms at trick 6. So ask only the contract question
before trick 7, and cap nodes at trick 4.

## Optional second part: defenders who hand declarer a guarantee

The strategy-fusion session's defender scan (the same feed, 8 cards left): 2,626 decisions where some card hands
declarer a guaranteed line and another does not; the bot played one that does in 278 (11%); in 11 of 270 tables a safe
card would have beaten the contract double dummy (99 IMPs at one down each). The same fork design measures the other
259 (declarer still makes double dummy after the safe card, but loses his guess): fork the safe card against the
played card with the same bots.

## Records

Write every fork (position, both cards, both continuations' plays, results, the claim finder's answers) so the rows can
also train the rollout net: the claim finder's per-card guarantees are exact labels (the claim log's format:
`scripts/claim_log.py`, decision key `claim`).
