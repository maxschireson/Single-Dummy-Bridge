# Sure-trick search in C++ above a resident ending table

`sure.cpp` is the pooled-defender game of README section 5 (what North-South can guarantee against every split of the unseen cards, given hand sizes and show-outs), written for speed and checked against `sure.py`. One thread. All timings are from a shared 2-core x86 VM, best of 3 runs unless stated; node and lookup counts are deterministic.

## Search

- Yes/no question per search: can North-South guarantee `need` more tricks. `--need N` asks it once per legal card ("does this card guarantee the contract"); without it every card gets its exact value.
- Transposition table at trick boundaries. Key: who holds each remaining card of each suit in rank order (North, South, unseen), show-outs, leader, trump. Stores lower and upper bounds and the best card. The value depends only on the key, so entries stay valid across decisions and deals and the table never needs clearing.
- At a trick boundary with K cards left (`--front K`) the search reads the ending table instead of searching. The stand-in table key is the same information made canonical under suit permutation and the half-turn of the table.
- Bounds tried before a table read and before a search: sure winners of the hand on lead; quick tricks using both declaring hands; top trumps for either side whoever leads.
- Touching cards: declarer plays one card per run. A defender plays one per run when partner has already played, when partner is known void in the suit, or when the card is a plain discard; otherwise both ends of the run (lowest only is unsound, see README section 5).
- Move order: stored best card first, then the two leads that last settled a node for this seat at this depth, then winners and long suits on lead, cheapest winner or lowest when following.

## The table is simulated

No table has been built (`TABLE_BUILD.md` is the specification). The stand-in is a hash map filled on first use by the same search run to the end of the hand. With `--warm` the map is filled in untimed passes and the timed pass starts from an empty transposition table. With `--cells 2.5` the timed pass reads each value from a real 2.5 GB array at a hashed slot, its cache lines flushed first, and does not touch the hash map: one dependent memory read per lookup, as with a built table. Not in the figures: the index function a real table needs (position to slot). The stand-in key and hash take its place; the real cost is unknown.

## Checks

The current build against `sure.py` on random endings dense in touching cards with random show-outs (`check_cpp.py`):

- 3-card endings, 600 trials, default flags: 0 mismatches
- 4-card endings, 1500 trials, default flags: 0 mismatches
- 4-card endings, 1500 trials, flags `--nobounds --noorder`: 0 mismatches
- 5-card endings, 250 trials, flags `--front 4`: 0 mismatches
- 5-card endings, 250 trials, default flags: 0 mismatches
- 6-card endings, 30 trials, flags `--front 4`: 0 mismatches
- 4-card endings, 600 trials, default flags: 0 mismatches  [build without BMI2]
- 5-card endings, 250 trials, flags `--front 4 --warm --cells 0.01`: 0 mismatches
- 5-card endings, 250 trials, flags `--front 4 --warm --replay`: 0 mismatches

Against the build before the second round of changes, on positions too large for the Python reference (`check_cpp_builds.py`):

- benchmark positions, contract question: 19 positions, 0 differ
- benchmark positions, every card: 11 positions, 0 differ
- random 7-card positions: 600 positions, 0 differ
- random 8-card positions: 250 positions, 0 differ
- random 9-card positions: 60 positions, 0 differ

Against the Python results already reported for the test-set positions (`check_cpp_positions.py`):

- A6 7 cards: Python 30.8 s, C++ 0.5 ms above a 4-card table; per-card values agree
- A6 8 cards: Python 182.1 s, C++ 2.5 ms above a 4-card table; per-card values agree
- B6 8 cards: Python 128.4 s, C++ 2.0 ms above a 4-card table; per-card values agree
- S6 7 cards: Python 106.7 s, C++ 1.0 ms above a 4-card table; per-card values agree
- positions compared: 4, differing: 0

## Timings: 6, 7 and 8 cards left

Positions are the test-set deals after the first tricks of the sound line. Milliseconds of search. The table columns read a cold 2.5 GB array (`--cells 2.5`).

| Position | Contract, 4-card table | All cards, 4-card table | Contract, no table | All cards, no table | Contract, 5-card table |
| --- | --- | --- | --- | --- | --- |
| A6, 6 cards | 0.0 | 0.1 | 0.1 | 0.1 |  |
| A6, 7 cards | 0.4 | 0.6 | 1.4 | 1.9 | 0.1 |
| B6, 7 cards | 0.2 | 0.7 | 0.6 | 1.7 | 0.1 |
| S6, 7 cards | 0.7 | 1.0 | 2.3 | 2.8 | 0.2 |
| A6, 8 cards | 2.1 | 2.3 | 4.8 | 6.5 | 0.8 |
| B6, 8 cards | 0.7 | 1.9 | 2.0 | 4.5 | 0.3 |
| S6, 8 cards | 2.4 | 3.2 | 6.5 | 7.9 | 0.8 |

