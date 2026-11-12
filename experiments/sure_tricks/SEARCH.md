# Sure-trick search in C++ above a resident ending table

`sure.cpp` is the pooled-defender game of README section 5 (what North-South can guarantee against every split of the unseen cards, given hand sizes and show-outs), written for speed and checked against `sure.py`. One thread. All timings are from a shared 2-core VM, best of 3 runs unless stated; node and probe counts are deterministic.

## Search

- Yes/no question per search: can North-South guarantee `need` more tricks. `--need N` asks it once per legal card ("does this card guarantee the contract"); without it every card gets its exact value.
- Transposition table at trick boundaries. Key: who holds each remaining card of each suit in rank order (North, South, unseen), show-outs, leader, trump. Stores lower and upper bounds and the best card. The value depends only on the key, so entries stay valid across decisions and deals and the table never needs clearing.
- At a trick boundary with K cards left (`--front K`) the search reads the ending table instead of searching. The table key is the same information made canonical under suit permutation and the half-turn of the table.
- Sure-winner bounds for both sides, tried before a table read and before a search.
- Touching cards: declarer plays one card per run. A defender plays one per run when partner has already played, when partner is known void in the suit, or when the card is a plain discard; otherwise both ends of the run (lowest only is unsound, see README section 5).
- Move order: stored best card first, then winners and long suits on lead, cheapest winner or lowest when following.

## The table is simulated

No table has been built. The stand-in is a hash map filled on first use by the same search run to the end of the hand. With `--warm` the map is filled in an untimed first pass and the timed pass starts from an empty transposition table. With `--mem 2.5` every table read also reads one byte of a real 2.5 GB array at a hashed address, with the CPU caches flushed before the timed pass, so the cost of reaching into a table of that size is in the figures. Not in the figures: the index function a real table needs (position to slot). The hash-map lookup stands in for it; its real cost is unknown. For the time split further down the values themselves are read from an array (`--cells`), with no hash map in the timed pass.

## Checks

Against `sure.py` on random endings dense in touching cards with random show-outs (`check_cpp.py`):

- 3-card endings, 600 trials, default flags: 0 mismatches
- 4-card endings, 1500 trials, default flags: 0 mismatches
- 4-card endings, 1500 trials, flags `--nobounds --noorder`: 0 mismatches
- 5-card endings, 250 trials, default flags: 0 mismatches
- 5-card endings, 250 trials, flags `--front 4`: 0 mismatches
- 6-card endings, 30 trials, flags `--front 4`: 0 mismatches
- 6-card endings, 30 trials, flags `--front 5`: 0 mismatches
- 4-card endings, 1500 trials, default flags: 0 mismatches
- 5-card endings, 250 trials, flags `--front 4`: 0 mismatches
- 5-card endings, 250 trials, flags `--front 4 --warm --cells 0.01`: 0 mismatches
- 5-card endings, 250 trials, flags `--front 4 --warm --replay`: 0 mismatches
- 6-card endings, 30 trials, flags `--front 4 --warm --cells 0.01 --huge`: 0 mismatches

Against the Python results already reported for the test-set positions (`check_cpp_positions.py`):

- A6 7 cards: Python 30.8 s, C++ 2.3 ms above a 4-card table; per-card values agree
- A6 8 cards: Python 182.1 s, C++ 11.1 ms above a 4-card table; per-card values agree
- B6 8 cards: Python 128.4 s, C++ 5.0 ms above a 4-card table; per-card values agree
- S6 7 cards: Python 106.7 s, C++ 5.4 ms above a 4-card table; per-card values agree
- positions compared: 4, differing: 0

## Timings: 6, 7 and 8 cards left

Positions are the test-set deals after the first tricks of the sound line. Milliseconds of search.

