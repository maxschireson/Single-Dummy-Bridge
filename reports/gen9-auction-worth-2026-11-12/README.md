# What reading is worth in tricks: the auction, suit lengths, honours (house tables)

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

## What information is worth, by kind and by place

The same pools, on top of the prototype's reading (`aimed_shape.py`, `aimed_subsets.py`). Each stored layout's weight
is multiplied by `exp(-k x d)`, where `d` counts what the layout has wrong: the suits in which it gives a hidden hand
the wrong length ("suit lengths"), or the honours (T to A) it gives to the wrong hand. `k` is set to give the stated
gain in the true layout's log weight a helped decision; "known" is a large `k`, as far as the pool holds such layouts.

Where the prototype gives up its 0.546 tricks a board, and what knowing would save there:

| Decisions | A board | Given up | Suit lengths known | Honours known |
| --- | ---: | ---: | ---: | ---: |
| Declarer deciding, tricks 1 to 6 | 10.6 | 0.250 | +0.128 +- 0.023 | +0.091 +- 0.028 |
| A defender deciding, tricks 1 to 6 | 9.5 | 0.187 | +0.085 +- 0.017 | +0.080 +- 0.019 |
| Declarer deciding, tricks 7 to 13 | | 0.086 | +0.058 +- 0.013 | +0.067 +- 0.014 |
| A defender deciding, tricks 7 to 13 | | 0.023 | +0.015 +- 0.005 | +0.011 +- 0.007 |
| Every decision | 40.4 | 0.546 | +0.286 +- 0.032 | +0.249 +- 0.038 |

What a partial gain is worth, tricks a board:

| Helped decisions | Kind | +0.3 nats a decision | +0.7 nats a decision |
| --- | --- | ---: | ---: |
| Every decision | suit lengths | +0.078 +- 0.012 | +0.186 +- 0.021 |
| Every decision | honours | +0.071 +- 0.010 | +0.153 +- 0.019 |
| Every decision | small cards one by one | +0.013 +- 0.005 | +0.034 +- 0.008 |
| Declarer, tricks 1 to 6 | suit lengths | +0.011 +- 0.005 | +0.034 +- 0.007 |
| Declarer, tricks 1 to 6 | honours | +0.017 +- 0.005 | +0.052 +- 0.010 |
| A defender, tricks 1 to 6 | suit lengths | +0.020 +- 0.005 | +0.043 +- 0.010 |
| A defender, tricks 1 to 6 | honours | +0.012 +- 0.005 | +0.027 +- 0.007 |

Reading these:

- **Four fifths of what imperfect information costs is at tricks 1 to 6** (0.437 of 0.546 tricks a board), and more
  of it with declarer than with the defenders.
- **A nat about suit lengths is worth as much as a nat about honours.** A nat spread over the small cards one by
  one is worth a fifth of that (p41's finding); what matters about small cards is how many each hand holds.
- **Count read perfectly by declarer through trick 6 would be worth 0.13 tricks a board, about 0.46 IMPs.** That is
  the ceiling for reading a defender's count signals. A reader that adds 0.3 nats there (the fitted model of BEN's
  signals adds 0.16 to 0.32 over Gen 8) is worth about 0.01 tricks, 0.04 IMPs; one that adds 0.7 nats (a declared
  scheme followed four times in five) about 0.03 to 0.05 tricks, 0.12 to 0.19 IMPs.
- **A defender who knew partner's and declarer's lengths through trick 6** would save 0.085 tricks a board; 0.7 nats
  toward it saves 0.04. That is the size of what our own signals could give our own defence, before what they give
  away to a declarer who reads them.

The proxy's limits apply with more force here: these are single decisions on recorded house play, scored double
dummy, with the rest of the play as recorded.

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
