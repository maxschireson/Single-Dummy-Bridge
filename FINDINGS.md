# Findings (15:47 UTC, 12 November 2026)

Stopped at Max's word after 1,081 boards each (seed 7111, deals 0 on, the same deals in both matches; common bidding).

| Match | IMPs a board for the first bot |
|---|---|
| `m1`: `71s-32-w1` (7.1, layout-weight exponent 1.0) against `7s-32` (7.0 as deployed, 0.5) | +0.137 +- 0.079 |
| `m3`: `71s-32-w1` against `7s-32-w1` (7.0 at 1.0) | +0.111 +- 0.078 |
| `m1` minus `m3`, board by board on the same deals: 7.0 at 1.0 over 7.0 at 0.5 | +0.026 +- 0.038 |

1,040 of the 1,081 boards came out the same in both matches (correlation 0.88): moving 7.0's exponent from 0.5 to 1.0
changed the result on 41 boards. The exponent barely changes the Gen 7 bot's play, as the 4.1 session's bench predicted
(the Gen 7 bot reads the play only from the deal list on, where 1.0 over 0.5 is worth +0.004 to +0.008 tricks a board).
So both matches are, in effect, 7.1 against 7.0 again, fork-free on random deals.
