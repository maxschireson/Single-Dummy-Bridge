# Attention width 96 versus 64, full1513 snapshot

Max authorized this matched comparison on 10 November 2026 after width40 underperformed width64 on the earlier192-family snapshot. This run uses the frozen full1513 feed union:601,037 training outcomes across5,689 families and78,727 validation outcomes across748 metadata families (745 nonempty).

Both arms start from the same later-Gen3 dense parent with zero attention readout, giving the same initial predictions. Width64 has99,161 parameters; width96 has153,561. Keep two heads, one block, dense backbone, family-weighted individual-outcome MSE, seed2026110923, batch128, AdamW learning rate0.0002 and weight decay0.0001, clipnorm1, and8 epochs. Select by validation-family MSE including epoch0. Frozen promoted Gen5 is a separate comparator. The existing Gen5 continuation is not a matched width control because it starts with trained attention.

Preflight passed parent-function preservation, nonzero-attention portable NumPy scoring, save/restore, and legacy width inference for width96, alongside existing40/64 checks. The unchanged runner verifies the pinned input and source hashes, resumes completed optimizer epochs, preserves interrupted first-epoch directories, skips completed arms, and writes paired family MSE64-minus96 with SE and95%CI. Positive favors width96.

The fit runs two single-thread workers in a separate native terminal tab and separate output directory. Existing gen6 fits keep their locks and outputs. No test scoring, arena changes, or recipe changes outside this authorized comparison. Single-seed validation is screening evidence; any promising candidate needs fresh independent confirmation.

Reproduce with the Python and absolute paths pinned in `configs/gen6-policy-width96-full1513.json`:

```sh
python -u scripts/run_policy_width_comparison.py --plan configs/gen6-policy-width96-full1513.json
```
