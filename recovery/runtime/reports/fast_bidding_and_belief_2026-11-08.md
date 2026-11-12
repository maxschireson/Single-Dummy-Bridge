# Fast bidding and first auction belief model — 8 November 2026

A fast BEN neural-only collector produced **50,000 independent complete
auctions in 199.74 seconds** on the current CPU worker (excluding model startup).
A **46,582-parameter** belief model then trained for 20 epochs in **107.56 seconds**.
It improved held-out validation ownership predictions over the uniform prior,
and removing auction inputs removed the gain. No bot-strength result is claimed.

## Collection and source policy

- BEN revision `9b5f43104aeac713a80b73513f2f2d6daf9f8769`, model
  `GIB-BBO-8742_2026-10-23-E30.keras`; exact model/config hashes in the archive.
- Greedy best legal neural call; search, sampling, DDS, rescue bidding and
  auxiliary hand-inference output are disabled. Calls of equal sequence length
  are batched across independent deals (up to 128). Each model input receives
  only the acting bidder's own hand and public auction prefix.
- This deliberately changes the policy relative to full-search BEN. It is
  suitable for learning this bidding style; its playing/bidding strength and
  generalization to other systems or human conventions are not established.
- A 1,000-auction development run completed in 4.13 seconds. Thirty-two batched
  probability vectors matched scalar inference exactly. Sixty-four additional
  calls sampled across early/middle/late stages matched ordinary neural-only
  BEN's chosen calls. The large run also checked its first 32 scalar calls.
- The sustained large-run rate was 250.32 auctions/second; 529,803 calls,
  167 passed-out auctions, zero failed auctions. Mean/max length 10.60/32 calls.
  Opening 1NT occurred 6,071 times, with mean 15.82 HCP, a basic informativeness
  check rather than a bidding-quality assessment.
- The original 10,000 self-play deals, 200 reserved BEN calibration deals and
  1,000 development auctions were excluded by original-deal hash. All complete
  auctions/contracts/transcripts were independently validated, with zero
  repeated deals or cross-split groups. A setup-path error before generation
  produced no auctions; it was fixed before the successful large run.

These are **50,000 auctions, not 50,000 played games**. The original 10,000
complete-game collection remains separately audited and preserved. PIMC play
still uses 32 worlds and its original exploration settings.

## Dataset and model

| Split | Independent deals | Observation rows | Uncertain-card targets |
|---|---:|---:|---:|
| Train | 39,951 | 319,608 | 12,464,712 |
| Validation | 5,023 | 40,184 | 1,567,176 |
| Test | 5,026 | 40,208 | 1,568,112 |
| Total | 50,000 | 400,000 | 15,600,000 |

Each deal supplies four completed-auction views and one sampled pre-call view
per seat. Inputs are own hand, derived own shape/HCP, public vulnerability,
relative dealer, ordered calls and relative callers. Prefix examples receive
neither future calls nor the eventual contract. Hidden owners are separate
targets; known own cards are excluded from loss. Original deal groups govern
all splits. Source board files contain privileged full hands and must never be
used directly as model inputs.

The model has 4-dimensional call embeddings, 2-dimensional caller embeddings,
Dense(64), dropout 0.15, Dense(64), and 52x4 ownership logits. Seats are relative
to the observer. Hard masks exclude impossible owners. AdamW, learning rate
0.001, weight decay 0.0001, batch 1,024, four CPU threads, seed 20261109,
TensorFlow 2.21.0. The best validation checkpoint was epoch 20, the predeclared
budget limit; convergence is not established. Test metrics were not evaluated
or used for model selection. This model conditions on bidding only, not play.

## Validation results

| Input/model | Ownership accuracy | NLL (lower better) | Brier (lower better) |
|---|---:|---:|---:|
| Uniform unknown-owner prior | 33.33% | 1.098612 | 0.666667 |
| Learned, all views | 42.78% | 1.058717 | 0.639863 |
| Learned, pre-call prefixes | 41.87% | 1.063668 | 0.643114 |
| Learned, completed auctions | 43.68% | 1.053766 | 0.636611 |
| Same checkpoint with auction removed | 33.38% | 1.099631 | 0.667349 |

The ablation removes calls, caller sequence and prefix length. It is a
validation diagnostic; it is not a separate retraining experiment. Validation
is grouped into 5,023 independent deals; the 1.57 million labels are correlated.
The uniform baseline is intentionally simple. This is evidence of learning
auction information, not evidence of surpassing BEN's existing belief machinery
or improving our PIMC bot. Future evaluation should compare informative priors,
calibration, legal joint samples and card-play strength at equal compute.

## Next integration

Play new trajectories under the actual frozen auctions and then train a
combined bidding/play belief model. Do not attach these auctions to old games
played under different contracts. Keep full-search BEN calibration separate.
For policy selection, branch near-equal choices and preserve original deal
split groups; repeated trajectories never count as new independent deals.

## Reproduction and checks

The dataset archive contains original episodes, frozen playable boards,
manifest/config/model hashes, summary, audit, three input/target NPZ exports,
exclusion registry, source and per-file hashes. The model archive contains
selected/final checkpoints, run manifest, history, metrics and exact source
snapshots. No weights, games, binary arrays or logs are committed to Git.

Run the collector with an external pinned BEN checkout and its Python environment:

```sh
python scripts/collect_ben_auctions.py --ben-dir /path/to/ben \
  --config /path/to/neural-only.conf --exclude-groups /path/to/exclusions.json \
  --seed 20261302 --count 50000 --batch-size 128 --verify-scalar 32 \
  --out results/auctions
python scripts/prepare_auction_belief.py --data results/auctions \
  --exclude-groups /path/to/exclusions.json --expected-deals 50000 \
  --out results/auction-tensors
python scripts/train_auction_belief.py --data results/auction-tensors \
  --out results/auction-model --epochs 20 --patience 4 --threads 4
```

Seven play-belief tests and three auction-encoder tests passed. Additional
integration evidence includes complete auction replay, exact NPZ/JSON spot
checks of 1,560 original-play rows, cross-split audits, batched/scalar bidding
checks and completed end-to-end export/training. No claims rely on Apple
hardware performance extrapolation.


[Download the 50,000-auction dataset](https://chatgpt.com/library?file_id=libfile_fde3_f-9889c07d7e888191b6424b52b2051cd0_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal)
and [trained model and exact run sources](https://chatgpt.com/library?file_id=libfile_fde3_f-48b414c0687c8191b93ce4f1c5a62861_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).

Dataset archive SHA256:
`4cfa559989b7eecd4d3af2da7cd7e32701f5238a2ade4729f2b46d3142c7e8e7`.
Model archive SHA256:
`3737ab5999e4998bc3edcd316e41cd4591ce43f9a3c53ee20e0e680512f1ea43`.
