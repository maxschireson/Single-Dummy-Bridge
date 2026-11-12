# Self-improvement loop

The combined v2 uses the published auction belief net to weight PIMC samples and
an outcome-trained policy net to rank PIMC-near-equal plays. Both are warm-started
and retrained in each generation. The selector sees public play/state and the
auction-informed PIMC values; it does not directly encode the auction. Combining
them is an experimental starting point, not an established strength gain.

## Cycle and objective

1. Freeze v1 (uniform PIMC), v2, both network artifacts, the bidder, BEN card-play
   reference, source, native DDS, and external model/configuration hashes.
2. Collect 10,000 independent self-play deals. BEN supplies neural-only auctions:
   no bidding search, rescue, BBA, or auction DDS calls. The four players use the
   combined parent plus 20% uniform exploration within its PIMC near-tie window.
3. Fit both nets using training deals and select each against its epoch-zero
   parent using validation only. Retain unchanged parents when fitting hurts.
4. Screen changed candidates against the parent on 1,000 paired deals. A
   nonpositive mean advances to more data without spending full-search BEN time.
   This is a compute-allocation heuristic; it can discard a small real gain.
5. For positive screens, confirm against parent, original, and BEN. Also measure
   parent versus BEN on the identical deals. Confirmation looks are 250, 1,000,
   then 4,000 independent deals. These deliberately bounded defaults prioritize
   iteration time and may be underpowered for small improvements.
6. Promote only if both improvement over the parent and improvement in score
   against BEN pass the predeclared statistical gate. Otherwise extend cumulative
   self-play to 50k, then 250k (40k and 200k additional deals).
7. A promotion becomes v3, then v4, etc. Preserve all historical bots. A new
   generation gets fresh self-play and arena deals. If all three data stages fail,
   retain the champion and stop for review of the learning recipe.

“Improvement against BEN” is `IMPs(candidate vs BEN) - IMPs(parent vs BEN)` on
identical deals. BEN need not be beaten outright. All evaluations swap
partnerships, use frozen auctions/contracts, and let each engine choose its
opening leads. Positive IMP/board favors the candidate. This measures card play,
not bidding strength. Passed-out deals remain in the population as zero IMPs.

## Progress per time

Self-play defaults to eight bounded workers, NumPy inference, 32 related DDS
samples, and the batch DDS interface. Neural auctions are batched and load only
the bidder network; the collector checks scalar versus batched output. Training
runs separately to avoid contending with play workers. Both learners stop after
two nonimproving validation epochs, at most eight epochs.

Unchanged models skip evaluation. Common sampling seeds reduce comparison noise
when public histories coincide. The three predeclared training stages share one
reserved arena cohort within a generation, allowing parent-versus-BEN games to
be cached. Candidates and training are never selected using individual arena
outcomes; only the predetermined data ladder responds to success or failure.
Statistical error spending covers all stages and looks despite cohort reuse.

A managed BEN server starts only after screening, uses one arena worker, and
releases its resources afterward. Shared resource locks serialize it with other
BEN experiments. Its bidding search is disabled; its card-play sampling and DDS
remain enabled. Existing servers are never reconfigured or terminated.

## Training and validation

The existing hash split is 80% training, 10% validation, 10% unused internal test,
by complete deal. Thus 10k collected deals give approximately 8k fitting and 1k
validation deals. All positions from one deal stay together. This validation
fraction is a reasonable starting point for network selection; it does not
size the promotion arena.

The belief learner fits hidden-card labels from legitimate observations and
frozen auctions. With bidding fixed, stronger card play does not improve the
auction-only label distribution; its benefit here is additional data. The policy
learner fits actual chosen-action remaining-trick returns, with logged behavior
propensities correcting to uniform support over eligible actions. With 20%
exploration, the importance weight is at most five. Unplayed actions receive no
invented outcome label. Neither learner accesses the internal test or arena.
Each exports NumPy inference weights; policy export is checked against TensorFlow.
Better validation loss alone never establishes stronger card play.

## Arena size and statistical gate

Evaluation size depends on effect and variance, not a fixed fraction of training.
Halving the target effect requires approximately four times as many independent
deals. Use earlier pilot SDs of the paired parent score and paired BEN difference:

