# Genuine auctions plus original play in unrelated contracts

**Outcome:** this from-scratch ownership model did not improve hidden-card
prediction on validation deals. **This is not a card-playing performance test.**
No tricks/board, IMPs or equal-time playing-strength comparison was run.

## Data and interpretation

All 10,000 original independent deals are used, with the genuine neural-only BEN
auction for the same cards. The original played contract, declarer, dummy,
visibility, actions and ownership labels remain unchanged. Auction tokens are a
separate auxiliary information channel, not a claim that the combined auction
and play are a legal bridge transcript. The original PIMC policy was auction-blind
and maximized tricks. Even a passed-out auction can be auxiliary information for
this synthetic inference task; it is not relabelled as a played passout board.

No new bidding or card play was required. Dealer/vulnerability and exact original
deal hashes bind each auction to its corresponding play. Original files remain
immutable. Preparation checks all 10,000 group identities, split disjointness,
52 rows per deal and ownership-label feasibility. A further 100-position check
across all ten training shards confirmed unchanged observation encodings and
targets, and correct joining of the auxiliary auction.

The split is unchanged: **7,993 train / 1,008 validation / 999 test deals**.
Every original position is used. Test data have appeared in previous experiments,
including 54 deals in the matched608 pilot, so these are exploratory reused-test
results, not fresh confirmatory evidence.

## Comparison

The same **22,676-parameter** model was trained with and without ordered auction
tokens, using seeds 731, 732 and 733. Both conditions see the actual played
contract and all the same play observations. The network predicts remaining
ownership probabilities, using residual logits over the capacity-balanced prior.
It never receives hidden hands, future play, original deal IDs or targets as
inputs. No suit augmentation is applied to real auctions.

Training uses batch size 1,024, AdamW (.001 learning rate, .001 weight decay),
dropout .15, maximum 40 epochs and patience 6. Selection uses all-deal validation
uncertain-card cross entropy (NLL), with the unchanged prior eligible as epoch
zero. All six fits finish before test metrics are computed.

## Results

| Measure | No auction | With auxiliary auction |
|---|---:|---:|
| Best trained validation NLL across seeds | 0.70842–0.71039 | 0.70850–0.71067 |
| Final training NLL across seeds | 0.69478–0.69533 | 0.69280–0.69311 |
| Selected epoch, all seeds | 0 | 0 |
| Selected test NLL | 0.707816 | 0.707816 |
| Selected test ownership accuracy | 52.014% | 52.014% |

The prior's validation NLL is **0.707598**, better than every trained checkpoint.
All runs therefore stopped after six epochs and selected the unchanged prior.
The auction-conditioned model fits training examples slightly better, but this
does not carry over to validation. Test predictions are identical because all
selected residuals are zero. Zero paired differences/intervals here describe
identical selected predictors, not proof of zero intrinsic information in bids.

The test metric covers **650,141 uncertain-card labels across 999 deals**; the
deal is the independent sampling unit. Hard-known ownership is excluded from
loss and accuracy. NLL is the mean negative log probability assigned to the true
remaining owner. It is **not** tricks lost or a bridge score.

Elapsed preprocessing plus fitting/final evaluation: **466.34 seconds**;
fitting/final evaluation alone: **412.46 seconds**, using CPU TensorFlow.
Best and final trained checkpoints are both preserved. The `best.keras` files
are epoch-zero priors; `last.keras` files contain the fitted but worse-validating
models. No checkpoint was deployed to the bot.

## What this establishes

This particular small, from-scratch model did not extract a useful generalizing
improvement from these combined signals. The result does not establish that
the information sources cannot be combined, or distinguish conclusively between
data quantity, representation and optimization as the limiting factor.

A separate auction-only experiment in the concurrent project learned bidding
signal from 50,000 auctions. A reasonable next hypothesis is to preserve that
learned bidding representation and learn corrections from play, rather than
relearn both in this small network. That transfer experiment was not performed
here. Any useful belief model still needs constrained deal sampling and an
equal-time card-playing evaluation before making a strength claim.

Reproduction details: [AUXILIARY_AUCTION_PLAY.md](../docs/AUXILIARY_AUCTION_PLAY.md).
The original 9,361-contract fresh-play queue remains unexecuted by this experiment.
Code/report are in Git; detailed metrics and checkpoints are archived separately.
The existing BEN/DDS attribution and licenses remain intact. Max Schireson
directed the work; ChatGPT/Codex assisted with implementation and analysis.
