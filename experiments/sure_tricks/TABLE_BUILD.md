# Ending table for the sure-trick search: build specification

Status: specification, 12 November 2026. Nothing in this document has been built except the two Python
references and the test vectors it names. Written to be implemented without access to the conversation
that produced it.

## 1. What to build

A memory-resident table of every 4-card ending of the *pooled-defender game* (section 3), giving the number
of tricks North-South can guarantee, for every state of knowledge about the defenders' shapes that the
table supports (section 3.2). The sure-trick search (`sure.cpp`) stops at 4-card trick boundaries and reads it.

| Item | Value |
| --- | --- |
| Entries, 4-card table | 7,457,413,672 (exact, section 4.6) |
| Size at 3 bits an entry | 2.80 GB |
| Smaller tables needed on the way | 1, 2 and 3 cards: 426, 168,458 and 41,915,724 entries |
| Build compute, 4-card | about 23 core-hours estimated (section 6.4), not measured |

Deliverables:

1. `endtable/endtable.h`: the index (canonical form, rank, unrank, class table) and the reader, C++17, no dependencies.
2. `endtable/endtable_build.cpp`: the builder (bottom-up, parallel, resumable).
3. `endtable/` tests that implement the acceptance checks of section 8.
4. Built tables for 1, 2 and 3 cards, and the 4-card table once a machine is assigned (section 9).
5. `endtable/REPORT.md`: results of every acceptance check with counts, build time, file hashes, read-time measurements, and anything that did not match this document.

Work in `experiments/sure_tricks/endtable/` on branch `research/sure-trick-table-20261112`. Every file there is new.
Do not edit `sure.cpp` or the other existing files in `experiments/sure_tricks/`: the search is being changed in
parallel by another session. `sure.cpp` already contains the hook that calls your reader (section 7).

## 2. What exists

All in `experiments/sure_tricks/`.

| File | Role for this work |
| --- | --- |
| `pooled_ref.py` | **Normative definition of the game and of an entry's value.** Plain minimax, no pruning. |
| `endtable_ref.py` | **Normative definition of the index** (canonical form, classes, rank, unrank, sizes). |
| `endtable_vectors.jsonl` | 5,726 test vectors: `k`, `slot`, position `line`, `value` (section 8). |
| `check_pooled_ref.py`, `check_endtable_ref.py`, `make_vectors.py` | How the references were checked and the vectors made. |
| `sure.cpp` | The search that will read the table. Knows show-outs only (no exact lengths yet). `--value` prints one position's value. |
| `sure.py`, `exact.py` | Earlier references: the game with show-outs only, and exhaustive enumeration over splits. |
| `SEARCH.md` | Timings of the search above a simulated table, and where its time goes. |

How far the references are checked (outputs in `results/pooled_ref_checks.txt`, `results/endtable_ref_checks.txt`, `make_vectors.log`):

- `pooled_ref.py` against `sure.py` on random endings with show-outs: 400 2-card, 300 3-card, 40 4-card, 0 mismatches.
- `pooled_ref.py` against `exact.py` run over every split consistent with random shape knowledge: 300 2-card, 200 3-card, 60 4-card, 0 mismatches.
- `pooled_ref.py` against `sure_cpp --value` on the 3,507 test vectors whose knowledge is show-outs only: 0 mismatches.
- `endtable_ref.py`: entry counts for 1 and 2 cards equal a brute-force count of distinct canonical forms; unrank then rank returns the slot for every slot at 1 and 2 cards and for 20,000 random slots at 3 and at 4 cards; positions transformed by suit permutation, half-turn, new ranks and removal of forced knowledge map to the same slot in all of those cases.

Not checked by anything: values of 4-card entries with exact lengths other than 0 or "all", beyond the 181 such
vectors and the 60 random endings above. Your tables will be the first large body of such values; section 8 says how to check them.

## 3. The game

`pooled_ref.py` is the definition. This section restates it.

### 3.1 Position

Cards are integers `13 * suit + rank`, rank 0 (the two) to 12 (the ace). Seats 0..3 are North, East, South,
West. Trump is a suit 0..3, or 4 for notrump. North and South are the declaring side.

A position between tricks:

- `hN`, `hS`: North's and South's cards (52-bit masks).
- `pool`: the unseen cards, held between East and West.
- `cE`, `cW`: how many cards East and West hold; `cE + cW` is the pool size. At a trick boundary all four hands have the same number of cards, `k`.
- `el[s]` for each suit: unknown, or East's exact number of pool cards in suit `s` (West holds the rest).
- trump, and the seat on lead.

### 3.2 Knowledge

A split of the pool between East and West is *consistent* if the hand sizes hold and every exact length holds.
With `x[s]` the number of pool cards in suit `s`:

