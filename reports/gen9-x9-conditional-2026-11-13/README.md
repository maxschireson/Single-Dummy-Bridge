# Conditional claims in play: X9 pilots (G9-A11), 13 November 2026

g9. Plan: [docs/gen9/sid-integration.md](../../docs/gen9/sid-integration.md), section 3. Code: branch `feature/gen9-x9`:

| Commit | Content |
| --- | --- |
| ac7dfdb | Floors, commitment, forks |
| 7da02ba | `x9.prefer` |

Tests: `tests/test_x9.py`, 19 passing.

## Design

Each pilot plays one X9 bot against the same bot with conditional claims off (`8x3c-ctl`, which is 8X v3 `8x3-ft1`).

- **Deals and setup.** The pilots share deals: 400 fresh deals, seed 9241, in g9's sandbox (2 workers), forks on.
- **Pilot 1, `9x3c-ft1`.** Floors set at a certified weight of 0.9 or more; 8 cards or fewer; games, slams and doubled
  contracts; commitment at the next decision.
- **Pilot 2, `9x3p-ft1`.** As pilot 1, plus `prefer` 0.25. Among the blend's candidates within 0.25 tricks of the
  best value, the card with the highest certified floor wins, when that floor is 0.9 or more.

What is counted:

- **IMPs a board**, X9's side.
- **Main-line decisions.** Fork branches repeat a table's earlier decisions, so they are not counted.
- **Moves.** A move is a decision where the card differs from the one the same bot plays with conditional claims off,
  on the same random stream. Each move is forked and played out both ways.
- **Time.** Seconds a board for each side.

## Results

| | Pilot 1: floors at 0.9 | Pilot 2: plus prefer 0.25 |
| --- | ---: | ---: |
| Boards | 400 | 400 |
| Decisions where the conditional questions were asked | 295 | 290 |
| Floors set | 36 | 30 |
| Preference active | - | 30 |
| Lines committed (chosen card's floor 0.9 or more) | 25 | 29 |
| Later decisions kept to a commitment | 117 | 169 |
| Played card changed | 11, on 8 boards | 13, on 12 boards |
| Forks (both cards played out): better / worse | 0 / 1 | 0 / 2 |
| Mean a fork | -0.091 +- 0.096 IMPs | -0.154 +- 0.096 IMPs |
| Match, X9's side | -0.0025 +- 0.0025 IMPs a board (399 flat, 1 lost) | -0.0075 +- 0.0056 (398 flat, 2 lost) |
| Extra time a board | +0.177 +- 0.132 s (+1.9%) | +0.011 +- 0.019 s (+0.2%) |

All three lost boards were 4S contracts that made at both tables. X9 took fewer overtricks than the control:

- board 233, in both pilots, 10 tricks against 11: -1 IMP;
- board 352, pilot 2 only, 10 tricks against 12: -2 IMPs.

None of the 24 changed cards gained.

The two pilots' times cannot be compared with each other. The sandbox restarted during pilot 1, and the control took 9.3 s a board in pilot 1 against 6.7 s in pilot 2. Within each pilot, both bots ran in the same processes.

Files:

| File | What |
| --- | --- |
| `run400-*`, `prefer400-*` | Statistics (`pilot_stats.py`), forks pooled by `scripts/x8_forks.py` (8X's own features are in the same file), summaries, and one line a board (`*-results.jsonl.gz`) |
| Episodes | Not committed (22 MB a pilot); kept in g9's sandbox, `/home/claude/x9match` |

## Reading

- **How often the claims act.** At 0.9, conditional claims change about one card in every 30 to 50 boards. A line
  certified on 90% or more of the layouts is almost always the line the blend already prefers. The preference rule
  does not change that.
- **What a change does.** When a change did matter, it gave up overtricks for a safety the contract did not need.
  Nothing in 800 boards showed the other side of the trade: a game kept that the blend would have gone down in.
- **Can more boards settle it?** A rare large gain can only be priced on many more boards. At one change per 30 to
  50 boards, 10,000 boards would give 200 to 300 changes. The plan's rule (lower the threshold after a 2-SE gain)
  cannot fire on anything smaller.
- **Recommendation.** Keep conditional claims off in X9 by default (`x9.conditional` 0), and spend no box time on
  them. The code, the tests and the bots stay on `feature/gen9-x9` for a later look, for instance only in slams and
  doubled contracts, where a safety play pays more than an overtrick.
