# Dense belief size and consequence-weighting comparison

Four research candidates from the same frozen policy-clean dataset. Each starts
from v4 predictions, resets AdamW, and trains for three epochs. All four use the
same validation objective to select a checkpoint, including epoch zero.

| Directory | Dense widths | Parameters | Card loss |
|---|---|---:|---|
| `current_ordinary` | 256, 128 | 308,726 | Ordinary ownership cross entropy |
| `large_ordinary` | 512, 256 | 682,614 | Ordinary ownership cross entropy |
| `current_consequence` | 256, 128 | 308,726 | Consequence-weighted ownership cross entropy |
| `large_consequence` | 512, 256 | 682,614 | Consequence-weighted ownership cross entropy |

Run `python restore.py` in this directory to reconstruct each selected
`belief.npz`. The script verifies every 512 KiB part and the reconstructed model
against `manifest.json`. These are inference exports; selected TensorFlow model
and AdamW checkpoints are retained separately in the recovery bundle.

Recovery bundle: [Belief_Size_Loss_Final_2026-11-10.zip](https://chatgpt.com/library?file_id=libfile_fde3_f-ee8f42e1a3888191bf5eebd25c003528_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal)
(owner access required). SHA256:
`0a3285b09151223469943d341e99e4d291f57bce0a21d8722a3c2314af5b752c`.
It contains all four selected model/optimizer checkpoints, all epoch validation
records, the frozen recent data, and references to historical replay and source
recovery. All four selected checkpoints are from epoch 1, with 494 AdamW steps.

See the [results report](../../../reports/belief_size_loss_2026-11-10.md) and
[complete metrics](../../../reports/belief_size_loss_2026-11-10.json) for epoch
selection, fixed-epoch comparisons, family-paired uncertainty, and timings.

Training implementation: commit
`e7bc310cf8b0a701f73d80df706e56454a23bf54` on
`research/belief-v5-impactful-cards`. Run:
`runs/belief-size-loss-v2-20261110`. The earlier run without `v2` in its directory
name was superseded after correcting dropout reproducibility across process
restarts and is excluded from the comparison.

No model has been promoted to the arena. Reserved test families remain
unevaluated. Attention remains paused.
