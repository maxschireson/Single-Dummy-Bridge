# E9-12: reading a foreign system by its card, at the table (final boards; written up by g9, 13 November 2026)

Gen 9 experiment E9-12 (owner bill; `team/gen9:experiments/E9-12.md`). Bill's lease expired at 08:02 UTC with the
three box jobs finished and no result written; g9 writes the result from the jobs' own records and another lead gives
the verdict.

**Jobs** (azure4, source `feature/gen9-bidding-cards` at `ea550d3`, `scripts/gen9_match.py`, bots
`configs/gen9-bidding-bots.json`, the same 1,200 fresh deals with seed 9121, auctions from the precision book
`reports/gen9-e9-12-2026-11-12/book-precision-9121.json.gz`: the rule bidder's precision settings at all four seats).
Records: `results.jsonl` on `transfer/gen9-e9-12-{c,u,x}-azure4-20261113`. Played, common auctions, fork-free.

| Pair | Boards | IMPs a board (candidate's side) | Won | Lost |
| --- | ---: | --- | ---: | ---: |
| `9c-32` (reads the auction through the declared card `rb-precision`) against `8p-32` (the house scorer) | 1,200 | +0.383 +- 0.085 | 277 | 165 |
| `9x-32` (reads it by replaying the rule bidder) against `8p-32` | 1,200 | +0.302 +- 0.082 | 269 | 172 |
| `9u-32` (does not read the auction) against `8p-32` | 600 | -0.010 +- 0.126 | 112 | 137 |

Paired by deal: card minus no reading +0.413 +- 0.137 (600 shared deals); replay minus no reading +0.393 +- 0.161
(600); replay minus card -0.081 +- 0.103 (1,200).

**Predictions as registered.** (1) The card beats the scorer by +0.5 IMPs a board or more: the gain is +0.383 +- 0.085
(4.5 SE above zero; its 95% interval, 0.22 to 0.55, holds 0.5). Positive and large, short of the stated size.
(2) Replay adds to the card: -0.081 +- 0.103. Not met. Slice: not reading the auction at all scores the same as
misreading it with the scorer (-0.010), so the gain is from reading by the card, not from stopping the misreading.