| Position | Contract, 4-card table | All cards, 4-card table | Contract, no table | All cards, no table | Contract, 5-card table |
| --- | --- | --- | --- | --- | --- |
| A6, 6 cards | 0.2 | 0.1 | 0.5 | 0.5 |  |
| A6, 7 cards | 1.2 | 1.5 | 7.1 | 8.0 | 0.3 |
| B6, 7 cards | 0.4 | 1.2 | 1.3 | 3.9 | 0.2 |
| S6, 7 cards | 2.5 | 4.0 | 8.6 | 11 | 0.6 |
| A6, 8 cards | 8.0 | 11 | 27 | 31 | 2.4 |
| B6, 8 cards | 1.6 | 5.7 | 4.6 | 13 | 0.6 |
| S6, 8 cards | 7.6 | 12 | 25 | 36 | 2.6 |

Nodes above the table and table reads, contract question with the 4-card table: A6 6 cards 216 nodes, 258 reads; A6 7 cards 4,407 nodes, 3,447 reads; B6 7 cards 1,192 nodes, 681 reads; S6 7 cards 11,095 nodes, 6,748 reads; A6 8 cards 35,816 nodes, 26,251 reads; B6 8 cards 6,253 nodes, 2,660 reads; S6 8 cards 35,184 nodes, 16,960 reads.

## Timings: 9 to 11 cards left

Contract question. Milliseconds of search. Best of 2 with the table, single run without.

| Position | 4-card table | No table | Nodes above table | Table reads |
| --- | --- | --- | --- | --- |
| A4, 9 cards | 42 | 84 | 239,155 | 117,962 |
| A6, 9 cards | 96 | 243 | 412,750 | 241,404 |
| B6, 9 cards | 4.0 | 8.8 | 21,757 | 7,764 |
| S6, 9 cards | 34 | 104 | 154,649 | 61,824 |
| A4, 10 cards | 88 | not run | 466,042 | 150,562 |
| A6, 10 cards | 334 | 545 | 1,409,035 | 554,730 |
| B6, 10 cards | 27 | not run | 177,686 | 44,933 |
| S6, 10 cards | 114 | 222 | 557,794 | 155,133 |
| A4, 11 cards | 72 | not run | 391,331 | 128,716 |
| A6, 11 cards | 157 | not run | 972,666 | 254,631 |
| B6, 11 cards | 95 | not run | 650,850 | 126,778 |
| S6, 11 cards | 104 | not run | 498,188 | 136,395 |

What the table buys at 8 cards: the 4-card table makes the contract question 3.0 to 3.4 times faster than no table, and a 5-card table (simulated the same way) a further 2.4 to 3.3 times. At 9 and 10 cards the 4-card table gives 1.6 to 3.0 times.

## What moved the node count

Contract question, 4-card table. Nodes above the table.

| Position | Final | no move ordering | no sure-winner bounds | history heuristic added |
| --- | --- | --- | --- | --- |
| A6, 8 cards | 35,816 | 83,286 | 36,964 | 45,523 |
| B6, 8 cards | 6,253 | 13,402 | 6,469 | 6,515 |
| S6, 8 cards | 35,184 | 63,801 | 51,987 | 39,659 |
| A6, 9 cards | 412,750 | 1,414,263 | 431,343 | 435,581 |

Move ordering is the main factor. The history heuristic made things worse and is off (`--hist` turns it on). One card per run on plain discards cut nodes by 9 to 19 percent on these four positions (44,258 to 35,816 on A6 at 8 cards). Trying the bounds before the table read cut reads by 10 to 30 percent on the four positions measured. Transposition-table size from 2^16 to 2^22 entries made no measurable difference at 8 and 9 cards (three positions); the default is 2^20.

Reaching into real memory: A6 8 cards 6.1 ms without the array read, 8.0 ms with it; A6 9 cards 69 ms without the array read, 93 ms with it; S6 8 cards 5.6 ms without the array read, 7.5 ms with it. Standard 4 KB pages; huge pages not tried. Hashed addresses are the worst case for locality.

Where the nodes are: 73 to 80 percent of the nodes above the table are in the last trick before it (5 cards left) on the three positions counted (A6 at 8 and 9 cards, S6 at 9); `--stats` prints the count by depth. Keeping the transposition table from one decision to the next in the same deal cut the next decision's nodes by 20 to 30 percent on the three deals tried (all-card values, 8 then 7 cards).

## Where the time goes: lookups against the tree above the table

