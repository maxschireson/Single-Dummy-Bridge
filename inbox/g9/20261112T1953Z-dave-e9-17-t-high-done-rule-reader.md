E9-17 t-high done: rule reader minus scaled net -0.10 (0.14) IMPs; prediction (+0.1) not met; t-high's rule holds 93%

dave, 12 Nov 19:53 UTC. Task E9-17.

From dave, 12 Nov 19:58 UTC. Task E9-17. t-high's three matches are done: 400 deals each, the same deals (seed 917). t-low is under way and t-random follows; both should be done by about 02:30 UTC.

Native IMPs a board from the reader's side. Common is identical, because every bot bids alike and all 400 deals reached the same contract in each pair:

| Reader against t-high | Mean (SE) |
| --- | --- |
| `r9t-32` (rule reader) | +0.542 (0.210) |
| `8x-32` (net scaled by 0.2) | +0.640 (0.197) |
| `8p-32` (net in full) | +0.312 (0.220) |

| Paired by deal, 400 deals | Difference (SE) | Prediction |
| --- | --- | --- |
| `r9t-32` minus `8x-32` | -0.098 (0.142) | +0.1 or more: not met; 95% interval about -0.38 to +0.18 |
| `r9t-32` minus `8p-32` | +0.230 (0.199) | |
| `8x-32` minus `8p-32` | +0.328 (0.205) | g8 measured +0.36 (0.13) |

**sam's check** on r9t-32~t-high's records: t-high's spot is the highest of its class in 93% of the four situations' plays (1,278 occasions; declarer's lead 0.92, first discard 0.96, partner's lead 0.92, trump 0.91). The table I gave the reader says 100%, with a 5% even floor. So in about 7% of occasions the true layout is marked down by roughly log(0.05/n) because t-high's tie set was smaller than its class. That is one candidate reason the rule reader does not beat the scaled net here; I have not tested it.

A table at the measured 0.93 would test it, as a labelled post-hoc variant. I have not added it: it would go past the registered cap of 3,600 boards, and it needs your approval.
