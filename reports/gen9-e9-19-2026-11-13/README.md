# E9-19: the cheap re-scoring of different contracts (g9), 13 November 2026

Registration: `team/gen9:experiments/E9-19.md`. Background: [docs/gen9/arena-selfplay.md](../../docs/gen9/arena-selfplay.md),
section 5.4.

## Finding before the run: the arena's current pairs never bid differently

On every one of the Gen 9 cohort's first 715 boards, both tables bid the same auction. The same holds in the Gen 8
feeds for every pair among `8s-32`, `8x3-32` and `71s-32`. The reason is that all of these bots bid with the house net
(`auction_source` `systems:house-gen6|house-gen6`).

So the cohort and the arena's comparisons among current house bots measure card play only. All their variance is card
play, and only a play version of the re-scoring can reach it.

Contracts differ only where one side is:

- an older generation (`1`, `5RZ32`), or
- a foreign system (`8c-32`, the Precision rule bidder; BEN).

## Method

- **Boards.** The native boards of two Gen 8 feeds, `arena-gen8-azure1-feed` and `arena-gen8-x3-azure1-feed`, as
  published.
- **Which boards are re-scored.** Each board where the two tables' contracts differ in level, strain, doubling or
  declarer.
- **Re-scoring one table.**
  - Declarer's hand is fixed.
  - 20,000 uniform deals of the other 39 cards are weighted by the hand-fit scorer's likelihood of the three other
    seats' calls (the feeds' scorer, SHA-256 `56e6444079d1…`).
  - 64 layouts are drawn by those weights and each is solved double dummy at the opening lead.
  - Each layout is scored as the contract stood at the table.
- **The board's re-scored result** is the candidate's expected IMPs over all pairs of the two tables' layouts.
- **Other boards** keep their result.
- **Scripts.** `e919.py` and `e919_report.py`. Results: `results-*.jsonl.gz`, one line a board.
- **Bias.** The cheap version is biased by design: on a re-scored board, double-dummy play replaces both tables' real
  play. A gap in card play between the pairs therefore drops out of those boards.

## Results

The run covered 2,322 native boards. On 439 of them (19%) the two tables reached different contracts; the full table
is in `report.txt`. The two tables' recorded results were reproduced on every board.

| Boards | SD plain (IMPs) | SD re-scored | Fall | Mean plain | Mean re-scored |
| --- | ---: | ---: | ---: | ---: | ---: |
| All 2,322 | 4.65 | 4.10 | 12% | | |
| Contracts differ, 439 | 7.32 | 5.15 | 29.6% | | |
| of which a foreign system (`8c-32`), 265 | 6.78 | 5.24 | 23% | -0.97 | -1.39 |
| of which an older generation (`1`, `5RZ32`), 174 | 7.66 | 4.75 | 38% | +2.38 | +0.67 |

The means are the candidate's IMPs on those boards.

- **Prediction 1** was that the SD where contracts differ falls by at least 30%. It fell by 29.6%: **not met**, by a
  hair.
- **Prediction 2** was that pairs more than 2 SE from zero keep their sign. All 7 kept it: **met**.
- **Bias.** The means move: `8s-32` against Gen 1 goes from +2.61 to +1.71 over all its boards. On the re-scored boards
  the stronger bot's better card play drops out, as the method section says it must. `8c-32` against `71s-32` moves
  from +0.26 to -0.48.
- **Sampling.** The median effective sample of the weighted layouts was 53 a table (the smaller of the two tables). It
  was under 10 at one table of 46 boards, where the scorer reads the auction poorly (Precision auctions) and the
  re-scoring is mostly noise.

## Reading

- **Stopping rule.** The registered stopping rule applies: the SD fell by less than 30%, so this is reported and
  stopped, and the cheap version is not proposed as a screen. The unbiased version is not opened.
- **Too little to matter, and biased.** Where it applies, the cheap version cuts the SD of a whole match by about 12%
  (about 22% fewer boards for the same error). Its bias, up to 1.7 IMPs a board on the boards it touches, is larger
  than the differences ratings must resolve.
- **The cohort.** For the Gen 9 cohort and for every comparison among current house bots, it does nothing: their
  tables always bid the same. If variance reduction is pursued, it is the play version, at the trick where the two
  tables' plays part.