- A show-out is an exact length: East void in `s` is `el[s] = 0`, West void is `el[s] = x[s]`.
- A whole shape is every suit exact.
- Anything between (some suits exact, others unknown) is allowed.

Normalization (`pooled_ref.normalize`): lengths that are forced become exact. A suit with no pool cards is exact 0.
If East has no cards left for the unknown suits they are all 0; if West has none they are all `x[s]`; a single
remaining unknown suit takes what is left. A normalized state therefore has either no unknown suit or at least
two, with East holding more than none and fewer than all of the cards in them. The function returns `None`
when no split is consistent. Two knowledge states with the same set of consistent splits normalize to the same thing.

### 3.3 Play

- North or South plays any card of the suit led if he has one, otherwise any card.
- A defender may play pool card `c` of suit `s` when all of the following hold (`pooled_ref.defender_plays`):
  1. If a different suit `L` was led, he holds none of `L`: `el[L]` becomes 0 (East) or `x[L]` (West). Illegal if `el[L]` is already exact and different.
  2. He can hold a card of `s`: if `el[s]` is exact, East needs `el[s] >= 1` and it drops by one; West needs `x[s] - el[s] >= 1`.
  3. With `c` removed from the pool and his count reduced, the knowledge normalizes (is consistent).
- The trick goes to the highest trump, else the highest card of the suit led. The winner leads next.
- North-South maximize, East-West minimize, the number of tricks North-South win from here on.

Declarer sees both his hands and every card played, so this is a game of perfect information. Its value is the
most tricks one line of play guarantees against every consistent split and every defence.

### 3.4 Entry

For hand size `k`, an entry is a position at a trick boundary with `k` cards in each hand, and its value is the
game value, 0..k. The search today produces show-out knowledge only; shape knowledge is for searches that
assume a shape ("if East is 3-2 in the minors").

## 4. Index

`endtable_ref.py` is the definition; its module docstring states the scheme. Port it exactly: your slot numbers
must equal its slot numbers (section 8, T2). Summary:

### 4.1 Positions that share an entry

1. Only the order of the remaining cards within a suit matters, not their ranks.
2. Half-turn: with South or West on lead, swap North with South and East with West (`el[s]` becomes `x[s] - el[s]` where exact), so the leader is North or East.
3. Suits may be permuted: all four at notrump, the three side suits with a trump suit.
4. A trump suit with no cards left in any hand is notrump.
5. Knowledge is normalized.

### 4.2 Suit type and pattern

A suit's type is `(n, s, x, kn)`: North's, South's and unseen cards in it, and the knowledge code, -1 for unknown,
else East's exact length. For `x = 0` the code is 0. Valid triples have `n, s <= k`, `x <= 2k`, `n + s + x <= 13`.
Types are ordered as tuples; a type's id is its position in that order.

A suit's pattern is which of its `L = n + s + x` cards, numbered 0 (lowest) upward, each of North and South holds.
Pattern rank: `rankN * C(L - n, s) + rankS`, where `rankN` is the colex rank of North's positions among the `L`, and
`rankS` the colex rank of South's positions among the `L - n` positions North does not hold, renumbered from 0.
Colex rank of positions `p1 < ... < pm` is the sum of `C(p_i, i)`. A type has `P = C(L, n) * C(L - n, s)` patterns.

### 4.3 Class

Canonical suit order: the trump suit first, if there is one; the other suits ascending by (type id, pattern rank).
A class is the tuple of the four type ids in that order. A class is valid when the counts add up (`k`, `k`, `2k`) and
the knowledge is normalized and consistent: with no unknown suit, the exact lengths sum to `k`; otherwise at
least two unknown suits, exact lengths summing to less than `k`, and West's known cards also fewer than `k`
(`Index.knowledge_ok`). With a trump suit, its triple is not `(0, 0, 0)`.

Classes are listed in lexicographic order of their id tuples, separately for notrump and trump. A class's offset
is the total size of the classes before it.

### 4.4 Rank within a class

Digits, most significant first:

- with a trump suit, its pattern rank, radix `P`;
- then, for each run of `m` consecutive suits of equal type (pattern count `P`), the multiset rank of their sorted pattern ranks `r_0 <= ... <= r_{m-1}`: the sum over `j` of `C(r_j + j, j + 1)`, radix `C(P + m - 1, m)`.

A trump suit is never grouped with a side suit of the same type.

### 4.5 Slot

`slot = base[strain] + 2 * (class_offset + rank_in_class) + leader_bit`, with `base[notrump] = 0`,
`base[trump] = 2 * M_notrump`, and leader bit 0 for North, 1 for East. Slots need 64 bits.

`unrank(slot)` gives the canonical concrete position: suits in canonical order placed as suits 0..3 on the lowest
ranks, trump 0 for a trump entry and 4 for notrump.

