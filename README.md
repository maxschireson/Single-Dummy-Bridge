# SiD net S_0: training outputs

Research data, not a feed; never merge. Made by `training/sid-net-s0-20261113/chain.sh` on
`research/sid-net-s0-20261113` (source and settings in `logs/timeline.log`; steps 1 and 2 of `experiments/sid_loop/SPEC.md`).

- `runs/s0`: `policy.npz` (the epoch with the best held-out card log-loss), every epoch, `metrics.json`.
- `e1/`: the student against the exact solver on held-out boards (`scripts/sid_e1.py`).
- `labels/`, `labelsB/`: the label sidecars of the training episodes and of the held-out ones (`--full`), as tar parts
  of `<episode blob id>.npz`; `manifest.json` says what they were made with, `stats.jsonl` what each episode cost.
- `data/`: the fetch manifests (the training episodes are those at the tips of rollout net v2's last fetch) and label statistics.
- `logs/`: every stage.
