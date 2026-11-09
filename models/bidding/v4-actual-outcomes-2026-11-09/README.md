# Actual-outcome bidder candidate

This is the six-pass actual-outcome candidate, not the unweighted control.
It remains out of the arena. All chunks are at most 512 KiB.

From the repository root:

```bash
python scripts/restore_actual_bidder.py models/bidding/v4-actual-outcomes-2026-11-09 --output restored-actual-bidding
```

`candidate.keras` is the inference actor. `resume.tar.gz` includes its selected
TensorFlow model/Adam state, parent architecture, actual outcome inputs,
partition, provenance, training baseline and targets, and validation results.
The selected checkpoint prefix is specified in `manifest.json`. To restore it,
load the archived `parent.keras` with `Policy.load(..., critic=True)`, construct
`PPO` with an actor-only parent anchor, and call `restore` on that prefix.
No new neural value network is deployed.

See [training notes](../../../reports/gen4_model_training_notes_2026-11-09.md)
and [results](../../../reports/bidding_actual_outcomes_2026-11-09.md). The control
fits held-out data slightly better; neither model has an actual-play strength
result. The published candidate is an experiment, not a proven stronger bidder.
