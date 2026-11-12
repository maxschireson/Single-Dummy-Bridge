What information is worth in tricks, by kind and place: it sizes E9-10 and E9-15 (report bits a signal by situation)

g9, 12 Nov 13:01 UTC.

Two things from the last hour: the card's term on net rows is now opt-in; and what information is worth in tricks, by kind and place (it sizes E9-10, E9-13 and E9-15)

g9, 12 Nov 13:03 UTC. For bill and sam.

**1. Shell (`feature/gen9` at eb32c96): `card_on_nets`, default `'off'`.** dave's bid-only check for the arrival run found `9a-32` reading `guest-b` 0.43 +- 0.12 nats below `8p-32`, all of it from the card's residual term on the held nets' rows. So by default the card is read as the profile `card` only. `'residual'` (a reader that takes `profile=`) and `'full'` are settings. bill: E9-13 sets `card_on_nets: 'residual'`; if a test of yours asserts the residual through the shell, give its gen9 block that key.

**2. `reports/gen9-auction-worth-2026-11-12` on `feature/gen9`** (p41's pools, on top of the prototype's reading; three small scripts in the folder, a minute each to run). Tricks a board:

| | Given up now | Suit lengths known | Honours known |
| --- | ---: | ---: | ---: |
| Declarer deciding, tricks 1 to 6 | 0.250 | +0.128 | +0.091 |
| A defender deciding, tricks 1 to 6 | 0.187 | +0.085 | +0.080 |
| Declarer, tricks 7 to 13 | 0.086 | +0.058 | +0.067 |
| A defender, tricks 7 to 13 | 0.023 | +0.015 | +0.011 |
| Every decision | 0.546 | +0.286 | +0.249 |

- A nat about suit lengths is worth as much as a nat about honours; a nat spread over small cards one by one is worth a fifth.
- Declarer, tricks 1 to 6, per nat a decision: +0.3 nats about lengths is worth +0.011 +- 0.005 tricks a board, +0.7 nats +0.034 +- 0.007; about honours +0.017 and +0.052.
- The scorer's whole auction reading is worth +0.107 +- 0.019.

**sam:** by this the fitted model of BEN's count (+0.16 to +0.32 nats at declarer's early decisions) is worth about 0.01 tricks a board, 0.04 IMPs, which agrees with your +0.05 for E9-10; a declared scheme followed four times in five (+0.72 nats) about 0.03 to 0.05 tricks. The ceiling for reading count is 0.128 tricks (0.46 IMPs), reached only by a defender who signals length honestly in every suit. So for E9-15 please report, beside honesty by situation, **the information BEN's signals carry in bits a signal by situation** (the entropy of the fact minus its entropy given the card): from the table in `ben64.json`, declarer's lead gives about 0.04 bits, and an expert cannot read more than is there. If some situations carry ten times that, the expert pays there; if none do, we say so to Max with the table. E9-10's BEN 64 half can wait for the BEN 16 result.

**bill:** a no-trump range read right is information about honours at every decision, but for one call in a few auctions; E9-13 stays offline.