Nodes above the table and table reads, contract question with the 4-card table: A6 6 cards 60 nodes, 20 reads; A6 7 cards 1,954 nodes, 813 reads; B6 7 cards 979 nodes, 397 reads; S6 7 cards 5,751 nodes, 1,188 reads; A6 8 cards 15,778 nodes, 3,930 reads; B6 8 cards 4,149 nodes, 1,144 reads; S6 8 cards 16,650 nodes, 3,332 reads.

## Timings: 9 to 11 cards left

Contract question. Milliseconds of search. Best of 2 with the table, single run without.

| Position | 4-card table | No table | Nodes above table | Table reads |
| --- | --- | --- | --- | --- |
| A4, 9 cards | 6.7 | 7.7 | 72,569 | 4,851 |
| A6, 9 cards | 14 | 26 | 109,157 | 24,646 |
| B6, 9 cards | 2.1 | 4.4 | 14,126 | 2,831 |
| S6, 9 cards | 9.3 | 25 | 58,288 | 13,613 |
| A4, 10 cards | 16 | 19 | 171,717 | 11,735 |
| A6, 10 cards | 55 | 94 | 408,313 | 81,986 |
| B6, 10 cards | 12 | 20 | 112,645 | 14,084 |
| S6, 10 cards | 26 | 65 | 176,412 | 35,994 |
| A4, 11 cards | 15 | not run | 138,957 | 16,151 |
| A6, 11 cards | 41 | not run | 450,536 | 58,913 |
| B6, 11 cards | 43 | not run | 371,065 | 57,786 |
| S6, 11 cards | 11 | not run | 84,959 | 15,244 |

What the table buys at 8 cards: the 4-card table makes the contract question 2.2 to 2.8 times faster than no table, and a 5-card table (simulated the same way) a further 2.3 to 2.9 times. At 9 and 10 cards the 4-card table gives 1.2 to 2.7 times.

## Second round: what was taken from DDS

Before is the build of commit `0fe1283` (first push of this directory). Contract question, values read from a cold 2.5 GB array, 8 interleaved rounds, minimum, milliseconds.

| Position | Before | Now | Speed-up | Nodes before | Nodes now | Table reads before | Table reads now |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A6, 8 cards | 8.1 | 2.0 | 4.1× | 35,816 | 15,778 | 26,251 | 3,930 |
| S6, 8 cards | 7.5 | 2.3 | 3.3× | 35,184 | 16,650 | 16,960 | 3,332 |
| B6, 8 cards | 1.3 | 0.7 | 2.0× | 6,253 | 4,149 | 2,660 | 1,144 |
| A6, 9 cards | 86 | 13 | 6.5× | 412,750 | 109,157 | 241,404 | 24,646 |
| S6, 9 cards | 30 | 8.5 | 3.6× | 154,649 | 58,288 | 61,824 | 13,613 |
| A6, 10 cards | 283 | 52 | 5.5× | 1,409,035 | 408,313 | 554,730 | 81,986 |
| S6, 10 cards | 98 | 24 | 4.0× | 557,794 | 176,412 | 155,133 | 35,994 |

The search is 2.0 to 6.5 times faster on these positions. What was adopted, each with DDS's counterpart:

- **Lead memory** (DDS keeps a best move per depth). The two leads that last settled a node for the same seat with the same number of cards left are tried right after the transposition table's move. Without it the benchmark positions take 2.25 times the nodes, random positions 6 to 7 percent more.
  Among declarer's lead nodes that some lead settles, the first lead tried is that lead in 99 percent of cases at A6 with 9 cards and 90 percent at S6 with 9 cards (45 and 41 without the memory); for a defender on lead 87 and 77 percent (13 and 63 without).
