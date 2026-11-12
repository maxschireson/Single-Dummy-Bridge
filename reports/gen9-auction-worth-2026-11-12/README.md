# What the auction reading is worth in tricks (house auctions)

12 November 2026, g9. A double-dummy proxy on p41's published layouts and solves, not played boards.

## Question

Gen 9's auction readers were measured in nats of the true layout's weight at the opening lead (a replayed bidder
+0.69 nats a seat over the hand-fit scorer; a card +2.5 nats over not reading). Two sandbox matches then showed
little. Before more box time goes to auction readers: how many tricks is the whole auction reading worth?

## Answer

On 530 recorded house tables (21,417 decisions after the opening lead, 329 deals), with the prototype's settings and
the v4 policy net, double-dummy tricks a board (the four seats of one table):

| Reading | Tricks given up a board |
| --- | ---: |
| Nothing | 0.856 |
| The auction alone (hand-fit scorer) | 0.732 |
| The play alone (v4) | 0.653 |
| Both (the prototype `8p-32`) | 0.546 |

- **The whole auction reading is worth +0.107 +- 0.019 tricks a board once the play is read** (0.653 against 0.546),
  about 0.4 IMPs at 3.6 IMPs a trick, and +0.124 +- 0.026 with no play reading.
- The play reading is worth +0.185 +- 0.029 given the auction (p41's figure, reproduced).
- What is left to a player who sees every card is 0.546 tricks a board, about 2 IMPs. A test bot that is told the
  deal beat the prototype by +2.36 +- 0.61 IMPs over 39 boards.

By stage, the auction's worth given the play reading:

| | Tricks 1-2 | 3-4 | 5-6 | 7-9 | 10-13 | Declarer deciding | Defender deciding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tricks a board | +0.021 +- 0.007 | +0.031 +- 0.010 | +0.023 +- 0.008 | +0.022 +- 0.010 | +0.009 +- 0.005 | +0.054 +- 0.013 | +0.053 +- 0.014 |

## What follows for Gen 9

1. **A better reading of an auction we already read is worth a few hundredths of a trick at most.** The replayed
   bidder adds about a fifth to the scorer's nats at the lead; a fifth of 0.107 is 0.02 tricks, under 0.1 IMPs. A
   1,600-board match has a standard error of about 0.08 IMPs and cannot see it. `e9-11-r8` moves down the box queue;
   the bench scores replay directly (G9-X2).
2. **Reading a stranger's auction at all is the prize, and it is about 0.4 IMPs a board**, more if reading them with
   the wrong net is worse than not reading them, which this study does not measure. That is what the `card`
   profile, `flat` and system detection are for.
3. Together with the Gen 8 session's result on carding (reading a player whose spots the net does not model at
   full weight costs 0.35 to 0.45 IMPs a board), being right about a stranger is worth up to about 0.8 IMPs a board
   over treating it as a house bot. Against house bots the player model has almost nothing to add.

## Method

`auction_worth.py` in this folder, with `scripts/gen8_reading_bench.py` (branch `feature/gen8-p41-20261112` at
`61796a2`) and the pools of `transfer/gen8-p41-reading-pools-20261112`.

Every stored set of layouts was drawn by the scorer's auction weights (before the deal list, and deal lists of more
than 1,024 layouts) or carries them as its prior (complete deal lists). "No auction" divides them out: the prior
becomes `prior - scorer`, with `scorer` from the `scw` files. The cost is `score`'s engine-way cost (32 layouts
resampled before the deal list, the listed layouts after), the mean over eight resampling offsets. Standard errors
take the deal family as the unit; a band's figure counts decisions outside the band as zero, so the bands add up.

Dividing the scorer out of a pool that the scorer drew is an importance-weighted estimate: layouts the scorer
dislikes are rare in the pool. Two checks: the median effective number of layouts without the auction is 157, 131
and 126 of 512 at tricks 1-2, 3-4 and 5-6; and the estimate before the deal list does not move with the pool size
(`auction_cover.py`: +0.075 +- 0.015 with 512 layouts, +0.075 +- 0.013 with 256, +0.069 +- 0.014 with 128). If
coverage still biases it, the bias is toward too small a figure.

The nats column that the script prints (the scorer's own gain on the true layout) is not used here: before the
deal list it is estimated from the scorer's own draws and runs low. On complete deal lists, where it is exact, it
is +1.24 +- 0.04 nats at tricks 7 to 9 and +0.56 +- 0.02 at tricks 10 to 13, against 3.6 measured at trick 1 by
bill: the auction says less about what is left as the hands narrow.

## Limits

House auctions and house card play only. Double dummy stands in for the result. No tree and no tie-break. One net
(v4).
