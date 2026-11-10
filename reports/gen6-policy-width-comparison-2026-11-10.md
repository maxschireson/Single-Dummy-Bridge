# Matched 69K versus 99K attention policy comparison

Max requested an intermediate model around 70K parameters and explicitly asked
to test narrower attention. This experiment changes attention width from 64 to
40: 99,161 versus 69,113 total parameters. The dense backbone, two attention
heads, one attention block, observable inputs, targets, and family weighting
remain the same.

Both arms start from the same later-Gen3 dense checkpoint, SHA256
`8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5`,
with zero attention residual readouts. Thus their initial predictions match;
the 99K arm does not receive the promoted Gen5 model's extra training history.
The frozen promoted Gen5 checkpoint (`03e70a6f...`) is also evaluated as the
practical benchmark. This capacity experiment is separate from unchanged
Gen5-to-Gen6 continuation.

Both arms use the identical pinned policy-first-union dataset: 436,263 training
outcomes, including 25,569 from the first 192 new arena records. This is an
initial-data experiment, not the full later-export refresh. Source checksums,
canonical family splits, bad-policy exclusions, and reservations are inherited
from that verified dataset. There are 607 validation families with outcome
rows. Later feed arrivals must not be added to either active fit.

Each arm has eight epochs, seed 2026110923, AdamW learning rate 0.0002,
weight decay 0.0001, clipping norm 1, and batch size 128. Validation-family MSE
selects each arm's best epoch, including epoch zero. Evaluation preserves
family pairing and reports the SE of small-minus-large MSE. Test outcomes and
test choice labels remain unopened for this experiment. One-seed validation
results are a screen; independent confirmation is required before promotion.

The existing 39,512-parameter dense and 80,136-parameter wide-dense experiments
provide historical context, but changing attention width tests a different,
previously untested part of the capacity range.

`scripts/run_policy_width_comparison.py --plan
configs/gen6-policy-width-comparison.json` runs and resumes both arms. The plan
pins local data/model/source hashes and paths. Each fit saves optimizer state
after every completed epoch. The runner holds a writer lock and preserves an
interrupted pre-first-epoch directory before restarting it. It skips completed
arms and produces a paired validation comparison when both finish.

Portable inference now infers attention width from each checkpoint, allowing
the 69K candidate and existing 99K benchmark to be evaluated together. Checks
cover exact parent preservation, nonzero attention readouts, NumPy/TensorFlow
agreement, save/restore, and legacy exports without explicit width metadata.
The width-40 and width-64 checks passed before launch.

No active arena models or settings are changed by this experiment.