```sh
python3 -m bridge_harness.improvement size-arena \
  --effect 0.10 --sd-parent 2.0 --sd-ben-delta 3.0
```

Those SDs are illustrative. Freeze an evaluation ladder before the campaign;
do not silently expand it after inspecting results. Smaller differences may
remain inconclusive at the time-oriented 4k cap.

Both primary lower confidence bounds must exceed `minimum_imp_gain` (zero by
default). Family alpha .05 is allocated across generations using 1/[g(g+1)],
three data stages, three confirmation looks, and both endpoints. Approximate
Student-t intervals operate on independent deals. Zero-variance/all-tie results
cannot promote. Screening never promotes and cannot relax the full gate.
Original/BEN absolute intervals are descriptive 95% intervals. Restarts of the
same campaign retain the budget; repeatedly starting new campaigns does not
preserve a single global error guarantee.

## Prepare and run

Use a stable worker checkout. Install the loop dependencies, build DDS, and
provide the existing belief/policy NPZ artifacts plus an external licensed BEN
checkout and models. No model weights or external BEN distribution are in Git.

```sh
python3 scripts/build_dds.py
python3 -m pip install -e '.[loop]'
python3 -m unittest discover -s tests -v
python3 scripts/prepare_v2_loop.py --root runs/v2-loop-001 \
  --belief /absolute/auction_weights.npz --policy /absolute/policy_weights.npz \
  --ben-dir /absolute/ben --ben-python /absolute/tf-venv/bin/python \
  --bid-config /absolute/neural-only.conf --play-config /absolute/full-cardplay.conf \
  --exclude /absolute/prior-deal-ids.json --resource-lock /absolute/shared-ben.lock \
  --workers 8 --verified-ben
python3 -m bridge_harness.improvement check --root runs/v2-loop-001
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -u -m bridge_harness.improvement \
  run --root runs/v2-loop-001 --generations 1
```

`--verified-ben` records a successful live check of this source/models/card-play
configuration. Without it the campaign remains prepared but cannot run. The
helper disables server bidding search and rescue, preserves card-play settings,
and freezes all referenced models and Python sources. `--exclude` can repeat to
reserve all prior training/evaluation identities. A fully customized immutable
campaign can instead be initialized from `configs/self_improvement.json`.

The run command resumes completed games and fits, and advances at most one
successful generation per invocation by default. A supervisor can invoke it again
on promotion. Failed games block progression and are retained; explicit
`--retry-failures` retries the same inputs, preserving the failed records.
`status` is safe while a worker holds the writer lock. `report` rebuilds
`progress.md`/`progress.json` when no writer is active.

## Durability and audit

Bot manifests copy artifacts and are immutable. A promotion atomically updates
champion, version history, and next generation. A single OS-owned writer lock
prevents duplicate campaign controllers. Self-play auctions are frozen in
250-deal chunks, and each game is atomically saved, replay-validated, and cached.
The SQLite ledger rejects old-data reuse and training/evaluation overlap.
Related-layout families are not treated as independent arena deals.

`state.json` includes cumulative collection/training/screening/confirmation wall
time. Progress files retain IMPs against original, parent, BEN, paired BEN gain,
uncertainty, match timing, and decisions. Raw games preserve predictions, actual
propensities, seeds, legal moves, and DDS costs. Evaluation is as configured;
there is no claim of equal wall-clock strength.

Keep the pinned checkout and run directory together with external configurations
and models. Absolute paths are recorded, so relocation requires preserving mount
paths. Archive state and completed chunks periodically on a persistent worker.
The supervisor must acquire the existing writer lock and preserve completed
work; elapsed time or a missing process in another namespace does not authorize
starting a competing worker.

## Attribution and evidence

Bridge rules, PIMC, constrained sampling, replay, and DDS are reused from this
repository. The auction model and selector come from the prior bidding and
self-play studies (selector source commit f26f975a5c197def5e203dd2da87d84dd54aadb9).
BEN and DDS retain their upstream licenses/credits. Implementation assistance:
OpenAI Codex, working with Max Schireson. The launch report distinguishes tests
and plumbing checks from actual strength evidence.
