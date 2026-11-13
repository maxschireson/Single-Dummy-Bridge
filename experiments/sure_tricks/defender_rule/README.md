# The defender rule in `sure.cpp` and `sure.py` (fixed 13 November 2026)

## The bug

The search let a defender try only the lowest and highest card of a run of touching pool cards while his partner was
still to play to the trick (and when leading). Pool cards have no hand until they are played, so such a run can be
split between East and West, and a middle card can leave the trick's winner unsettled until partner plays, after
declarer's side has had to commit. The rule therefore missed defences, and values could be a trick too high for
declarer. Found while building the ending table: `../endtable/REPORT.md` section 1, with the counterexamples
(`../endtable/k3_defender_rule_counterexamples.txt` and the four 4-card lines in section 5).

## The fix

`genDef` in `../sure.cpp` and the defender branch of `Sure._can` in `../sure.py` now reduce a run to one card only when
the reduction is sound:

1. partner has already played to the trick;
2. partner is known to hold none of the suit (shown out);
3. the card is a plain discard (not the suit led, not a trump).

Otherwise every card is tried. `sure_cpp --nodefeq` tries every defender card always (no reductions; exact by
construction), for checking.

## Checks (13 November 2026, sandbox, 2 cores)

| Check | Result |
| --- | --- |
| The 1 three-card and 4 four-card counterexamples | old 1 trick, fixed 0, `--nodefeq` 0, table 0 |
| All 21,869,828 show-out-only entries of the 3-card table against `sure_cpp --value` (`../results/k3_showout_fixed.txt`) | 0 differ (the old search differed on 1) |
| Fixed against `--nodefeq`, per-card exact values: 151,241 real-play positions with 1 to 7 cards left (below) | 0 differ |
| Fixed against `--nodefeq`: random played-out positions (1,500 each at 4, 5, 6 cards; 3,000 at 7; 800 at 8) | 0 differ |
| Fixed against `--nodefeq`: run-dense endings, 0 to 3 cards in the trick (20,000 at 4 and 5 cards, 3,000 at 6) | 0 differ |
| `check_cpp.py 5 250`, `check_cpp.py 4 600 --front 3` (C++ against the fixed `sure.py`) | 0 mismatches |
| `check_cpp.py 5 250 --front 3 --table k3.et` (`-DENDTABLE`, real 3-card table) | 0 mismatches |
| `check_sure_reduction.py 4 400` (fixed `sure.py` against its unreduced search) | 0 mismatches |
| `check_pooled_ref.py A 4 300` (fixed `sure.py` against `pooled_ref.py`) | 0 mismatches |

## How often the old rule gave a wrong answer in play

Real play: every position before a card in 241 Gen 8 arena episodes (`arena-gen8-azure1-feed`, episodes 0 to 240, main
and fork tables, de-duplicated), from the declaring side's view as the claim finder builds it (`episode_positions.py`).

| Positions | Question | Old differs from fixed |
| --- | --- | --- |
| 151,241 with 1 to 7 cards left | exact value of every card | 1 position: two of a defender's cards valued 3 tricks for declarer instead of 2; the position's value unchanged |
| 6,458 with 8 to 10 cards left, contract not yet made or lost | `N<need>` (the claim finder's question) | 0 |
| 1,657 with 8 to 10 cards left (every fourth) | exact value of every card | 0 |

The one position (South led ♥8, East to play, 6 cards each, 3 tricks still needed):
`0 2 4801810010 20000308400 4a01402464102 6 6 4 0 19`. The old search said East's ♠3 or ♠10 leaves declarer a
guaranteed contract; it does not. An 8X defender reading hand-over odds would have avoided those cards for that reason.

Run-dense random endings (a further 150,000 at 5 cards, 40,000 at 6) gave no difference either. The ending-table
counts are the densest measure: 1 in 21.9 M show-out 3-card entries, 4 in 1 M show-out 4-card entries.

## Cost

Search time, old against fixed:

- Real-play positions without a table (as the bots ask): 8 to 10 cards left, `N<need>` 225.5 s against 240.9 s for the
  6,458 positions (+7 percent); exact values 561 s against 615 s for 1,657 (+10 percent). 1 to 7 cards: 40.1 s against
  41.4 s for 151,241 (+3 percent).
- Benchmark positions (`split.py ... "new=--replay"`, contract question, 4-card stand-in table, best of 5), ms:

| Position | Old | Fixed | `--nodefeq` | Nodes old / fixed |
| --- | --- | --- | --- | --- |
| A6_8 | 1.64 | 1.89 | 3.29 | 15,778 / 18,312 |
| S6_8 | 1.80 | 2.25 | 4.02 | 16,650 / 20,856 |
| B6_8 | 0.46 | 0.54 | 0.83 | 4,149 / 4,968 |
| A6_9 | 11.73 | 12.30 | 21.80 | 109,157 / 112,634 |
| S6_9 | 6.57 | 7.42 | 13.54 | 58,288 / 65,830 |
| A6_10 | 43.00 | 46.21 | 82.87 | 408,313 / 436,199 |
| S6_10 | 18.81 | 20.59 | 37.64 | 176,412 / 189,920 |

The timings in `../SEARCH.md` were taken with the old rule.

## Files

- `episode_positions.py MAXLEFT EPISODES...` — solver lines for every real-play position in arena episodes.
- `gen_play_positions.py N COUNT SEED` — random deals played out at random to N cards left.
- `gen_dense.py SURE_DIR N COUNT SEED [--trick]` — run-dense endings as `check_cpp.py` draws them.
- `cmp_bins.py LINES name=CMD ...` — per-card values of several solver commands on the same lines.

```
g++ -O2 -march=native -std=c++17 -o sure_cpp ../sure.cpp
python episode_positions.py 7 EPISODES/*.json.gz | cut -f4 > ep7.txt
python cmp_bins.py ep7.txt "plain=./sure_cpp --nodefeq --keep --ttbits 22" "fixed=./sure_cpp --keep --ttbits 22"
```
