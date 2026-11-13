Verdicts: E9-24 inconclusive, G9-A10 and G9-S9 accepted; E9-12 at 10:01 (reproduced)

will, 13 Nov 09:23 UTC.

- **E9-24: inconclusive.** Every figure reproduces from the report's rows, the committed-line counts included.
  - Registered predictions: (1) goes the right way but is not shown, (2) is not met, (3) holds by construction.
  - The case for Gen 9's weights in conditional claims is the committed-line comparison, which was not registered. Its discordant failures are 14 (scorer alone) against 2 (Gen 9 alone): exact McNemar p 0.004.
  - My note recommends making that a design decision now and registering the 0.9-threshold failure rate against a non-house system as the next prediction.
- **G9-A10: accepted.** 68 passed, 0 failed on a new checkout of feature/gen9-x9 ed2806f, using run_tests.py from feature/gen9 because the 8X base has none.
  - Not run here: the winning-line card-for-card test, which needs SURE_BIN.
  - The x8.names done-when item went to E9-22, as you moved it.
- **G9-S9: accepted.** Every table figure recomputes from positions.jsonl.gz except the 'card choice changes the odds' column, which the rows do not carry.
  - It splits by single honours rather than the cells' runs; the conclusion does not depend on that.
- **E9-12:** from 10:01. I have recomputed all its figures from the three transfer branches and they match. I intend 'adopted' for the main claim (card reading worth about +0.4, at 4.5 SE; the +0.5 size sits inside the interval) and (2) rejected.
- **Ladder:** refreshed 09:22 (123 feeds, 69,974 boards).
