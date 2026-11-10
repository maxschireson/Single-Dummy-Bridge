# Layout embedding: first fit, 2026-11-10

The first compact embedding is trained. It learns some held-out DDS action-contrast structure, but the subset-selection gain remains inconclusive. This checkpoint is experimental and has not been promoted.

## Model and objective

150,020 trainable parameters: 445 inputs, dense hidden layers of 256 and 128 units, a 16-dimensional embedding, and a 16-to-52 auxiliary training head. The inference encoder has 149,136 parameters.

Training targets are differences between layouts' centered vectors of all legal-action DDS trick values. Removing each layout's common action-value offset makes the representation sensitive to which action is preferable, rather than only the overall value of a layout. The loss combines within-position pair-distance Huber loss with 0.2 times auxiliary centered-action MSE and a small embedding norm penalty. Seats are actor-relative and suits are randomly permuted during training.

The reducer accepts caller-supplied probability masses. Greedy weighted medoids select representatives and transfer each cluster's total mass to its representative. Optional probability-proportional random selection within each cluster preserves the candidate-pool average in expectation. Do not multiply belief probabilities into samples already drawn from that posterior without accounting for their sampling distribution.

This first encoder does not consume auction/history or belief logits. Its target uses trick contrasts, not contract-dependent IMP utility. Those limitations matter for the eventual playing-strength objective.

## Data and split

| Split | Layouts | Position groups | Original deal families |
|---|---:|---:|---:|
| Training | 181,442 | 4,359 | 396 |
| Validation | 28,344 | 716 | 62 |

The source was 39,636 expensive DDS capture records from the component and supplement runs. Only 10–13 remaining tricks, complete legal-action labels, and clean compatible public trajectories were retained. Episodes involving v4/v4p or unknown bot identities were excluded. Deal-family boundaries inherit the existing clean belief manifest; reserved test families were not prepared or scored. The older unprovenanced 600k-layout DDS cache was not used.

Training layouts are not independent positions: the effective diversity is much smaller than 181k. Captures contain expensive native solves rather than all cache hits, so their distribution is selective. Deduplication does not recover posterior probabilities.

## Fit and validation

Data preparation took 49 seconds. A total of 64 epochs took 213 seconds of fitting and about 218 seconds including the final report, using one CPU thread. The first 16 epochs took 56 seconds. Best validation pair-distance loss occurred at epoch 52.

| Quantity | Untrained | Selected checkpoint |
|---|---:|---:|
| Pair-distance Huber loss | 0.241462 | 0.127054 |

The validation-only compression screen uses 400 position groups from 62 families, reducing 32 to 8 or 64 to 16 layouts with uniform candidate mass. Regret below is the loss in mean DDS tricks relative to choosing the best action on the same complete candidate pool; it is not actual play or IMP gain.

| Selector | Mean regret in tricks | Contrast MSE |
|---|---:|---:|
| Random subset | 0.017702 | 0.009388 |
| Raw card geometry | 0.015865 | 0.011413 |
| Learned embedding medoids | 0.015010 | 0.008928 |
| Learned action-head geometry | 0.017363 | 0.009025 |
| Learned clusters, random within | 0.017363 | 0.010046 |
| Oracle using true DDS labels | 0.001484 | 0.000367 |

For learned medoids versus random, the family-balanced mean regret difference is -0.002271 tricks, with a 95% family-bootstrap interval of [-0.007954, +0.003516]. Group-weighted table means and family-balanced differences use different aggregation weights. This result does not establish a selection gain.

The oracle is unavailable at inference and supplies a diagnostic bound. The reference shares the candidate pool, so this screen cannot test whether a learned 32 beats ordinary 128. It also does not compare the existing top-32 selector. The next decisive evaluation needs 128 candidates from the current belief sampler with its correct weights, top-32 and random-32 controls, an independent high-effort reference, and ultimately paired play.

## Cost and verification

A one-thread benchmark over 200 repetitions measured approximately 0.75 ms to embed 128 layouts plus 1.25 ms to select 32, or 2.0 ms total. Mixed-position rows were used only to measure computation; this is not a quality evaluation.

Five targeted tests passed, covering mass preservation, distinct representatives and tied embeddings, unbiased random-within-cluster selection, common-offset invariance, and suit relabeling. NumPy export predictions agree with PyTorch within 5.97e-7. The source/policy audit covered all 458 retained episodes, and reconstructed legal-card masks match all saved labels.

## Reproduction and recovery

Code branch: [research/layout-embedding-20261110](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/layout-embedding-20261110).

The separate checkpoint bundle contains prepared train/validation data, source and context metadata, audit, configuration, history, selected NumPy weights, and the resumable optimizer checkpoint. Code is maintained in GitHub.

With that bundle extracted at repository root and a Python environment with NumPy and PyTorch:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python scripts/train_layout_embedding.py --data runs/layout-embedding-20261110/data --out runs/layout-embedding-20261110/fit --epochs 64 --threads 1
```

The existing last checkpoint resumes the completed run; use a fresh output directory for a new fit. Training config records the data hash. Best weights are fit/best.npz, selected at epoch 52. The last checkpoint is epoch 64 and is intended for resumption.

The current belief-net research priority was respected: this job used one low-priority CPU thread and changed no production player.
