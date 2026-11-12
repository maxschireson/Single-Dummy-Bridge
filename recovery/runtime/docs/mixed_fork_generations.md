# Mixed branching generations

Each long run evaluates its frozen candidate while collecting data for its
successor. Generation one contains **25,000 distinct, fresh contracted deals**,
with shared neural-only auctions. Passed-out deals are excluded before selecting
the cohort, never on the basis of a play result.

## Frozen actors and environment

All current and historical play versions use the **same latest bidding network**.
The restart on 9 November adopts the validated 40,000-pair DDS bidder for every
seat and every version. Auctions are generated once with that actor and frozen
for both root tables and all forks. Historical versions retain their play and
belief differences, but do not retain historical bidding. Promotion therefore
compares cardplay under common auctions, without attributing gains to bidding.
The next boundary reads the shared bidder registry and freezes it for all bots
again. A live generation never silently changes its auction distribution.

| Environment partnership | Initial probability |
|---|---:|
| New auction policy plus public-play belief | 50% |
| Previous selector plus public-play belief | 25% |
| Original combined v2 | 12.5% |
| Original PIMC v1 | 12.5% |

The ideal weights are 1/2, 1/4, 1/8, ...; the oldest available version receives
the remaining geometric tail. Sampling occurs at partnership level. Versions,
weights, source hashes, 32-sample search, 0.125-trick eligible window, and zero
policy exploration are frozen within the generation. The newest validated
version is the default best without requiring a prior significant IMP win.

## One board, several uses

For every deal, choose a historical opponent and focal partnership orientation
before play. Play two full main tables: current candidate in those seats versus
that opponent, and previous best in the same seats versus the identical
opponent. Auction, vulnerability, board, and decision random streams match.
Focal NS/EW orientation is randomized independently of results. The difference
of duplicate scores is converted once to IMPs from the focal perspective.
Thus 25,000 boards means 25,000 whole-bot paired comparisons, 50,000 main tables,
plus counterfactual continuations; branches do not increase the independent
board count. No old unmatched self-play scores are used as controls.

The candidate also commits each policy move before an independent 50% audit
coin. Its reference policy is evaluated using the same candidate belief and
PIMC proposal. A differing reference action is forced from the identical public
history, followed by the same frozen continuation players. This local IMP
contrast isolates the policy decision; whole-board pairs evaluate the complete
bot. Identical-action audits are known zeros. Losses are retained.

Recursive depth is at most two and nonidentical forks at most 64 per deal.
The two main tables fund a common CPU allowance targeting at most 3x their play
CPU. Admission uses estimated remaining-tail cost; admitted continuations finish
even if they overrun. Random priorities prevent systematically taking only
early positions. Budget exclusions are logged, so audited contrasts are not
misrepresented as uniformly sampled over every possible position. Predicted
gain never controls the audit coin. Local gains are never summed into the
whole-board match score.

All full trajectories are retained. Hidden holdings label belief predictions;
only permitted observations enter either deployed network. Canonical deal
families determine an 80/20 train/validation split, shared by every branch,
view and table. Independent fresh-generation outcomes may evaluate today's
frozen policy and subsequently train tomorrow's policy. They cease to be
independent evidence for a model after entering its fitting or selection.

## Adoption, demotion, and the next generation

The newest prediction-validated version begins first. Current-versus-reference
IMPs are checked at predeclared board counts (initially 500, 1,000, 2,500, 5,000,
10,000 and 25,000). A negative one-sided upper t bound triggers demotion. The
nominal alpha budget is divided across looks and across generations as
0.05 / (g(g+1) * number_of_looks). These t bounds are approximate sampling
bounds, not distribution-free guarantees. Intermediate ordinary 95% intervals
are descriptive. Checks use the completed contiguous board prefix, preventing
fast-finishing deals from selectively triggering a look.

Demotion changes the recorded best immediately and the next generation's
historical order. The active run's frozen actors and mixture do not change.
The failed candidate remains in history just below its successful reference.
At the fixed boundary, train even if the IMP result is inconclusive.

The belief continuation restores model and Adam and reevaluates parent and
candidate on identical held-out observations. Both weighted cross entropy and
card-possession accuracy must improve. The existing BEN/bidding/play data is
retained alongside the new trajectories. The policy's auction and action
layers are fine-tuned solely on verified audited IMP contrasts, with equal
total weight per family and held-out checkpoint selection. The new IMP output
is explicitly in IMP units. No ordinary outcome labels are used. A component
that fails predictive validation is retained from the parent. If neither
component changes, retain the current actual best and do not add a duplicate
version or re-promote a demoted parent. Historical optimizer checkpoints are
retained with their versions.

The automatic next generation uses fresh boards and the selected components,
with the new version first provisionally. Default lengths grow 25k → 50k →
100k → 200k, capped at 250k; they are explicit in each manifest. Historical
snapshots and completed pair results remain available to monitoring agents.

## Operations and verification

Runtime root: `runs/mixed-fork-25k/g0001-bid40k`. The parent `current.json` points to
the active generation. `manifest.json` contains immutable identities;
`state.json` contains paired IMPs, split counts, audit counts, and best status;
`heartbeat.json` names work currently in flight. Atomic compressed episodes and
small hashed receipts allow bounded slices to resume without replaying done
boards. The versioned supervisor `ops/supervise_mixed.py` separately verifies the
training-transition hash in `training-config.json`, preserving the frozen
collection code. It starts another slice automatically and launches fitting
at the boundary. OS-owned writer/supervisor locks prevent duplicate workers.
Never delete a lock file to take ownership. A `STOP` file stops new dispatch and
allows in-flight complete boards to be preserved.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ops/mixed_generation.py status \
  --run runs/mixed-fork-25k/g0001-bid40k
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ops/supervise_mixed.py supervise \
  --run runs/mixed-fork-25k/g0001-bid40k --seconds 240 --workers 8
```

Use `status --audit` for full replay and receipt verification. Failures are
preserved and block silent omission. The supervisor can recover child failures
only after investigation; an external monitor must restart it if the entire
execution environment disappears. Startup alone is not proof of progress:
inspect committed board counts and heartbeat times.

Model results and exact checkpoints are documented in
[the v2 component report](../reports/v2_network_results_2026-11-09.md).

The original `g0001` is permanently stopped at 351 pairs. Its observations are
preserved separately and never pooled into the restarted 25k result. The
[restart record](../reports/bid40k_restart_2026-11-09.md) identifies the promoted
bidder, source review, deployment checks and recovery instructions.
