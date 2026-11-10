# Residual belief attention: measured training estimate

Budget **30–40 minutes for three full epochs**, with the first full validation
result after approximately **10–12 minutes**, on the current CPU with two
TensorFlow compute threads. The measured forward/backward and validation compute
estimate is 8.88 minutes per epoch, or 26.64 minutes for three; the budget includes
allowance for loading, reporting and checkpointing. A matched dense control and
final export verification would add several minutes. This is an estimate, not a
completed full-data training run.

The prototype retains the selected dense v5 network and adds one 64-wide,
two-head cross-attention block. Its 52 card queries attend to 52 public-card
tokens, 64 ordered auction slots and one public-context token. The correction
outputs four ownership logits per card and starts at zero. There are **357,754
parameters**, including **49,028 new parameters** above the dense model's 308,726.

The timing screen used batch size 128, eight warmup updates and 100 measured
updates, cycling actual training batches from historical bidding, historical
BEN, historical play and recent clean play. Mean update time was **64.97 ms**;
mean forward-only time was **26.00 ms**. The frozen data requires 7,807 training
batches and 987 validation batches per epoch at this batch size.

The initial maximum logit difference from dense v5 was below **6e-7** in each
of the four domains. The correction readout changed during the disposable
timing updates and the loss stayed finite. No benchmark model was retained or
selected. This screen did not access reserved test data or restart the paused
standalone attention run.

Limitations: timing uses cached tensors and excludes shard I/O, family-level
metric aggregation, startup and checkpoint writes. Its scalar weighting is
simplified for timing; a full comparison must preserve the frozen
family/domain/consequential-card objective. The first measured epoch should
replace this extrapolation with an observed ETA.

Parent SHA256:
`99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a`.
Dataset SHA256:
`188d3ebe78e2c448b2a9f244d680a89e69f0aa787ee305477b35114e619aab76`.

Reproduce the timing screen:

```sh
python -u scripts/profile_residual_attention_belief.py \
  --data runs/dense-impact-v5-clean-20261109 \
  --parent runs/belief-size-loss-v2-20261110/current_consequence/best.npz \
  --out runs/belief-residual-attention-profile-20261110/batch128.json \
  --batch-size 128 --steps 100 --threads 2
```
