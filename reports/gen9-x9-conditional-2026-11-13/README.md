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

_Filled in when both pilots finish._

## Reading

_Filled in when both pilots finish._
