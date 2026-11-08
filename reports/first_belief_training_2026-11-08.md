# Initial belief training — 8 November 2026

Training began only after the full 10,000-independent-deal audit passed. Two
90,856-parameter CPU fits were completed. Neither improved on the diagnostic
capacity-balanced ownership prior on validation; no model was deployed and no
playing-strength claim is made.

## Data and protocol

- 7,993 training deals (415,636 positions), 1,008 validation deals (52,416
  positions), 999 test deals. Original grouped splits were preserved.
- 654,114 uncertain hidden-card labels in validation after hard-known/forced
  ownership is masked out. Correlated positions are not independent samples.
- Inputs: legal pre-action known cards, ordered card/seat play history, public
  context, voids and remaining hand sizes. Privileged ownership/outcome/behavior
  labels and identifiers never enter the encoder. Auctions are excluded because
  this corpus uses synthetic, hand-uninformative auctions.
- Ordered embeddings plus Dense(80), dropout 0.1, Dense(64), 52x4 ownership
  logits. AdamW, batch 1,024, learning rate 0.001, seed 20261108, four CPU threads.
  TensorFlow 2.21.0. Up to 20 epochs; early stopping after four validation misses.
- Test performance was not evaluated or used for selection. NPZ split groups,
  counts and hashes were checked; a further 1,560-row spot check across all 30
  exports matched the already-audited JSON observations and true owners exactly.

## Results

Lower NLL/Brier is better. These are supervised validation diagnostics, not a
comparison against the actual constrained deal sampler or a bridge strength test.

| Variant | Validation NLL | Ownership accuracy | Brier |
|---|---:|---:|---:|
| Uniform legal-owner support | 0.717515 | 49.15% | 0.510017 |
| Approximate capacity-balanced prior | 0.707598 | 52.07% | 0.501253 |
| Plain MLP, best trained epoch (1) | 0.721537 | 49.49% | 0.513906 |
| Prior residual + symmetry augmentation, best trained epoch (4) | 0.711238 | 51.65% | 0.504735 |

The plain run stopped after five epochs in 47.75 seconds of fit/evaluation time;
training NLL fell to 0.661902 while validation worsened to 0.763247. The residual
run stopped after four epochs in 91.38 seconds, including first-epoch prior-cache
construction. It used random seat rotations and suit permutations per training
shard/epoch. Its selected `best.keras` is explicitly **epoch zero**, the
zero-correction prior, because every learned checkpoint was worse. The plain
run's best checkpoint is a trained model, but worse than both diagnostic priors.
Startup, initial validation and provenance checks are outside these timings.

This establishes that the trainer works and exposes overfitting. It does not
establish that more data alone will solve it. Next experiments should compare
smaller/shared-feature encoders and learning curves by independent deal count,
and add genuine hand-dependent auctions. An engineering starting budget is
50,000–100,000 cheap auctions, with separate development/test deal groups, before
committing to large expensive full-play collections. All BEN-calibration deals
remain excluded. New auctions cannot be attached to old trajectories played
under different contracts.

Max has approved weaker/faster bidding for data generation. Neural-only BEN is
a useful first source; rules-based or other systems can add diversity later.
Record source/version/system/config so a belief model can account for bidding
style. Full-search BEN remains a separate benchmark configuration.

For policy-selector training, branch near-equal PIMC choices from identical
positions and compare continuations. Initially budget roughly 80% of collection
compute to fresh deals and 20% to branches/replays, then measure utility. All
branches remain in the original deal group and never count as new independent
deals. Replays also diversify belief histories, but cannot replace new hands.

## Fast bidding probe

BEN's supported `search_threshold=-1`, `check_final_contract=False` and
`no_samples_when_no_search=True` select its best legal neural proposal without
sampling/DDS. On seven selected requests, full search took 27.28 seconds versus
1.95 seconds for this mode, with zero sampled worlds/DDS solves in the latter.
The search timing includes cProfile instrumentation and the fast run does not;
this is an indicative selected-request comparison, not a controlled population
benchmark. Bids changed on one of seven requests. Bidding strength is unmeasured.
Both paths include cold graph/shape initialization. No PIMC play samples were
reduced. The next optimization is to batch independent bidding requests and
avoid auxiliary hand-inference output when only the chosen call is needed.

## Validation and artifacts

Seven focused tests passed: privileged-field invariance, ordered history,
impossible-owner masking, capacity conservation in a simple case, seat/suit
transformation and label alignment, masked-loss gradients, and model save/load.
No bulk data, weights or training logs are committed to Git. Model artifacts
include source snapshots, input checksums, run manifests, validation histories
and selected checkpoints. See `docs/TRAINING_PLAN.md` for reproduction.

[Download training artifacts](https://chatgpt.com/library?file_id=libfile_fde3_f-7b95af3856dc81919f0835d4b397fde4_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).
