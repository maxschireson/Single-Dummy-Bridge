# Continue the promoted large belief net

The larger epoch-6 net is the selected collector. The size comparison is closed;
the small net is retained only as a reference. Future promotion requires lower
weighted validation cross entropy AND higher ownership accuracy, using half
public play and one quarter each completed DDS-bidding and BEN auctions. No IMP
significance prerequisite is imposed. Mixed-pool play supplies confirmation.

At 01:31 Budapest on 9 November the frozen v2 collection had 7,823/10,000
completed episode files, 30 complete 250-deal shards, and last episode activity
at 01:21:25. Its three supervisor/writer locks were free. Mixed block001 remained
1/200 with a free writer lock. Its existing collection owner was given this
handoff; this task did not launch a duplicate or alter either collection.
The next production fit awaits the committed remaining data/block boundary.

The selected model/Adam checkpoint was restored and checked against the promoted
NPZ: exactly equal model arrays, optimizer iteration 5,658, 18 optimizer variables.
Promoted weights SHA256:
`bb46241ed4270ac171354ca9b7d5146bf532f50fc08370c5a5ee07461bbceedb`.
This uses the selected epoch6 optimizer, not the later unselected epoch8 state.

## Continuation implementation

`scripts/continue_large_belief.py` starts a separate run on a newly frozen
dataset, verifies that its parent matches the current collector registry, and
restores the matching model AND Adam state. It pins the registry and checkpoint
hashes, rejects parent mismatch or optimizer reset, and re-evaluates that current
parent on the exact validation observations used for the new candidate. It does
not reuse initial/parent metrics from the old size study. A stopped 48-row smoke
fit resumed through epoch2 from the selected optimizer; it is diagnostic only,
not a candidate or promotion result. NumPy/TensorFlow export checks passed.

Eligible checkpoints must improve both weighted measures against the current
parent; the selectable epoch0 is retained otherwise. There is no minimum IMP
or cross-entropy effect-size gate. The script emits promotion eligibility but
does not change a live collector pointer. At publication, recheck the parent
identity and transfer collector/reference manifests at a block boundary. Keep
the older fixed v2 anchor for longitudinal evidence.

Example from the belief-size checkout after preparing NEW-DATA with the current
promoted weights as its parent:

```sh
OPENBLAS_NUM_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3 OMP_NUM_THREADS=1 \
  /workspace/scratch/ad64ffb80c06/work/ben_venv/bin/python \
  scripts/continue_large_belief.py --data NEW-DATA --out NEW-RUN \
  --parent-checkpoint runs/belief-sizes-v1/large/selected-checkpoint/ckpt-6 \
  --registry /workspace/scratch/c3d88c7ec30c/bridge-belief-arena/runs/prediction-led-collection/current.json \
  --run-seconds 120
```

Pool usable trajectories across bidder/player versions with provenance. Score
mixed blocks before their trajectories enter gradients, then retire their old
independent-evidence status for the newer model. Keep family splits, use only
public information as inputs, and preserve the policy selector/sample budget.
The original frozen size-study datasets, model/Adam checkpoints, DDS-bidding
study and 8/16/32 budget studies remain unchanged.
