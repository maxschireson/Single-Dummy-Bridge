# Larger belief net: paired play and provisional collection

The 308,726-parameter epoch-6 belief checkpoint was compared against the
original auction-belief v2 bot. Both sides use the same frozen policy selector,
16 sampled layouts per decision, a 0.125-trick near-tie window, and zero policy
exploration. This isolates the belief change at the cheaper search budget Max
requested. The separate 8-vs-16 and 8-vs-32 budget studies remain unchanged.

## Fixed pilot

The initial cohort contains 50 completed self-play deals recorded after the
selected checkpoint was written. Every deal family is excluded if it appeared
in this candidate's training or selection validation, including rotated hands
and the original BEN corpus. Deal selection uses a deterministic hash, without
looking at play outcomes. The frozen manifest contains source hashes, boards,
auctions, model identities and the cutoff. No additional deals are selected
after seeing pilot results.

Each deal is played twice: candidate NS against incumbent EW, then incumbent NS
against candidate EW. The auction and decision random-number scheme are shared.
Positive IMPs favor the candidate. The original self-play outcomes are not used
as controls: those games used exploration, and changing one partnership changes
the subsequent trajectory. Records are replay-validated for legality and score.

This began at 32 samples, then Max requested 16 versus 16 for speed. The 32-sample
pilot was stopped and retained separately. The new 16-sample test uses the same
50-deal cohort. Do not pool the two budgets or treat the interrupted run as an
independent confirmatory test. Fifty deals is a functional and directional
pilot, not enough to establish a small strength gain.

Selected belief SHA256:
`bb46241ed4270ac171354ca9b7d5146bf532f50fc08370c5a5ee07461bbceedb`.
Incumbent belief SHA256:
`c070981c21cc79eed2205b5dbe6693e5804641a05d7ce32948df10bf15a1e96a`.
Shared selector SHA256:
`02b6885e8f07da473970052d7f9ea9dc2a10fa34505ad60186e4a14d02218c60`.

## DDS reuse

The older, pinned collection checkout did not yet save individual sampled-world
DDS results. Its aggregate move estimates cannot reconstruct those solves.
The full-deal bidding table cache also cannot answer arbitrary sampled partial
positions. Therefore using already-played boards does not make this first test
a cache-only replay.

This isolated arena incorporates the exact cache from the shared-beliefs work.
Both models and both budgets share it. Keys include all remaining cards, strain,
leader, current trick and solver build; cached values cover all legal moves.
Only exact matches are reused. Changed beliefs may sample different worlds and
new actions lead to different positions, so cache-only speed is not promised
for a new model. Do not constrain the new model to the old sampled layouts.

The completed 16-sample pilot took 149.54 seconds for 50 paired deals (100 table
plays), or 20.06 paired deals/minute. Mean gain was **0.00 tricks/deal**, with
descriptive 95% interval **[-0.207, +0.207]**, and **+0.24 IMP/deal**, interval
**[-0.353, +0.833]**. There were 7 IMP wins, 38 ties and 5 losses. These results
do not establish a small gain or rule out a modest regression.

Of 65,488 requested world solves, 41,671 needed native solves, 13,810 were exact
cache hits and 10,007 were duplicate worlds resolved within batches. Some cache
hits reused the interrupted 32-sample run, so this is not a cold speed benchmark.
Replaying one complete pair with the same inputs took 0.237 seconds, produced
identical cards and scores, and served all 1,408 worlds from cache with zero
native solves. This is an exact-replay demonstration, not new-model throughput.

Observed paired trick standard deviation was 0.728. A normal approximation
suggests about 42,000 pairs to detect a 0.01-trick effect at two-sided 5% alpha
and 80% power, around 35 hours at this measured rate. The small pilot makes this
a rough planning estimate, not a promised sample requirement. It supports using
prediction validation for incremental promotion rather than trying to measure
each tiny gain with a separate arena.

## Accepted promotion change

Max explicitly directed promotion based on lower cross entropy and better
ownership predictions, with confirmation accumulating from mixed-pool play.
The larger checkpoint is therefore **promoted for collection**. The executable
gate requires both lower weighted validation cross entropy and higher weighted
ownership accuracy, using the frozen selection weights: half public play and
one quarter each completed DDS-bidding and BEN auctions. It does not read IMP
results. Tests check acceptance without play results, rejection when either
metric worsens, and mismatched/nonfinite metric rejection.

The immutable promotion event and current collector pointer are in
`runs/prediction-led-collection/`; the previous bot remains a fixed reference.
Prediction improvement does not itself establish improved play. This distinction
is a reporting distinction, not an extra significance gate on collection.

For the next collection generation, use paired mixed-version matches: a
candidate partnership against the retained reference, swapping directions on
the same deal. These games supply both learning trajectories and a controlled
effectiveness signal. Both versions remain immutable during a collection block;
record versions, sample budgets, seating, seeds and any exploration probabilities.
Use the same settings on both sides. If exploration is enabled for collection,
report its strength estimate separately from greedy-play results.

Score each frozen block before its deals enter a subsequent fit. After using
the deals for training, retire them as independent evidence for that newer model;
evaluate it on fresh subsequent deals. This permits almost all generated play
to become training data without pretending in-sample replay is a new test.
Retain a stable older anchor and report each fixed-version comparison separately;
do not pool changing candidates into one estimate of the latest model's strength.

Keep the older reference for longitudinal comparison while promoting collectors
on prediction validation. Small inconclusive estimates need not stop collection;
clear deterioration should trigger investigation. Repeated interim confidence
intervals are descriptive, not sequential significance guarantees. No arbitrary
automated rollback threshold was introduced.

The first mixed block freezes 200 additional post-checkpoint deals, excluding the
50-deal pilot and all candidate training/selection-validation families. Its first
pair passed full replay validation. Both partnerships use 16 samples and greedy
selection so its signal has a single interpretation. Completed trajectories are
eligible for the next fit after block metrics are recorded, and then retired as
independent evidence for that newer fit.

The current frozen 10k collection finishes unchanged. At that boundary the
continuation uses this prediction-led collector and mixed blocks, rather than
launching the old mandatory IMP-significance gate. The separate DDS-bidding and
sample-budget experiments retain their own frozen recipes.

## Reproduction

Run from this branch with the frozen models and run directories restored:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ops/large_belief_arena.py \
  --samples 16 --run-seconds 240 --workers 2
```

The manifest is immutable; completed records are validated and skipped, failures
require inspection, and a writer lock prevents duplicate dispatch. Bounded
invocations stop dispatch at the time budget and finish their active pairs.
The default cache is `runs/large-belief-play-v1/dds-positions.sqlite` so the two
sample budgets reuse exact overlaps. Preserve it with SQLite's backup API.

Resume the next collection block with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ops/large_belief_arena.py \
  --out runs/belief-mixed-v1/block-001 --count 200 --samples 16 \
  --run-seconds 240 --workers 2
```

Its manifest already freezes the promotion, candidate/reference and cohort.
Run `ops/promote_belief_on_predictions.py` to reproduce the idempotent promotion
transaction from the saved validation results and pilot manifests.

Validation before launch: nine cache/public-belief tests and three combined-bot
tests passed. The combined-bot tests require `PYTHONPATH=tests` under unittest.
The arena records themselves are checked by the existing full replay and
behavior-probability validator.
