# Residual attention belief: completed comparison

**The experiment did not improve its validation objective. Epoch zero, the existing dense v5 candidate, won in both arms. No model was promoted.**

The small attention component improved on matched dense continuation, but this training recipe did not produce a better overall candidate than the starting model. The closest trained attention checkpoint was epoch 2: composite NLL 0.86769118 versus 0.86762469 initially, a 0.0077% increase. Epoch 3 worsened again. This is a single-seed experiment; paired family SE does not include retraining uncertainty.

## Fixed final epoch

Lower NLL/Brier is better; higher accuracy is better. Recent-play metrics average within a deal family and then across families.

| Model | Composite | Ordinary NLL | Impact-weighted NLL | Accuracy | Brier |
|---|---:|---:|---:|---:|---:|
| Starting dense v5 | 0.86762469 | 0.67109578 | 0.67255530 | 60.1732% | 0.46766872 |
| Dense, epoch 3 | 0.86895007 | 0.67309092 | 0.67458847 | 59.9862% | 0.46947131 |
| Attention, epoch 3 | 0.86838093 | 0.67211037 | 0.67360182 | 60.2344% | 0.46854181 |

Attention minus dense continuation on recent weighted NLL: **−0.00098666 ± 0.00019128 SE**, an improvement of 5.16 SE. Attention minus starting v5: **+0.00104652 ± 0.00081580 SE**, slightly worse and statistically inconclusive. The ordinary NLL difference from starting v5 is +0.00101459 ± 0.00080693 SE.

On consequential cards alone, starting v5 versus final attention gives NLL **0.75459714 → 0.75569667**, accuracy **57.7982% → 59.5785%**, and Brier **0.50217559 → 0.50236285**. The NLL difference is +0.00109953 ± 0.00443125 SE; the accuracy gain is 1.7803 ± 1.1319 percentage points SE. These do not establish a consequential-card improvement.

Historical-play NLL improved by approximately 3 SE at epochs 1 and 2, but the final epoch lost that improvement. The attention model's composite scores were 0.86793306, 0.86769118 and 0.86838093. All domain metrics, all epochs, weighted accuracy/Brier and paired contrasts are in the [detailed report](belief_residual_attention_details_2026-11-10.md) and [JSON](belief_residual_attention_2026-11-10.json).

## Recipe, counts and checks

Both arms started at identical predictions from dense v5, with fresh AdamW, learning rate 0.0001, batch size 128, three epochs, identical row ordering, frozen policy-clean data and consequential-card weighting. The dense model has 308,726 parameters; one 64-wide, two-head residual cross-attention block raises that to 357,754. Neither arm restarts the old standalone attention experiment.

Each fit used **998,425 positions, 31,120,476 uncertain-card targets and 89,652 distinct training families**. Validation used 11,273 families overall; recent play supplied 192 families, 47,004 targets and 1,687 consequential targets in 130 families. Targets within a family are correlated. Both partnerships exclude the bad v4 policy; 4b remains included. The reserved test was not evaluated and no arena play occurred.

Dense active epoch time was 3.31 minutes and elapsed time 6.00 minutes. Attention active epoch time was **36.63 minutes**, elapsed **55.78 minutes**; two interruptions and worker startup account for much of the difference. Both fits completed 23,421 optimizer updates. Selected epoch-zero checkpoints have zero updates in the freshly initialized comparison optimizer.

Exported NumPy predictions match selected TensorFlow predictions across all four validation domains, maximum absolute error **5.96×10⁻⁷**. Reconstructed 512 KiB model parts match selected model SHA256 values. The recovery archive retains both selected and final trained models and Adam checkpoints, all per-family evaluations, frozen recent data and historical-data recovery references.

[Model files](../models/cardplay/gen5-belief-residual-attention-2026-11-10/README.md). The selected attention export has its initial zero correction and predicts identically to the starting dense v5; it is not an improved candidate. The trained final attention weights are retained in recovery for research.

[Full recovery archive](https://chatgpt.com/library?file_id=libfile_fde3_f-3be42a1ec2b48191975b851c18dc0158_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal), SHA256 `c3cc7c9f1e22c41dbfc746afb97e8c54e88dd0b857f39afe75c7ffe12a31fb55`.
