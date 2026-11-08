# Retrofitting BEN auctions and training on the reusable games

**Result:** 608 of the original 10,000 trajectories are reusable. A controlled
six-run belief-model experiment on that subset did not improve validation loss
over the existing capacity-balanced ownership prior. No playing-strength gain
was measured and no model was deployed.

## Bidding and reuse

All 10,000 original deals were bid by the pinned external BEN neural network,
with search/DDS disabled, batching 128 deals. The bidder sees only its own hand,
public auction prefix, dealer and vulnerability. The run took **41.546 seconds**
inside the bidding loop (model import/load excluded), completing 105,421 calls
at 240.70 auctions/second with no failures. The first 128 checked decisions had
identical batched/scalar probabilities and selected calls. This is an implemented
batched neural-only bidder measurement, not the earlier HTTP or full-search rate.

| Classification | Deals |
|---|---:|
| Exact contract, including declarer | 201 |
| Same strain/declarer, different level or doubling | 407 |
| Fresh play required | 9,361 |
| Passed out | 31 |
| Same strain, regardless of declarer (overlapping diagnostic) | 2,034 |

The original policy maximized tricks and ignored auctions. Its behavior therefore
does not depend on contract level or doubling. Same strain alone is insufficient:
changing declarer changes dummy and the opening leader. Reused games retain their
actions/behavior probabilities and trick estimates, but public auction/contract,
duplicate scores, observations and training labels were reconstructed and legally
replayed. Original files were not modified. The 200 reserved evaluation deals are
disjoint from this collection. Passed-out deals remain auction-only records.

The reusable set has **31,616 pre-action rows**, but only **608 independent deals**.
It is selected by agreement with the synthetic contract and cannot be assumed
representative of the full BEN-auction distribution.

## Predeclared training comparison

The original deal-level split was retained: **503 train / 51 validation / 54 test**.
Same architecture and initialization seeds 731/732/733 in both conditions:

* **No auction:** play observations and final contract, auction tokens zeroed.
* **With auction:** identical inputs plus the ordered, actual BEN auction.

The network has **22,676 parameters**, ordered embeddings, two 16-unit hidden
layers, dropout 0.15, and residual ownership logits over the capacity prior.
It uses uncertain-card cross entropy, AdamW (learning rate .001, weight decay
.001), batch size 512, maximum 60 epochs and patience 8. No suit augmentation
was applied to real bidding conventions. All six fits completed before any
test metrics were computed. Total fitting/final evaluation time was 43.23 seconds,
excluding preprocessing and TensorFlow startup.

## Outcome

| Quantity | Result |
|---|---:|
| Prior training NLL | 0.70720 |
| Final training NLL, six runs | 0.6013–0.6096 |
| Prior validation NLL | 0.70928 |
| Best trained validation NLL, six runs | 0.71176–0.71343 (worse) |
| Selected checkpoint, all six runs | Epoch 0 (unchanged prior) |
| Selected test NLL, either condition | 0.70668 |
| Selected test ownership accuracy | 52.33% |
| Test uncertain-card labels | 34,793 across 54 deals |

All runs stopped after eight epochs without a validation improvement. Training
loss fell substantially: the networks could fit these examples, but that fit
did not generalize better than the prior. Because every selected residual stayed
zero, the selected test predictions are identical up to floating-point rounding.
Any zero-width paired interval here describes identical selected predictors,
not evidence that bidding has intrinsically zero value. The stored `best.keras`
files are deliberately epoch-zero baseline checkpoints, not promoted trained bots.

This is a negative pilot result for this architecture/data size. It does not
establish that 608 deals are universally insufficient, that auctions contain
no useful information, or that a different architecture could not learn from them.
It does not establish playing strength, which needs a separate held-out arena.

## Next dataset

The 9,361 nonmatching BEN contracts are saved in `replay-required.jsonl` for fresh
play. They have **not** been replayed in this experiment. Completing that queue
would yield 9,969 auction-plus-play deals and 31 auction-only passouts. The original
synthetic-contract trajectories remain separately available. Keep all versions
of each deal in the same split; test results from this pilot must not guide
further tuning on these same 54 test deals.

Seven focused tests pass: actual PIMC move/value invariance to level/doubling,
relabel/replay and score updates, split/label preservation, original immutability,
wrong-declarer rejection, score-objective rejection, passout handling, context
validation and ordered-auction encoding with explicit overlength rejection.

Source/reproduction: [REAUCTION.md](../docs/REAUCTION.md). Bulk auctions, reused
episodes, models and detailed metrics are archived outside Git. BEN attribution
and model/config hashes are retained in the archive. BEN is GPL-3.0; no BEN source
or pretrained weights are redistributed by this branch. Original DDS licensing
and project credits remain intact. Max Schireson directed the experiment;
ChatGPT/Codex assisted with implementation, validation and analysis.
