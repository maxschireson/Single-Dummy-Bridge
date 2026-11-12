# Ending table: build report

Status, 12 November 2026: index, reader, evaluator and builder written; 1-, 2- and 3-card tables built and checked
(sections 1 to 4 below). The 4-card table is being built on azure6 (assigned by Max, 18:18 UTC); its results go in
section 5 when it finishes. Specification: [`../TABLE_BUILD.md`](../TABLE_BUILD.md).

## 1. Deviation from the specification: no defender equivalences

Section 6.2's defender rule (one card per run of pool cards, or the lowest and highest card of the run while partner
is still to play) gives wrong values. Pool cards have no hand until they are played: a run of unseen cards with no
North-South card between them may be split between East and West, and which card one defender plays then decides
what his partner can still do. The tables are built with **every legal card tried for a defender**, as in
`pooled_ref.py`. Max agreed this at 18:46 UTC.

Evidence. The 3-card table built with the section 6.2 rule differs from the table built with no equivalences in 114
of 41,915,724 entries, every one by a trick in declarer's favour (1 against 0). `pooled_ref.py` agrees with the plain
value in all 114. They are listed in [`k3_defender_rule_counterexamples.txt`](k3_defender_rule_counterexamples.txt).
113 have exact lengths other than 0 or all; one has show-out knowledge only:

```
slot 35790336   spades trumps, North on lead, 3 cards each
North  ♠3 ♠2 ♣2         South  ♥3 ♦3 ♣4
unseen ♠6 ♠5 ♠4 ♥2 ♦2 ♣3   East is void in hearts, West void in diamonds (East holds the ♦2, West the ♥2)
sure_cpp input line: 0 0 8000000003 20008004000 1000400201c 3 3 2 4
```

North leads a trump. If East plays the ♠4, West must win the trick (his spades are all higher); if the ♠6, East wins
it. Either way the winner is settled before South discards, and South keeps the red three that guards against the
defender on lead: one trick. With the ♠5 the winner is settled only by West's card, after South's discard; West wins
with the ♠6 if South throws the ♥3 and plays the ♠4 if South throws the ♦3, and the defender on lead draws North's
last trump and cashes the red two South let go: no trick. The section 6.2 rule never tries the ♠5.

**`sure.cpp` and `sure.py` use the same rule** (`genDef`, "both ends of each run") and give 1 on this position
(`./sure_cpp --value`, `sure.Sure.can`); `pooled_ref.py` gives 0. Their values can therefore be too high for declarer.
Among all 21,869,828 show-out-only 3-card entries this is the only disagreement with the table (section 4, T4); the rate
at more cards is not measured. These files belong to the search owner and are not changed here.

Declarer's equivalence (one card per run of his own legal cards with no live card of another hand and no card of the
current trick between them) is implemented as an option. Tables built with it are byte-identical to the plain ones for
every entry at k = 1, 2, 3 (T6). At k = 4 it saves nothing measurable (5.16 against 5.18 µs an entry, below), so the
4-card table is built with no equivalences at all and T6 does not apply to it.

## 2. What is here

| File | Role |
| --- | --- |
| `endtable.h` | Index (class table, canonical form, slot, unrank), file format, reader (section 7 interface). C++17, POSIX `mmap`, GCC/Clang builtins. |
| `endtable_eval.h` | One-trick evaluator: four plies, alpha-beta, leaves read the (k-1)-card table. Defenders: every legal card. |
| `endtable_build.cpp` | Builder: bottom-up, parallel over 8-entry-aligned chunks, resumable (chunk record, header and hash written last), deterministic. |
| `endtable_tool.cpp` | Checks T1 to T6 and T8, value histograms, slot timing, per-entry evaluator timing. |
| `sha256.h` | SHA-256 for the header. |
| `check_normalize.py` | The C++ knowledge normalization against `pooled_ref.normalize`. |
| `check_values.py` | Table values against `pooled_ref.py`, reading the file and unranking with `endtable_ref.py` (no C++ involved). |
| `compare_showout.py` | Table against `sure_cpp --value` on show-out entries; disagreements re-solved with `pooled_ref.py`. |
| `compare_bench.py` | T7: per-card values on `bench_lines.json` with the built table against the stand-in. |
| `azure/run_endtable.sh` | The box run: setup, small tables, 4-card build as a systemd unit, status, checks. |
| `Makefile` | `make` builds `endtable_build` and `endtable_tool`; `ARCH=` (empty) for a portable build. |

```
make                                   # in this directory
./endtable_tool sizes                  # T1
./endtable_build 1 k1.et --plain
./endtable_build 2 k2.et --prev k1.et --plain
./endtable_build 3 k3.et --prev k2.et --plain
./endtable_build 4 k4.et --prev k3.et --plain --threads 8      # resumable: re-run the same command after an interruption
```

The test vectors `../endtable_vectors.jsonl` were missing from the branch's first commit (the repository's `.gitignore`
excludes `*.jsonl`); they were regenerated here with `make_vectors.py` and are byte-identical to the copy the search
session added afterwards (SHA-256 `daa9a892a6eca5d9a0fd313f0d05280bcdbd775db8a703052b3a4a88ba86c90e`).

## 3. Index (T1 to T3)

Machine for sections 3 and 4: the sandbox, a shared 2-core VM, Intel Xeon @ 2.10 GHz (AVX2, BMI2), 7 GB.