### 4.6 Exact sizes

From `endtable_ref.py` (`results/endtable_counts.txt`). Your class table must reproduce every number.

| k | Suit types | Notrump classes | Notrump positions | Trump classes | Trump positions | Entries | Bits | Bytes of data |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 32 | 21 | 69 | 52 | 144 | 426 | 2 | 107 |
| 2 | 171 | 1,008 | 21,113 | 3,374 | 63,116 | 168,458 | 2 | 42,115 |
| 3 | 544 | 18,290 | 4,725,808 | 68,230 | 16,232,054 | 41,915,724 | 2 | 10,478,931 |
| 4 | 1,230 | 184,288 | 800,290,430 | 711,733 | 2,928,416,406 | 7,457,413,672 | 3 | 2,796,530,127 |

Entries = 2 × (notrump positions + trump positions). The Python reference builds the 4-card class table in 17 seconds; C++ should take well under a second.

### 4.7 Reading speed

The reference is written for clarity. The reader has to be fast: the search spends 13 to 26 percent of its time
computing a stand-in key at 65 to 110 ns a lookup (`SEARCH.md`). Target: slot computation at or under that on
the same machine, measured on random positions and reported. Suggestions, none binding:

- Pattern ranks from small precomputed tables (colex rank by 13-bit mask) after compressing a suit's cards to positions.
- Class lookup in two levels, so the hot part stays in cache: the four `(n, s, x)` triples to a base and a small per-shape array indexed by the knowledge codes. There are 896,021 classes at 4 cards; one flat hash of them would not stay in cache.
- No x86-only instructions without a portable fallback. The table will be used on Apple silicon as well as x86-64.

## 5. File format

One file per hand size. Little-endian.

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 8 | magic `SDBET001` |
| 8 | 4 | format version, 1 |
| 12 | 4 | `k` |
| 16 | 4 | knowledge kind, 1 (unknown or exact per suit) |
| 20 | 4 | bits per entry: 2 for k <= 3, 3 for k = 4 |
| 24 | 8 | entries |
| 32 | 8 | notrump positions |
| 40 | 8 | trump positions |
| 48 | 8 | notrump classes |
| 56 | 8 | trump classes |
| 64 | 32 | SHA-256 of the data section (the bytes of data counted in 4.6) |
| 96 | 4000 | zero |
| 4096 | | data: entry `i` occupies bits `[bits * i, bits * (i + 1))`, least significant bit first, followed by at least 8 zero bytes |

The class table is not stored. The reader rebuilds it on open and refuses the file if its counts differ from the header.
Table files are not committed to git. Add them to a `.gitignore` in `endtable/`; where they are kept is Max's decision (section 9).

## 6. Builder

### 6.1 Bottom-up

The value of a `k`-card entry is one trick of minimax whose leaves read the `(k-1)`-card table:

```
value(entry) = minimax over the four plays of:  (1 if North or South wins the trick else 0)
                                                + table[k-1](position after the trick, winner on lead)
```

with `table[0] = 0`. Build 1, then 2, then 3, then 4. Each needs only the table below it in memory (10.5 MB for the 4-card build).

### 6.2 One-trick evaluator

Write it standalone from section 3.3: four plies, legal plays as defined there, knowledge updated and
normalized after each defender's play, exact value by alpha-beta over the range 0..k. It does not need a
transposition table, bounds or move ordering, and it must not depend on `sure.cpp`.

First version: no card equivalences at all. It is then a direct transcription of `pooled_ref.py` and is checked
against it. Equivalences are an optimization to add afterwards and to verify against the plain version (T6):

- North or South: among his legal cards, cards with no live card of another hand between them are equivalent; play one.
- A defender: pool cards of a suit with no North or South card between them form a run. One card per run is enough when his partner has already played to the trick, or his partner holds no card of the suit (exact length 0 for partner), or the card is a plain discard (not of the suit led, not a trump). Otherwise both the lowest and the highest card of each run are needed. Lowest only is unsound: it was tried and gave wrong values (`README.md`, section 5). These rules were verified for show-out knowledge only.

### 6.3 Mechanics

- Iterate positions by unranking, both leader bits per position.
- Parallel over contiguous slot ranges whose boundaries are multiples of 8 entries, so no two workers write the same byte.
- Resumable: fixed-size chunks, a record of finished chunks, the header and hash written last.
- Deterministic: the same build twice gives the same bytes.

### 6.4 Compute

Measured with the current search on 200,000 random 4-card entries with show-out knowledge, hash map standing in
for the 3-card table: 11.2 µs an entry (33 nodes, 11 lookups); solving each from scratch: 31.7 µs. An earlier
run gave 10.3 and 29.3. At 11.2 µs, 7.46e9 entries are about 23 core-hours. Unmeasured: the cost with a
real index, with shape knowledge, and without card equivalences. Report the measured figure.

