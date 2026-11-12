# E9-12 inputs and the reading record (12 November 2026)

**Inputs** for the played boards of E9-12 (team/gen9 `experiments/E9-12.md`), and **prediction evidence**
(the reading of each bot on the very auctions it will play; no solver, no play).

- `book-precision-9121.json.gz`: 1,200 deals of gen8_match's seed 9121, all four seats bid by the rule
  bidder with its precision settings (`scripts/gen9_make_book.py --settings precision --seed 9121
  --deals 1200`); `book-standard-9122.json.gz`: 600 deals of seed 9122, standard settings. Bid with
  `bridge_harness/rule_bidder.py` sha256 f03afb2c...; no deal was passed out after a rule-bidder error.
  The box jobs (`scripts/gen9_e9_12_job.sh`, queue jobs `e9-12-*`) play these auctions.
- `reading-*.jsonl`: for every board and the two decisions of E9-1 (the opening leader before the lead,
  declarer at trick 1), the gain of the true layout over a pool of 512 drawn uniformly among layouts
  consistent with the decider's view: G = log(w(true) / sum w) - log(1/512), in nats, 0 = no information
  (9u-32's reading). Readers: S the hand-fit scorer (8p-32), F the declared card's filter alone at eps 0.05
  (9c-32), R replay of the rule bidder at eps 0.02 (9x-32 reads R on a pool drawn by S, so this is R's
  reading on a uniform pool, not exactly 9x-32's). Code: `scripts/gen9_book_reading.py`.

| Book (card) | Decision | n | S | F | R |
| --- | --- | ---: | ---: | ---: | ---: |
| precision (rb-precision) | leader | 1,200 | −9.24 ± 0.48 | 3.13 ± 0.04 | 5.51 ± 0.02 |
| | declarer | 1,200 | −1.90 ± 0.25 | 1.29 ± 0.04 | 1.75 ± 0.04 |
| | all | 2,400 | −5.57 ± 0.28 | 2.21 ± 0.03 | 3.63 ± 0.05 |
| standard (rb-standard) | leader | 600 | 1.10 ± 0.25 | 3.16 ± 0.06 | 5.52 ± 0.03 |
| | declarer | 600 | −0.19 ± 0.17 | 1.25 ± 0.05 | 1.83 ± 0.06 |
| | all | 1,200 | 0.46 ± 0.15 | 2.21 ± 0.05 | 3.67 ± 0.06 |

- On the precision auctions the scorer is 5.6 nats worse than not reading at all (9.2 for the opening
  leader): "stop misreading" is worth more than "read by the card" (+2.2 over not reading). This repeats
  E9-1 part 1 (−5.8, +2.2) on the deals that will be played.
- On the standard settings the scorer is slightly positive (+0.5), as E9-1 found (+0.52), and the card is
  still 1.75 nats better than the scorer, the replay 3.2.
- The rows carry the board index, so the played results can be joined by board: does a board's reading
  gap (F − S, R − S) predict its IMPs.