- **Quick tricks with both hands** (DDS's QuickTricks, simplified). With North or South on lead and no ruff possible: cash a card above every unseen card of its suit, or lead low to such a card in partner's hand, and count until the certainty runs out. Used as a lower bound at lead nodes and before table reads. Without it the benchmark positions take 58 percent more nodes and 3.1 times the table reads; random positions 4 to 9 percent more nodes.
- **Later tricks for trumps** (DDS's LaterTricks, trumps only). A trump above every trump of the other side wins the trick it is played on, whoever leads; North-South get at least the larger of their two holdings of such trumps, the defenders as many as one of them can be given. No effect on the benchmark positions, where trumps are drawn (0.1 percent); without it random positions take 13 to 14 percent more nodes.
- **Keys from relative ranks without a loop** (DDS uses lookup tables by suit holding). Each suit's part of the key comes from two bit-extract and two bit-deposit instructions; the loop version remains for processors without them. With picking the best remaining move instead of sorting all of them, this took 14 to 25 percent off the time when it went in.
- **One transposition lookup on the way into a node and a pointer check on the way out**, instead of three lookups with three key computations; the trick's current winner computed once per node; pool counts per suit once per node in the defenders' move generator. Together about 10 percent of the tree time when they went in.
- **Transposition table of 2^18 entries** instead of 2^20: same nodes up to 10 cards on these positions and 3 to 9 percent less time at 10 cards (it stays in cache). Not compared at 11 cards or more.

Tried and dropped:

- The same memory for the second, third and fourth seats, and a table of replies to the previous card: each searched more nodes on every set (15 and 68 percent more on the benchmark positions, about 60 percent more on random 8-card positions).
- Low cards first for a defender's non-winning leads: within 1 percent either way.
- "The side on lead cannot win the coming trick" as a bound for both sides: correct, under half a percent fewer nodes.
- A global history count (first round): more nodes.

Not carried over: DDS's winning ranks, where a transposition entry records only the cards whose rank mattered, so that one entry covers every position that differs in lower cards. A table read depends on every card of the ending and reports nothing about which ranks mattered, so a node with a table read below it cannot be generalized this way. Measured at A6 with 9 cards: of the lead nodes searched, 1,206 of 3,388 at 6 to 8 cards left and 442 of 5,602 at 5 cards left had no table read below them. Those are the nodes the technique could reach; it was not implemented. It would become available everywhere if the table stored, with each value, how many top cards of each suit the value depends on.

## What each part contributes

Node and table-read totals with one part switched off (`ordtest.py`). Benchmark: the 15 test-set positions at 7 to 10 cards, contract question. Random: 300 7-card and 120 8-card positions drawn uniformly over card patterns, position value. Answers were the same in every row.

| Build | Benchmark nodes | Benchmark reads | Random 7-card nodes | Random 8-card nodes |
| --- | --- | --- | --- | --- |
| Current | 1,169,268 | 200,810 | 753,126 | 1,899,563 |
| No lead memory | 2,636,668 | 636,058 | 796,631 | 2,031,099 |
| No two-hand quick tricks | 1,850,590 | 622,687 | 785,914 | 2,075,773 |
| No trump later tricks | 1,170,303 | 200,906 | 857,643 | 2,142,598 |
| No bounds at all | 2,009,790 | 837,518 | 1,087,595 | 3,062,045 |
| No move ordering | 5,333,306 | 1,684,041 | 1,700,851 | 6,651,614 |

## Where the time goes: lookups against the tree above the table

The same search run four ways, interleaved over 8 rounds, minimum taken (`split.py`). Contract question, 4-card table, milliseconds.

- Free lookups (`--replay`): the table's answers are returned in recorded order, with no key computed and nothing read. What is left is the tree above the table.
- In cache (`--cells 0.002 --noflush`): values read from a 2 MB table that stays in cache. Adds the key computation.
- Cold (`--cells 2.5`): values read from a 2.5 GB array at a hashed slot, 4 KB pages, the touched cache lines flushed before timing. Adds the wait on memory.
- Cold on 2 MB pages (`--cells 2.5 --huge`).

| Position | Lookups | Free | In cache | Cold | Cold, 2 MB pages | Tree | Key | Memory |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A6, 8 cards | 3,930 | 1.7 | 1.9 | 2.0 | 1.8 | 85% | 11% | 4% |
| S6, 8 cards | 3,332 | 1.6 | 1.9 | 2.3 | 2.0 | 70% | 15% | 16% |
| B6, 8 cards | 1,144 | 0.4 | 0.5 | 0.7 | 0.6 | 66% | 12% | 22% |
| A6, 9 cards | 24,646 | 11 | 12 | 13 | 13 | 79% | 8% | 13% |
| S6, 9 cards | 13,613 | 6.3 | 7.0 | 8.5 | 7.5 | 75% | 8% | 18% |
| A6, 10 cards | 81,986 | 40 | 44 | 52 | 47 | 77% | 8% | 15% |
| S6, 10 cards | 35,994 | 17 | 20 | 24 | 21 | 71% | 11% | 18% |

Tree, Key and Memory are shares of the Cold column. The tree above the table is 66 to 85 percent of the time, the key computation 8 to 15 percent (46 to 99 ns a lookup) and the wait on memory 4 to 22 percent. With free lookups the search would be 1.2 to 1.5 times faster; that is the most any work on the index or the read can gain. Before the second round the tree was 55 to 68 percent and free lookups were worth 1.5 to 1.8 times: the bounds removed most of the table reads.

Table size (cold, 4 KB pages, 5 rounds, minimum, milliseconds):

| Position | 0.03 GB | 1.07 GB | 1.75 GB | 2.5 GB | 3.09 GB |
| --- | --- | --- | --- | --- | --- |
| A6, 8 cards | 1.8 | 1.8 | 1.9 | 1.9 | 1.8 |
| S6, 8 cards | 2.1 | 2.3 | 2.1 | 2.3 | 2.1 |
| A6, 9 cards | 11 | 12 | 12 | 13 | 13 |
| S6, 9 cards | 6.8 | 7.7 | 8.0 | 8.0 | 7.8 |

1.07 GB, 1.75 GB, 2.5 GB and 3.09 GB are within the run-to-run spread of each other (the specified table is 2.80 GB). A 0.03 GB table is 7 to 15 percent faster than a 2.5 GB one. 2 MB pages for the transposition table made no measurable difference to the tree part (A6, 8 cards 1.6 against 1.5 ms; S6, 8 cards 1.6 against 1.7 ms; A6, 9 cards 10 against 10 ms; S6, 9 cards 5.7 against 5.8 ms).

Limits of this split. The key is the stand-in key (canonical suit order, then a hash); a real index swaps the hash for a ranking step and has not been written or timed. Hashed slots are the worst case for memory; a real index would put related endings near each other. The machine is an x86 VM with 4 KB pages and a large shared L3; Apple silicon has 16 KB pages and different caches.

## Building the 4-card table

Not built. `TABLE_BUILD.md` is the build specification, for the table that holds unknown-or-exact knowledge per suit (the mixed column below; 7,457,413,672 entries exactly). In outline:

- An index function, position plus knowledge state to slot. With suits sorted so that permutations share a slot the table is the size given below; without the suit symmetry it is about 9 times larger.
- A builder that walks the entries in index order, solves each and packs 3 bits. Bottom-up: the 3-card table first (41,915,724 entries), then each 4-card entry is one trick of search reading the 3-card table.
- Compute. Per entry, measured on 200,000 random entries with show-out knowledge (`build_cost.py`): from scratch 20.2 µs (150 nodes, 0 lookups); from the 3-card table 8.4 µs (26 nodes, 8 lookups). For the specified table (7,457,413,672 entries) that is 17 core-hours from the 3-card table or 42 from scratch, if an entry with shape knowledge costs the same, which is unmeasured. With the search as it was before the second round the same measurement gave 10.3 to 11.2 and 29.3 to 31.7 µs. The 3-card table here is the stand-in hash map.
- Checks: entries against `pooled_ref.py`, `sure_cpp --value` and the test vectors.
- At play time: map the file into memory; `sure.cpp` built with `-DENDTABLE` reads it through `endtable/endtable.h` (`--table FILE`).

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

- The table itself and its index function (specified in `TABLE_BUILD.md`).
- Shape knowledge and pinned cards in the C++ search (it has hand sizes and show-outs only). `pooled_ref.py` defines the game with shape knowledge; `sure.py` has pinned cards.
- Winning ranks in the transposition table (see above), read-ahead of table slots, and splitting the legal cards across threads. None is implemented. The memory wait that read-ahead would attack is now 4 to 22 percent of the time.
- A richer quick-tricks bound for a defender on lead (the declaring side's version uses both hands; the defenders' counts only what the leader can hold).
- The rule "a card that guarantees the contract comes first" (`surebot.py`) still calls the Python search. It has not been rerun on the C++ search.
- Timings cover four deals, all spade contracts, positions on the sound line only. The random positions are uniform over card patterns, not over positions that arise in play.

## Run

```
g++ -O2 -march=native -std=c++17 -o sure_cpp sure.cpp
python check_cpp.py 5 250 --front 4            # against sure.py
python runpos.py A6_8,S6_8 --contract --front 4 --warm --cells 2.5
python split.py A6_8,S6_8 8 "free=--replay" "cache=--cells 0.002 --noflush" "cold4k=--cells 2.5" "coldhuge=--cells 2.5 --huge"
python ordtest.py "" "--nokiller" "--norun"       # node counts with parts switched off
python build_cost.py 4 200000
python bench_cpp.py 6,7,8 --front 4 --contract  # needs the repo (SDB_ROOT) for Board
```

Input to `sure_cpp`, one position per line: `trump leader hN hS pool cE cW vE vW [cards already played to the trick]`. Trump 0-3 = S, H, D, C, 4 = notrump; leader 0-3 = N, E, S, W; hands and pool as hex masks with card = 13 × suit + rank (2 = 0 ... A = 12); cE, cW the defenders' hand sizes; vE, vW bit masks of suits shown out of. A line may start with `N<k>` to ask the contract question with target k. `csure.py` builds the line from a `sure.Sure` object.
