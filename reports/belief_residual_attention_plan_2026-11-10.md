# Full residual-attention belief comparison

Authorized scope: three full epochs each of a matched dense continuation and a
64-wide, two-head, single-block residual attention extension. Both start from
the selected dense v5 belief checkpoint
`99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a`.

The dataset is frozen at
`188d3ebe78e2c448b2a9f244d680a89e69f0aa787ee305477b35114e619aab76`:
998,425 training positions, 31,120,476 uncertain-card targets and 89,652 families.
Both fits preserve the 50/25/25 play/bidding/BEN objective, recent-family 2x
weight, within-family target normalization and existing consequential-card
weights. No new labels, records, splits or test evaluations are added.

Both fits use fresh AdamW, learning rate 0.0001, weight decay 0.0001, gradient
clip norm 1, batch size 128, the same row order and explicit dense dropout seed.
All layers are trainable. Batch size 128 is shared by both arms; earlier dense
experiments used 2048, so their continuation is not substituted for this control.

Primary comparison: attention minus dense at the fixed third epoch, with paired
family SE. Secondary: each arm's best frozen composite validation score,
including epoch zero, with all ordinary and consequential-card NLL, accuracy
and Brier metrics. If epoch zero wins, report no improvement in that arm's
validation objective. Selection-based comparisons are descriptive.

Each worker processes at most 2,000 minibatches. Model, AdamW, exact dropout RNG
state and data offset are saved every 250 minibatches and at worker boundaries.
The runner serializes workers with locks and retries interrupted processes from
committed state. Use file progress and a nonblocking lock check; process lists
from another exec namespace are not proof of a stopped worker.

Preflight: nonzero portable-export parity, parent prediction preservation and
exact interrupted-versus-continuous model/optimizer updates passed. A separate
one-epoch four-domain smoke fit passed through training, selection, export and
paired reporting for both arms; its quality results are not part of this study.

Run:

```sh
python -u scripts/run_residual_belief.py \
  --run runs/belief-residual-v5-20261110 \
  --data runs/dense-impact-v5-clean-20261109 \
  --parent runs/belief-size-loss-v2-20261110/current_consequence/best.npz
```

The old standalone attention experiment remains stopped. There is no arena
promotion, arena collection, reserved-test evaluation or additional model sweep
in this authorization. Final exports must be checked against selected TensorFlow
checkpoints, optimizer recovery saved, and results published to the existing
research branch. Hybrid inference uses the new residual-attention loader.
