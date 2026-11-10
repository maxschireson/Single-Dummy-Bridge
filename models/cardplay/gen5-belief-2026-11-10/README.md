# Promoted dense v5 belief component

Max authorized promotion on 10 November 2026. This is the selected dense
`current_consequence` checkpoint from epoch 1 of the clean size/loss comparison.
It is the belief component for v5, with 308,726 parameters and dense widths
256/128. The later attention experiment did not improve the selection objective.

Restore from the repository root:

```sh
python models/cardplay/gen5-belief-2026-11-10/restore_belief.py
```

Use `models/cardplay/gen5-belief-2026-11-10/belief.npz` with `belief_kind="public"`.
The existing `bridge_harness.belief_capacity.Weights` NumPy loader and public
belief player support it without a runtime change or TensorFlow dependency.
The script checks every part and the complete model against `manifest.json`.

Model SHA256: `99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a`.
These are exactly the weights used in the completed 150-board belief smoke test.

## Training and validation

Warm-started from v4, with fresh AdamW and consequential-card weighting on the
frozen clean recent-play subset. The fit used 998,425 positions, 31,120,476
uncertain-card targets and 89,652 training families, including historical replay.
The fine-tuning corpus excludes the bad v4/v4p policy on both partnerships and
retains 4b. All three epochs were evaluated; epoch 1 was selected, with unchanged
v4 eligible. The later continuation/attention study retained this starting model.

Relative to v4, the selected composite NLL is 0.86762469 versus 0.86795576.
Recent weighted NLL is 0.67255530 versus 0.67280401: improvement
0.00024872 ± 0.00036225 paired family SE, only 0.69 SE. Recent card-location
accuracy is 60.1732% versus 60.0982%. These are small, uncertain predictive gains.
The 150-board matched play smoke test was −13 ± 28 IMPs (one SE), so improved
playing strength has not been established. Promotion is Max's authorized
operational choice; it does not claim a statistically established play gain.

Selected TensorFlow/NumPy predictions and reconstructed model checksums were
verified. See the [full size/loss results](../../../reports/belief_size_loss_2026-11-10.md),
[play smoke results](../../../reports/belief_v5_play_followup_2026-11-10.md), and
[attention comparison](../../../reports/belief_residual_attention_2026-11-10.md).
The [model and optimizer recovery bundle](https://chatgpt.com/library?file_id=libfile_fde3_f-ee8f42e1a3888191bf5eebd25c003528_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal)
retains the selected TensorFlow and AdamW checkpoint and source metadata.

This publication promotes the belief component. Existing arena manifests remain
immutable; no arena run is started or resumed, and the reserved belief test set
remains unevaluated.
