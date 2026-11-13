# E9-8: what replaying the bidder is worth over the hand-fit scorer (12 November 2026)

**Prediction evidence; `team/gen9:experiments/E9-8.md`.** Code: `scripts/gen9_e9_8.py` (replay through
`bridge_harness/cards/match.lstm_step_logits`, the house LSTM teacher-forced on the actual auction) on
`feature/gen9-bidding-cards`. Data: `gen6.json`, `gen5.json`. 400 deals each, all four seats bid by the
house bidder; every seat read by its left-hand opponent over 256 uniform random hands from the 39 cards it
cannot see plus the true hand (1,600 decisions). Gain = log w(true) − log mean w(pool), nats.

| Auctions by | S (scorer v0) | replay, argmax, eps 0.02 | eps 0.1 | replay, softmax | scorer + replay softmax |
| --- | ---: | ---: | ---: | ---: | ---: |
| house Gen 6 (the arena's bidder) | 2.13 ± .04 | 2.56 ± .04 | 1.98 ± .03 | **2.82 ± .06** | 2.93 ± .08 |
| house Gen 5 (the scorer's training bidder) | 2.16 ± .04 | 2.53 ± .04 | 1.96 ± .03 | **2.75 ± .06** | 2.86 ± .07 |

By what the seat did (Gen 6; Gen 5 alike): only passed (514 seats) S 0.67, replay 0.75; one bid (548)
S 2.49, replay 2.98; two or more bids (538) S 3.16, replay **4.62**.

- The true hand never failed its own replay (0 of 3,200).
- Replay with the bidder's softmax is worth +0.69 nats on Gen 6 auctions and +0.60 on Gen 5 over the
  scorer, +1.4 for seats that bid twice or more. The hypothesis's 1 nat is reached only for those seats.
  The scorer adds little once replay is in (+0.1).
- The softmax is better than the argmax indicator: the bidders are close to deterministic but not
  exactly (an indicator at eps 0.1 is worse than the scorer).
- Cost, one sandbox core: 0.030 s to replay one seat over a pool of 257, against 0.004 s for the scorer;
  a board's auction is fixed during play, so replay runs once per hidden seat per board.
- The scorer as a proposal: a pool of 512 drawn from 8,192 uniform hands with probability proportional
  to exp(S) keeps on average 40% (Gen 6) and 46% (Gen 5) of the replay posterior's mass (60 leader
  views each). The scorer is a weak proposal for the exact reading; a pool drawn by it then reweighted
  by replay loses more than half of the posterior.

## Supplement, 12 Nov 08:25 UTC: a floor on the replay's likelihood

sam's review of G9-B7 (08:17): with no floor, a call the bidder gives almost no probability can rule a
layout out at high weight on one profile. `ProfileReplay` and `ReplayReader` now default to eps 0.02:
P(call) = 0.98 p + 0.02 / (legal calls). What the floor costs on the bidder's own auctions, and on
auctions of the other house net (a near mis-mapping), 200 deals (800 seat readings), pool 256, seed 8801
(`gen6-floor.json`, `gen5-by-gen6-floor.json`; `scripts/gen9_e9_8.py --replay`):

| Auctions bid by / replayed by | S | R-soft (eps 0) | R-soft eps 0.02 | R-soft eps 0.05 | seats bidding 2+: eps 0 / 0.02 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gen 6 / Gen 6 | 2.18 ± 0.07 | 2.84 ± 0.10 | 2.69 ± 0.07 | 2.65 ± 0.07 | 4.80 / 4.39 |
| Gen 5 / Gen 6 | 2.20 ± 0.07 | 2.76 ± 0.10 | 2.60 ± 0.08 | 2.56 ± 0.07 | 4.81 / 4.38 |

- The floor at 0.02 costs 0.15-0.16 nats a seat reading (0.4 on seats that bid twice or more), about a
  fifth of the replay's gain over the scorer; 0.05 costs a little more (0.19-0.20). Differences are paired
  on the same pools; the ± are the per-reader standard errors, not of the difference.
- Replaying Gen 6 on Gen 5's auctions loses only 0.08 nats against Gen 6 on its own: the two house nets
  bid nearly the same system, so a mis-mapping between them costs little.
- No catastrophic tail appeared at eps 0 in these 1,600 readings (the mean at eps 0 is above the floored
  means), including Gen 5's auctions read by Gen 6 (G9-D6's guest-b if it were mapped to house-gen6).
  The case the floor guards against, a player who psychs or strays from a held profile while weighted
  near 1 on it, is not in this sample.
- Not measured: floors below 0.02, where most of the cost may be recovered.