- **T1 sizes.** Suit types, classes, positions, entries and bytes for k = 1..4 equal section 4.6 exactly. Class table build: 0.11 s at k = 4.
- **T2 index.** All 5,726 vectors: `endtable_slot` equals `slot`, and unrank gives the vector's `line` exactly, 0 mismatches at every k. Unrank then rank returns the slot for every slot at k = 1, 2, 3 (426; 168,458; 41,915,724) and for 1e8 random slots at k = 4: 0 failures.
- **T3 shared entries.** 1e6 random entries per k = 1..4, 0 failures. Transformations: suit permutation (trump keeping its role), half-turn, cards re-spread onto random ranks in the same order, a random subset of exact lengths replaced by unknown whenever normalization restores them, and at notrump an empty suit named as trump.
- **Normalization.** `normalizeKnowledge` against `pooled_ref.normalize` on 1,827,914 states (pools of 0 to 8 cards by suit lengths, every East/West count split including impossible ones, every knowledge value from unknown to one past the length): 0 mismatches.
- **Portable path.** Built without BMI2 or hardware popcount: T2 vectors, every 3-card slot, 5e6 random 4-card round trips and 1e6 T3 transformations at k = 4 give 0 failures.

Slot computation, random raw positions (transformed as in T3), best of 5, `-march=native`:

| k | Slot | Slot and read |
| --- | --- | --- |
| 3 | 78 ns | 199 ns |
| 4 | 133 to 151 ns (3 runs) | after the build |

Of the 3-card figure, normalization is 28 ns and the four pattern ranks 11 ns (BMI2 `pext` with a colex table; 60 ns
with the bit loop). At k = 4 the rest is mostly the class lookup: a 16.8 MB array that random positions miss in cache.
The target in section 4.7 is the stand-in key's 65 to 110 ns measured inside the search; random positions are the worst
case for this lookup, so the in-search figure (section 5, `split.py`) is the comparable one. The portable build takes
250 ns at k = 3.

## 4. Tables of 1, 2 and 3 cards (T4 to T6, T8)

| k | Entries | Data SHA-256 (header) | File SHA-256 | Values 0, 1, 2, 3 tricks |
| --- | --- | --- | --- | --- |
| 1 | 426 | `74fb94555dc245713bf4329efd76f3cc439070aa75a1c50e6cb0cfde3f4b7249` | `be646285f1b1cfc819164d51a20c0f2200f2270bb5acd7b6a7d4e77c3b5e7dd6` | 225, 201 |
| 2 | 168,458 | `784914b44807ac0daf73573f0a40bd95802376665090fb8786a74967e23f3f94` | `f5733f22a4c97af868ac1037f55d1b351cb71a9ac2e488ad36b9227c12e94aee` | 63,358, 62,159, 42,941 |
| 3 | 41,915,724 | `636b5ecc717d05bf36c10335efded98fff8154f320084e82920fb44823053cdd` | `cfafa36d8f07976312c0ac2b4912c1f961f4221d1b388c85f781ce3b0c83c74d` | 12,255,836, 12,706,333, 10,721,881, 6,231,674 |

- **T4 values.**
  - Vectors: all 5,426 at k = 1..3 equal the table.
  - k = 1, 2: every entry equals `pooled_ref.py` (426 and 168,458; `check_values.py all`).
  - k = 3: all 21,869,828 entries whose exact lengths are all 0 or the pool length were run through `sure_cpp --value`. One differs, slot 35790336 (section 1); `pooled_ref.py` agrees with the table there. 20,000 random entries of any knowledge equal `pooled_ref.py` (seed 17).
- **T5 more knowledge never hurts.** k = 3: 1e6 random entries with an unknown suit, 5,100,023 comparisons with that suit fixed to each consistent length, 0 lower.
- **T6 equivalences.** Declarer-only equivalences give byte-identical tables at k = 1, 2, 3 (every entry). The section 6.2 defender rule: section 1.
- **T8 determinism.** Each table built at least twice with identical bytes: at k = 3 with 2 threads and 2^22-entry chunks, and again killed after 20 of 40 chunks and resumed with 1 thread and 2^20-entry chunks; also with and without declarer equivalences, and with portable and native builds.

Build cost (sandbox, `-march=native`): k = 3, 1.5 core-µs an entry (31.6 s on 2 threads), 20.7 nodes and 17.2 leaves an
entry. The 4-card evaluator on 50,000 random entries, one thread: 5.18 µs, 33.5 nodes, 32.8 leaves an entry; with
declarer equivalences 5.16 µs, 30.7 nodes, 28.8 leaves. Most of the time is the leaves' reads of the 3-card table.
At 5.2 µs, 7,457,413,672 entries are about 11 core-hours; the specification's estimate was 23.

End to end with the 3-card table (`sure_cpp` built `-DENDTABLE`, `--front 3 --table k3.et`): `check_cpp.py` 0 mismatches on
300 4-card and 100 5-card endings; per-card values on A6_6, A6_7, B6_7, S6_7 and A6_8 equal those with the stand-in.

## 5. The 4-card table

Running on azure6. Results to follow: build time and µs an entry, hashes, histogram, T2 to T5 and T7, read and slot
timings in the search (`split.py`).

## 6. For Max

- Where the 2.8 GB file is kept for good. It is on azure6 in `~/work/endtable/tables/` and is not committed.
- `sure.cpp` and `sure.py` carry the unsound defender rule (section 1); the search owner should know.
