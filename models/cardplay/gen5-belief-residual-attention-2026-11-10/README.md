# Residual belief attention comparison

Run `python restore.py` to reconstruct the selected dense and attention exports. Hybrid inference uses `bridge_harness.residual_attention_belief.Weights`; legacy loading intentionally rejects hybrid exports. No arena promotion or reserved test evaluation occurred. See the run report for selection and paired family metrics.

**Epoch zero won in both arms. This experiment did not improve its validation objective.** The selected dense export is the existing v5 candidate; the selected attention export has a zero correction and identical predictions. These files are research artifacts and were not promoted.

See the [result report](../../../reports/belief_residual_attention_2026-11-10.md). The [full recovery archive](https://chatgpt.com/library?file_id=libfile_fde3_f-3be42a1ec2b48191975b851c18dc0158_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal) also preserves the final trained models and optimizer checkpoints.