Memory: the output (2.8 GB, can be written chunk by chunk), the 3-card table and the class table.

## 7. Reader interface

`sure.cpp`, compiled with `-DENDTABLE`, includes `endtable/endtable.h` and calls exactly this:

```cpp
struct EndTable;                                    // opaque
EndTable* endtable_open(const char* path);           // map the file read-only; nullptr on any failure
void      endtable_close(EndTable*);
int       endtable_cards(const EndTable*);           // k

// Position at a trick boundary with k cards in each hand.
// hN, hS, pool: 52-bit masks, bit 13 * suit + rank.  el[s]: -1 unknown, else East's exact length in suit s.
// trump 0..3, or 4 notrump.  leader 0..3 = N, E, S, W.
// The knowledge need not be normalized; it is consistent.
uint64_t  endtable_slot(const EndTable*, uint64_t hN, uint64_t hS, uint64_t pool,
                        const int8_t el[4], int trump, int leader);
int       endtable_lookup(const EndTable*, uint64_t hN, uint64_t hS, uint64_t pool,
                          const int8_t el[4], int trump, int leader);   // tricks North-South guarantee, 0..k
```

Reads are thread-safe. `endtable_slot` is public so that a caller can prefetch. Run as
`./sure_cpp --front 4 --table FILE ...`; the hook is in `tableValue()` and converts the search's show-out flags to exact lengths.

## 8. Acceptance checks

All must pass. Report each with its counts.

- **T1 sizes.** Suit types, classes, positions and entries for k = 1..4 equal section 4.6.
- **T2 index.** For every line of `endtable_vectors.jsonl`, `endtable_slot` equals `slot`. unrank then rank returns the slot for every slot at k <= 3 and for at least 1e8 random slots at k = 4.
- **T3 shared entries.** For at least 1e6 random entries per k: the position after a random suit permutation (trump keeping its role), a half-turn, re-spreading the cards onto random ranks in the same order, and replacing forced exact lengths by unknown, maps to the same slot (`check_endtable_ref.py` shows the transformations).
- **T4 values.**
  - Every vector's `value` equals the table.
  - k = 1 and 2: every entry equals `pooled_ref.py`.
  - k = 3: every entry whose exact lengths are all 0 or `x[s]` equals `sure_cpp --value`; at least 20,000 random entries equal `pooled_ref.py`.
  - k = 4: at least 1e6 random entries with exact lengths all 0 or `x[s]` equal `sure_cpp --value`; at least 2,000 random entries of any knowledge equal `pooled_ref.py` (about 0.4 s each).
- **T5 more knowledge never hurts.** For at least 1e6 random entries at k = 3 and at k = 4 that have an unknown suit: fixing that suit to each exact length that is consistent gives a value at least as large as the entry's.
- **T6 equivalences.** If the evaluator uses card equivalences, its tables equal the plain evaluator's for every entry at k <= 3 and for at least 1e8 random entries at k = 4.
- **T7 end to end.** With `sure_cpp` built `-DENDTABLE` and `--table`: `python check_cpp.py 5 250 --front 4 --table FILE` and `python check_cpp.py 6 30 --front 4 --table FILE` give 0 mismatches, and the per-card results on the positions in `bench_lines.json` equal those without `--table`.
- **T8 determinism.** Two builds of each table at k <= 3 are byte-identical. Record the SHA-256 of every table file.

If a check fails and you conclude that `pooled_ref.py` or `endtable_ref.py` is wrong, do not change them:
report the smallest counterexample in `REPORT.md`. `sure.py` and `exact.py` are available for a third opinion
(`check_pooled_ref.py` shows how; `exact.py` needs the repository's DDS build).

Also report: value histogram per k, build time and µs per entry with core count and machine, slot computation
time, and `python split.py` style timings of the search with the real table next to the stand-in figures in `SEARCH.md`.

## 9. Order of work and decisions that are Max's

1. Index in C++: T1, T2, T3.
2. Evaluator and the 1, 2 and 3-card tables: T4 to T6 for k <= 3, T8. These run in minutes on any machine.
3. Stop and report if anything in 1 or 2 disagrees with the references.
4. The 4-card build, when Max assigns a machine: about 23 core-hours and 4 GB of memory by the estimate above. Do not start it on the Azure boxes or any shared worker without that assignment.
5. T4 to T7 at k = 4, read-time measurements, `REPORT.md`.

For Max: which machine runs step 4, and where the 2.8 GB file is kept.

## 10. Out of scope

- Changes to the search (`sure.cpp`), including shape knowledge above the table. The search owner will add it.
- A 5-card table.
- Knowledge other than unknown or exact per suit (ranges, cards pinned to a defender).
- Packing denser than 3 bits.
