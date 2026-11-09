# Actual-outcome bidding fit, 9 November 2026

Training completed and the candidate is saved. It is not deployed or promoted.
The bidder inherits BEN weights and the existing 40,000-deal fine-tuning; this
update uses actual completed hand outcomes without new DD calculations.

| Quantity | Value |
|---|---:|
| Actual table results | 7,400 |
| Distinct deal/auction families | 3,700 |
| Training families / decisions | 2,939 / 30,873 |
| Validation families / decisions | 761 / 7,950 |
| Historical distillation deals / prefixes | 512 / 10,860 |
| Passes, actual-outcome fit and control | 6 each |
| Selected actual-outcome pass | 6 |
| Original / final optimizer updates | 3,732 / 4,458 |

## Validation

| Bidder | Outcome-weighted NLL | Unweighted NLL | Family-weighted greedy decisions changed vs parent |
|---|---:|---:|---:|
| Parent | 0.066280737 | 0.067416721 | 0% |
| Actual-outcome candidate | 0.061078815 | 0.062228500 | 0.520% |
| Matched unweighted control | 0.060376001 | 0.061336710 | 0.602% |

The actual-outcome candidate improves outcome-weighted validation NLL by
7.85% versus the parent. Its paired family-mean reduction is
0.005201922, SE 0.000325482.

The unweighted control performs better on that same metric. The candidate's
loss is higher by 0.000702814, SE
0.000135852 (approximately
5.17 SE).
Thus this fit does not establish an incremental benefit from outcome weighting.
The actual-outcome candidate is retained explicitly as the requested experiment;
the control has not silently replaced it. These are descriptive selection-set
comparisons, not tests of playing strength, counterfactual bidding outcomes,
or IMPs won in the arena.

The selected checkpoint's exported actor exactly reproduces its saved model
on 128 legal auction observations (maximum probability difference 0). Adam
state restores at update 4,458. Eighteen focused tests pass,
covering score direction, outcome/input separation, canonical-family partitions,
duplicate handling, legal bids, cross-fitting, and optimizer restoration.

Full source, method, family weighting, retained data, and limitations are in
[the three-model training notes](gen4_model_training_notes_2026-11-09.md).
The machine-readable per-pass results and paired comparisons accompany the
model under `models/bidding/v4-actual-outcomes-2026-11-09/result.json`.