The same search run four ways, interleaved over 8 rounds, minimum taken (`split.py`). Contract question, 4-card table, milliseconds.

- Free lookups (`--replay`): the table's answers are returned in recorded order, with no key computed and nothing read. What is left is the tree above the table.
- In cache (`--cells 0.002 --noflush`): values read from a 2 MB table that stays in cache. Adds the key computation.
- Cold (`--cells 2.5`): values read from a 2.5 GB array at a hashed slot, 4 KB pages, the touched cache lines flushed before timing. Adds the wait on memory.
- Cold on 2 MB pages (`--cells 2.5 --huge`).

| Position | Lookups | Free | In cache | Cold | Cold, 2 MB pages | Tree | Key | Memory |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A6, 8 cards | 26,251 | 4.2 | 6.3 | 7.7 | 6.9 | 55% | 26% | 19% |
| S6, 8 cards | 16,960 | 4.4 | 5.7 | 7.2 | 6.2 | 61% | 19% | 21% |
| B6, 8 cards | 2,660 | 0.7 | 1.0 | 1.3 | 1.0 | 56% | 20% | 24% |
| A6, 9 cards | 241,404 | 51 | 66 | 86 | 83 | 59% | 18% | 23% |
| S6, 9 cards | 61,824 | 18 | 25 | 29 | 26 | 62% | 24% | 14% |
| A6, 10 cards | 554,730 | 176 | 220 | 268 | 240 | 66% | 17% | 18% |
| S6, 10 cards | 155,133 | 65 | 77 | 96 | 86 | 68% | 13% | 20% |

Tree, Key and Memory are shares of the Cold column. The tree above the table is 55 to 68 percent of the time, the key computation 13 to 26 percent (65 to 110 ns a lookup) and the wait on memory 14 to 24 percent. With free lookups the search would be 1.5 to 1.8 times faster; that is the most any work on the index or the read can gain. 2 MB pages for the table save 4 to 20 percent of the total.

Table size (cold, 4 KB pages, 6 rounds, minimum, milliseconds):

| Position | 0.03 GB | 0.25 GB | 1.07 GB | 1.75 GB | 2.5 GB | 3.09 GB |
| --- | --- | --- | --- | --- | --- | --- |
| A6, 8 cards | 6.9 | 7.4 | 7.5 | 7.9 | 7.7 | 7.6 |
| S6, 8 cards | 6.6 | 6.6 | 7.8 | 7.5 | 7.0 | 7.1 |
| A6, 9 cards | 74 | 77 | 84 | 86 | 85 | 88 |
| S6, 9 cards | 26 | 28 | 29 | 30 | 30 | 31 |

1.07 GB (whole shapes), 1.75 GB (show-outs) and 3.09 GB (mixed) are within the run-to-run spread of each other. A 0.03 GB table is 7 to 13 percent faster than a 2.5 GB one. 2 MB pages for the transposition table made no measurable difference to the tree part (A6 8 cards 4.8 against 4.3 ms; S6 8 cards 4.2 against 4.2 ms; A6 9 cards 52 against 52 ms; S6 9 cards 19 against 18 ms).

Limits of this split. The key is the stand-in key (canonical suit order, then a hash); a real index swaps the hash for a ranking step and has not been written or timed. Hashed slots are the worst case for memory; a real index would put related endings near each other. The machine is an x86 VM with 4 KB pages and a large shared L3; Apple silicon has 16 KB pages and different caches.

## Building the 4-card table

Not built. `TABLE_BUILD.md` is the build specification, for the table that holds unknown-or-exact knowledge per suit (the mixed column below; 7,457,413,672 entries exactly). In outline:

- An index function, position plus knowledge state to slot. With suits sorted so that permutations share a slot the table is the size given below; without the suit symmetry it is about 9 times larger.
- A builder that walks the entries in index order, solves each and packs 3 bits. Bottom-up: the 3-card table first (41,915,724 entries), then each 4-card entry is one trick of search reading the 3-card table.
- Compute. Per entry, measured on 200,000 random entries (`build_cost.py`): from scratch 31.7 µs (222 nodes, 0 lookups); from the 3-card table 11.2 µs (33 nodes, 11 lookups). For the specified table (7,457,413,672 entries) that is 23 core-hours from the 3-card table or 66 from scratch, if an entry with shape knowledge costs the same, which is unmeasured. An earlier run of the same measurement gave 10.3 and 29.3 µs. The 3-card table here is the stand-in hash map.
- Checks: a sample of entries against `sure.py` and against from-scratch solves.
- At play time: map the file into memory and replace the stand-in lookup with index plus read.

## Table sizes

`table_size.py`, `table_size_shapes.py`. Positions: each remaining card is North's, South's or unseen, relative rank only, up to suit permutation, two leader classes, notrump and trump. Each position is then multiplied by its knowledge states.

| Cards | Positions | Show-outs only | Whole shapes only | Mixed |
| --- | --- | --- | --- | --- |
| 3 | 4.02e+06 | ×9.1, 3.7e+07 entries, 0.01 GB | ×4.8, 1.9e+07 entries, 0.00 GB | ×12.5, 5.0e+07 entries, 0.01 GB |
| 4 | 3.72e+08 | ×12.5, 4.7e+09 entries, 1.75 GB | ×7.7, 2.9e+09 entries, 1.07 GB | ×22.2, 8.2e+09 entries, 3.09 GB |
| 5 | 2.87e+10 | ×16.4, 4.7e+11 entries, 176 GB | ×12.5, 3.6e+11 entries, 134 GB | ×38.1, 1.1e+12 entries, 409 GB |

- Show-outs only: each suit with unseen cards is free, or all East's, or all West's. States that imply one another are counted once (counted separately the 4-card figure is 6.6e+09 entries, 2.5 GB, the number quoted earlier).
- Whole shapes only: East's length in every suit is known. This answers "what is guaranteed if East is exactly this shape". It does not give the value when the shape is unknown: the minimum over shapes is only an upper bound on it, because different shapes can need different lines.
- Mixed: each suit is either unknown or known exactly. Contains both of the others.
- Sizes at 3 bits an entry (2 bits for 3 cards). Build time is unmeasured.
- These are estimates: the knowledge multiplier was counted on ordered suits and applied to the symmetry-reduced position count, and a trump suit with no cards left is counted apart from notrump. The reference index (`endtable_ref.py`) counts the mixed table exactly: 426, 168,458, 41,915,724, 7,457,413,672 entries at 1 to 4 cards, 2.80 GB at 4 cards, 10 percent below the estimate above.

## Not done

- The table itself and its index function. The batch build has not been written or timed.
- Shape constraints and pinned cards in the C++ solver (it has hand sizes and show-outs only). `sure.py` has pinned cards but no shape constraint.
- Matching transposition entries on the cards that mattered rather than all cards (what DDS does), and splitting the legal cards across threads. Neither is implemented; their gain here is unknown.
- The rule "a card that guarantees the contract comes first" (`surebot.py`) still calls the Python search. It has not been rerun on the C++ search.
- Timings cover four deals, all spade contracts, positions on the sound line only.

## Run

```
g++ -O2 -march=native -std=c++17 -o sure_cpp sure.cpp
python check_cpp.py 5 250 --front 4            # against sure.py
python runpos.py A6_8,S6_8 --contract --front 4 --warm --mem 2.5
python split.py A6_8,S6_8 8 "free=--replay" "cache=--cells 0.002 --noflush" "cold4k=--cells 2.5" "coldhuge=--cells 2.5 --huge"
python build_cost.py 4 200000
python bench_cpp.py 6,7,8 --front 4 --contract  # needs the repo (SDB_ROOT) for Board
```

Input to `sure_cpp`, one position per line: `trump leader hN hS pool cE cW vE vW [cards already played to the trick]`. Trump 0-3 = S, H, D, C, 4 = notrump; leader 0-3 = N, E, S, W; hands and pool as hex masks with card = 13 × suit + rank (2 = 0 ... A = 12); cE, cW the defenders' hand sizes; vE, vW bit masks of suits shown out of. `csure.py` builds the line from a `sure.Sure` object.
