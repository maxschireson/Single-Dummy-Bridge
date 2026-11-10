# Dense v5 consequential-card belief candidate

This directory contains the selected epoch-2 model from the policy-clean dense
v5 belief experiment. It has the same 308,726-parameter architecture as v4.

- `belief.npz.part*`: 512 KB parts of the portable NumPy inference weights.
- `selected-checkpoint/ckpt-2.*`: 512 KB parts of the TensorFlow model plus
  Adam optimizer state, along with its small index and checkpoint files.
- `result-summary.json`: compact metrics, hashes and data counts.
- `manifest.json` and `restore.py`: verify every part and reconstruct the two
  large files. Run `python restore.py` from this directory.

The full recipe and interpretation are in
`reports/dense_impact_belief_v5_result_2026-11-10.md`. The selected candidate
narrowly improved the composite validation objective but did not improve NLL on
the specifically upweighted consequential-card subset. It is retained for
research and is not promoted to the arena. Reserved test families were never
prepared or evaluated.
