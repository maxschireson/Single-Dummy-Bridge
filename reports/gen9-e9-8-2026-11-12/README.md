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
