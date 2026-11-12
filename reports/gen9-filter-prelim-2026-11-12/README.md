# Gen 9 rule filter: preliminary reading gain (12 November 2026)

**Prediction evidence only; a preliminary version of E9-1 part 1, not its registered protocol.**
Code: `scripts/gen9_filter_eval.py` on `feature/gen9-bidding-cards`. Data: `result.json` (400 deals a
system, all four seats bid by it, 1,600 seat decisions; pool 256; seeds in the file).

For each seat s, its left-hand opponent weights s's true hand among 256 random hands from the 39
cards it cannot see. Gain = log w(true) − log mean w(pool), in nats (0 = no information). This is a
one-seat marginal with a uniform pool, not the registered E9-1 measure (512 layouts from the prior,
leader and declarer views). S = hand-fit scorer v0 (trained on Gen 5 bidder auctions). F = rule
filter with the system's own card (eps 0.05, lambda 1.5). For `rb:*` the filter reads the rule
bidder's own tables (`bridge_harness/cards/rb_meanings.py`), the exact meanings. For `house:gen5`
the card is `two-over-one`, an approximate description of the house system.

| Auctions bid by | S | F | S + F | ½S + F | wrong card, S + Fw |
| --- | ---: | ---: | ---: | ---: | ---: |
| house Gen 5 bidder (card: 2/1, approximate) | 2.18 ± .04 | 0.85 ± .05 | 1.77 ± .07 | 1.61 ± .06 | 1.32 ± .07 |
| 2/1 card | 0.61 ± .09 | 1.68 ± .04 | 0.97 ± .09 | 1.56 ± .06 | 0.20 ± .10 |
| SAYC card | 0.75 ± .08 | 1.67 ± .04 | 1.08 ± .09 | 1.60 ± .06 | 0.30 ± .10 |
| Acol card | −1.34 ± .19 | 1.65 ± .04 | −0.55 ± .17 | 0.97 ± .08 | −1.82 ± .23 |
| Precision card | −2.49 ± .23 | 1.42 ± .04 | −1.90 ± .23 | 0.18 ± .11 | −3.44 ± .28 |
| Polish Club card | −1.16 ± .18 | 1.43 ± .04 | −0.72 ± .17 | 0.72 ± .09 | −1.75 ± .23 |
| rule bidder, standard (exact tables) | 0.39 ± .09 | 1.58 ± .03 | 0.68 ± .09 | 1.38 ± .05 | −0.03 ± .10 |
| rule bidder, precision (exact tables) | −2.55 ± .23 | 1.71 ± .03 | −1.73 ± .22 | 0.37 ± .11 | −3.24 ± .28 |

Wrong card: Precision for natural systems and the house, 2/1 for the others, rule-bidder standard
and precision for each other.

What it says, within this measure:
- On systems it was not trained on, the generic scorer is worse than knowing nothing (negative gain):
  it reads a strong club, a weak no-trump or a multi-way 1C as the house would mean them.
- Adding the filter to the scorer recovers only 0.3 to 0.8 nats of gaps of 1 to 4 nats. The scorer's
  misreadings stay. Down-weighting the scorer helps a lot (½S + F), which supports handing misread
  calls to the rules instead of multiplying.
- On house auctions, a card that only approximately describes the house system costs 0.42 nats
  when multiplied in at eps 0.05, and 0.25 with eps learned per call family from 1,500 house boards.
  A filter on top of a matching profile must be limited to the calls where the profile and card
  disagree, or learn the player's ranges, not only a rate.
- A wrong card is worse than no card everywhere.
