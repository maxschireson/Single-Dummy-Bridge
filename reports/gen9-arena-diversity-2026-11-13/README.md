# E9-20: diversity and redundancy of the current population (g9, 13 November 2026)

Gen 9 experiment E9-20 (`team/gen9:experiments/E9-20.md`), for [the arena design note](../../docs/gen9/arena-selfplay.md),
section 3. Read-only; decides nothing.

## 1. Results distance (from E9-21's cells)

19 pairs of ladder points have results rows within noise of each other (mean z² of their cells against every other
point at most 1) and strengths within 0.1 IMPs a board, among them `6-32` with `8c-32` (the house system against a
Precision rule bidder) and `6-256` with BEN 64. With pair effects this small (t2 = 0.0067) a results row is little more
than the strength, so the results distance alone would retire members that differ in system.

## 2. Behaviour distance (paired decisions on common-auction boards)

In a common auction both tables hold the same hands and auction and the two bots sit in swapped seats, so until the
first card where the tables' plays differ, each card is the same decision taken by one bot at one table and the other
bot at the other. Forced cards are left out. Up to five board shards per registered feed (113 feeds, `rows` collected
07:14 UTC): 141,234 paired decisions over 553 pairs of bot names. Ladder points with at least 300 paired decisions:

| Pair | Paired decisions (not forced) | Different card | Opening leads | Different lead | Different lead suit | Strength difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `8c-32~8s-32` | 25,953 | 0.0% | 625 | 0.0% | 0.0% | -0.79 |
| `5~5-32` | 1,184 | 6.8% | 93 | 30.1% | 25.8% | +0.23 |
| `5-32~5R32` | 1,841 | 6.8% | 158 | 40.5% | 36.7% | -0.03 |
| `71s-32~8c-32` | 6,712 | 8.8% | 632 | 0.0% | 0.0% | +0.35 |
| `71s-32~8s-32` | 13,191 | 9.0% | 1,258 | 0.0% | 0.0% | -0.44 |
| `6-256~6-32` | 5,462 | 9.1% | 569 | 37.4% | 29.9% | +0.13 |
| `5R32~5RZ32` | 1,840 | 9.6% | 195 | 32.3% | 29.2% | -0.05 |
| `71s-32~7s-32` | 16,798 | 10.7% | 1,804 | 4.8% | 1.8% | -0.03 |
| `5R192~5R32` | 473 | 12.9% | 63 | 25.4% | 23.8% | +0.20 |
| `6-32~7s-32` | 17,898 | 15.7% | 2,816 | 11.0% | 4.9% | -0.32 |
| `6-32~71s-32` | 2,645 | 16.4% | 433 | 12.7% | 6.5% | -0.29 |
| `5RZ32~6-32` | 6,784 | 22.2% | 1,525 | 54.2% | 48.9% | -0.85 |
| `4b~5-32` | 617 | 32.3% | 199 | 45.2% | 32.7% | -0.02 |
| `5RZ32~7s-32` | 2,877 | 33.6% | 967 | 51.9% | 45.8% | -1.18 |
| `5RZ32~8s-32` | 1,860 | 33.8% | 628 | 54.6% | 49.4% | -1.59 |
| `4b~5R32` | 933 | 36.9% | 344 | 57.3% | 45.3% | -0.05 |
| `3~6-32` | 936 | 40.3% | 377 | 60.7% | 50.1% | -1.01 |
| `3~5R32` | 412 | 42.2% | 174 | 58.6% | 48.3% | -0.11 |
| `2~6-32` | 789 | 48.3% | 381 | 62.7% | 48.3% | -0.97 |
| `6-256~ben` | 434 | 51.8% | 225 | 66.2% | 39.6% | +0.28 |
| `71s-32~ben64` | 8,480 | 54.0% | 4,576 | 66.6% | 37.7% | +0.21 |
| `7s-32~ben64` | 1,259 | 54.3% | 684 | 64.9% | 39.0% | +0.24 |
| `8s-32~ben64` | 7,434 | 55.3% | 4,109 | 67.0% | 37.7% | +0.65 |
| `7s-32~ben` | 2,271 | 55.9% | 1,269 | 67.0% | 40.7% | +0.48 |
| `6-32~ben` | 480 | 56.5% | 271 | 69.4% | 44.3% | +0.15 |
| `3~4` | 545 | 69.2% | 377 | 77.2% | 45.9% | +0.36 |
| `1~6-32` | 513 | 73.7% | 378 | 81.5% | 62.7% | -1.88 |
| `1~7s-32` | 1,278 | 75.6% | 966 | 82.9% | 61.0% | -2.21 |
| `1~8s-32` | 808 | 77.5% | 626 | 84.3% | 59.7% | -2.62 |

- `8c-32` and `8s-32` never chose differently in 25,953 paired card decisions: the same card play with a different
  bidder. In the native condition `8c-32` is 0.79 IMPs a board weaker, all of it from bidding.
- `71s-32` and `8s-32` differ on 9% of card decisions and never on the opening lead.
- No pair of different bots is under 5% at the card level; the closest are the Gen 5 variants (6.8%).
- "Different card" counts choices between equal cards too, so a bot that randomizes among equal cards (`8r-32`, 8X)
  looks different from its own base on many decisions. A behaviour distance for redundancy should count only choices
  that differ in double-dummy value, or use suits for leads.

## 3. Declared distance

Every house bot declares one bidding family (`house-gen6`, `house-gen5` and `house-dds40k` are lineages of it) and no
carding (E9-9). Only `8c-32` (Precision) and BEN differ in system. So the declared distance separates three groups and
nothing within the house group.

## What it means for the design

The rule of section 3.3 needs all three distances, as written: by results alone `6-32` and `8c-32` look redundant,
and by card play alone `8c-32` and `8s-32` are identical, while their declared systems differ. The behaviour
threshold has to be on choices that differ in value, not on cards, once randomizing bots are in the population.
Under the rule as written, no current ladder member is redundant.
