# Auction-aware policy bootstrap and random fork learning

The draft policy now receives the auction directly, including bidder seats,
alongside visible cards, ordered public play, contract/vulnerability and PIMC
estimates. Previously the selector received bidding indirectly through the
belief-weighted search. No hidden hand, future outcome or source identifier is
part of its neural inputs. Synthetic legacy auctions are masked during fitting.
Deployment in this experiment uses genuine BEN network-only auctions.

## One final predictive warm-start

Max stopped the original 10,000-board collection at roughly 8,000. Its last
in-flight slice drained to **8,315 complete unique boards**, including 24 passed
out boards, with no invalid records. Both collection locks were free when the
stop was finalized. The STOP marker remains; do not resume it to 10,000.

The frozen mixed dataset includes these records and previous completed play
experiments, deduplicated by file/trajectory. Imported benchmarks are retired
as independent evidence for this model. All rotations, views and tables of a
deal share a split; the old selector's 7,993 gradient-training families are
forced into training, never the new validation set.

| Item | Result |
|---|---:|
| Parameters | 39,512 (parent 25,170) |
| Training decision rows | 363,868 |
| Validation decision rows | 58,288 |
| Validation deal families | 2,466 |
| Parent validation MSE | 0.90976017 |
| Selected validation MSE | 0.81304822 |
| Relative MSE decrease | 10.63% |
| Selected epoch | 8 of 8 |
| Active fitting time | 103.82 seconds |
| Changed greedy ranking on validation support | 31.94% |

Targets are the observed remaining partnership tricks for the chosen action.
Uniform-target importance correction is used only where the logged behavior
has positive probability on every eligible action; partial-coverage records
remain ordinary predictive examples. Unplayed actions receive no invented label.
This is the last such predictive policy fit.

Zero initialization on added state inputs preserves the parent function before
training: maximum discrepancy 4.77e-7, no changed greedy choices. Selected NumPy
inference matches TensorFlow within 9.54e-7. The mean per-family MSE change is
-0.08714, with descriptive normal 95% interval [-0.10237, -0.07190]. The epoch was
selected on these data; this is validation, not an untouched confirmatory test.

Most of the prediction gain is shared state-value prediction. With the action
correction removed, selected MSE is 0.813197 versus 0.813048 with it. That small
difference and the changed rankings do **not** establish better play. The model
is a draft collector, not a declared stronger incumbent. Nor does this single
fit isolate how much of the gain came from auction inputs versus new data.

Selected checkpoint SHA256:
`8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5`.

## Random audits and forks

The initial block freezes 150 unused real-auction deal families, excluding every
family in the predictive warm-start. Candidate partnership alternates NS/EW.
Both sides use the promoted large belief model, 32 PIMC samples and the same
near-tie window. The separate 64-versus-32 study is unchanged. The reference is
the original selector operating on those same beliefs and search estimates;
this isolates the local policy decision, not the earlier belief change.

The candidate commits its move, including 15% uniform exploration within the
near-tie window, before an independent 50% audit draw. Predicted gain never
controls audit selection. A frozen reference chooses from the identical PIMC
proposal. When the moves differ, replay the prefix, force the reference move,
and continue with the same frozen partnership assignments. Score the duplicate
score difference in IMPs from the audited actor's partnership's perspective.
An identical action has a known zero advantage without a second rollout.

All descendants share one compute account. Mainline process CPU accrues credit
for a target of 3x total play CPU across the block. Random priorities decide
which drawn audits are considered first. Remaining parent-tail CPU estimates
gate admission; an admitted tail always finishes even if it overruns. Depth is
limited to two and nonidentical forks to 64 per board. Budget exclusions and
audit probabilities are logged; these are random audits within the admitted
opportunities, not an assertion that every position has equal final inclusion.

Continuation random seeds are keyed by board, ply and controller, not history;
different observations can consume the stream differently. Exact DDS results
are shared in SQLite. Prefix replay needs no solves, and overlapping sampled
positions can hit the cache; new worlds and branches still incur misses.

The first 12 boards produced 106 audited deviations, including 64 recursive
ones, at 1.315x mainline CPU. These are 12 independent families, not 106
independent boards. The pilot is a collection/functional check, not evidence of
playing strength. All complete mainlines and branches are replay-validated.

## Policy/value head after the warm-start

`train_fork_policy.py` accepts only the random-fork schema and reconstructs each
matched comparison. It rejects ordinary play as a policy-label source. Inputs
are rebuilt at the pre-action observation; targets are the verified audited
IMP differences. All descendants stay with their deal family in train or
validation. The initial readout keeps the 39,512-parameter representation frozen
and fits nine regularized coefficients over its nonlinear action features and
PIMC value. This conservative first head can be expanded/unfrozen as fork data
grows. It predicts candidate-minus-reference IMP advantage; the reference is
exactly zero. It can both rank actions and report their predicted advantage.

The trainer requires at least ten train and ten validation families with actual
deviations, compares five fixed regularization choices with a zero-gain baseline,
and weights families equally so heavily branched boards cannot dominate. It
does not automatically promote a model. The initial collector still reports
its warm-start predictions in tricks and leaves predicted IMP gain null; it
does not relabel trick predictions as calibrated IMP estimates.

Ordinary and fork trajectories may continue training beliefs. From this point,
only fork comparisons may train the policy head. Keep reference/continuation
versions with every label, and use a new frozen block when versions change.

## Reproduction and continuation

Run from this checkout with the archived run directories restored:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/collect_policy_forks.py \
  --root runs/random-policy-forks-v1 \
  --corpus runs/random-policy-forks-v1/corpus.jsonl \
  --belief runs/random-policy-forks-v1/artifacts/belief.npz \
  --bootstrap runs/random-policy-forks-v1/artifacts/bootstrap.npz \
  --incumbent runs/random-policy-forks-v1/artifacts/incumbent.npz --seconds 180

OPENBLAS_NUM_THREADS=1 python scripts/train_fork_policy.py \
  --run runs/random-policy-forks-v1 --out runs/fork-imp-head-v1 \
  --bootstrap runs/random-policy-forks-v1/artifacts/bootstrap.npz
```

Finish the frozen collection block before fitting its IMP head. Do not restart
the old 10k collector or the superseded unforked mixed block. The separate large
belief continuation task owns belief fitting; it may use the final 8,315 boards.
Preserve checkpoints and cache using SQLite backup, not a live WAL-file copy.

Validation: 18 relevant tests passed for public inputs, seat rotation, exact
parent preservation/export, audit independence, reward sign/IMP boundaries,
recursive budget accounting, and exact DDS-cache behavior. Initial real audit
records were also independently re-encoded and their label signs checked.
