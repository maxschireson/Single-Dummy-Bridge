# Planned direct pair matches for future arenas

User decision, 9 November 2026: allocate distinct sets of boards to A versus C and B versus C as well as A versus B. Do not use an A/B substitution against a third opponent as the only comparison.

## Version identities

For the current three-version explanation:
- A: deployed large belief plus new auction-aware policy.
- B: the same large belief plus original policy.
- C: original combined-v2 belief plus original policy.
All share the latest bidder, frozen at generation launch. The next generation must record exact version names, model hashes and component differences for every named comparison; labels are not sufficient identities.

## Board allocation and scoring

Use the user's rank-weighted allocation: A-B : A-C : B-C = 4 : 2 : 1, with A ranked first, B second and C third. Thus A plays B twice as often as C, and B plays C one quarter as often as A. Allocate disjoint, deterministically shuffled board-family cohorts in proportions 4/7, 2/7 and 1/7. For the already-authorized next 50,000-board generation, use 28,571 / 14,286 / 7,143 paired boards respectively (largest-remainder integer allocation). For a 25,000-board example, the counts would be 14,286 / 7,143 / 3,571. This replaces the earlier equal-allocation proposal. The ratios are consistent with pair weights proportional to the product of geometric rank weights 1/2, 1/4, 1/8, excluding self-pairs and normalizing over eligible pairs. Freeze the roster ranks and allocation in the manifest; apply subsequent ranking changes at the declared boundary. Select the pair and orientation before seeing outcomes. A board belongs to one pair only; there is no requirement to run all three pairings on every board.

For a pair X-Y, play two root tables on the identical deal and frozen auction:
1. X in North-South, Y in East-West.
2. Y in North-South, X in East-West.
Randomize execution order independently of outcomes. Convert NS_score(table1) minus NS_score(table2) once to IMPs favoring X. Both partnerships therefore hold each set of hands once. Preserve the established matched RNG convention and record it. Two root tables per family preserve the existing root-table budget; random counterfactual forks remain additional.

Report each pair separately: independent board count, total IMPs, IMPs per paired board, wins/ties/losses, descriptive interval and elapsed cost. A-C measures the combined play-component change; B-C measures the belief change with original policy fixed; A-B measures the policy change with the large belief fixed. These interpretations require the specified component hashes to match. Do not add their separate-sample estimates as though they were exactly additive. No bidding contribution is measured under common bidding.

## Learning, ranking and validation

Retain complete trajectories, canonical family grouping, the 80/20 split, post-commit random audits and the existing fork CPU/depth limits. Branches do not inflate independent board counts. Policy training uses only valid local matched contrasts with a declared same-belief policy reference; do not use a whole-bot opponent with different beliefs as if it isolated policy. Keep local rewards separate from whole-pair IMPs.

Freeze ranking/demotion rules and any multiplicity allocation for the new comparison schedule before collecting its data. Do not reuse the current substitution-test thresholds unchanged or mix its outcomes into a new direct-match estimate. The newest validated candidate remains provisional by default; inconclusive IMPs do not block the authorized successor fitting.

## Conditional 10,000-board decision for the current generation

User amendment, 9 November 2026: we may close the current run and train its successor at 10,000 completed paired boards if the result is a clear blowout. Review the complete contiguous 10,000-board prefix, using whole-pair IMPs, uncertainty and stability across blocks. Treat a clear win or a clear regression as potential grounds to finish early; a merely positive estimate or nominal significance alone is not the intended blowout. The user has not specified a numerical effect-size cutoff, so this is an explicit decision checkpoint rather than an automatic numerical stopping rule. If evidence remains inconclusive, continue toward the existing 25,000-board target.

At an early finish, preserve all completed and already-in-flight completed records, publish the actual cohort size and stopping decision, snapshot models/data/results, and have the owner train the successor from the retained data. Keep the original manifest and target as historical evidence; record an early-completion event rather than rewriting history or discarding excess records. The owner must provide a versioned early-boundary handoff because the current supervisor only trains automatically at its manifest target. No competing trainers. Apply the new two-version-per-match 4:2:1 design to the successor. Do not pool generations or describe an outcome-selected stopping interval as a fixed-sample confirmatory result.

## Delivery boundary

The direct-pair design changes future planning and is not implemented by the current collector. The separate 10,000-board review above applies to the current generation. Preserve the active g0001-bid40k manifest, source, models, completed results and existing score interpretation.

The owner must implement and test direct two-way pair scheduling/scoring in a separate versioned collector before launching the next generation. Pin its source and pair allocation in a new manifest and update the versioned boundary handoff explicitly. Required checks include swapped-seat score orientation, correct model assignment, deterministic disjoint family allocation, duplicate-free resume and separate per-pair reporting. Do not launch a second writer or trainer for the active run. The existing successor authorization remains in force; this is a requirement on its match design.


## Executed correction: direct matches in the current batch (9 November 2026)

The user explicitly corrected the earlier future-only scope. That restriction is superseded.
The substitution phase is permanently stopped after 3,235 completed paired boards.
The remaining 21,765 original, unused deal families now use direct A–B/A–C/B–C
matches, shuffled in seven-board blocks with weights 4:2:1. Actual allocations
are 12,438 AB, 6,218 AC and 3,109 BC. The same three frozen models, auctions,
32 samples and near-tie setting are retained. No mid-batch model training occurred.

The new collector is `bridge_harness/direct_arena.py`, dispatched by manifest
protocol `direct-pairs-v1`. It swaps whole partnerships, randomizes table order,
and reports independent pair scores. Local A-policy audits use B's policy on
A's own search estimates, including against C; C's different beliefs never
become a policy training contrast. Both tables may supply audits under a shared
CPU budget and a combined 64-fork cap. B–C games supply belief trajectories but
no A-policy audit labels. Audits do not contribute to match scores.

`ops/switch_direct_pairs.py` requires the old STOP and both free OS locks. It
copies frozen artifacts, removes all completed families from the remaining
cohort, freezes a new manifest and updates the shared pointer and handoffs.
Atomic receipts and replay validation remain in force. Restart only missing
indices from the new checkout. The former collector must never be resumed.

Training retains the 3,235 legacy families and the direct phase, validating
each with its original manifest. Their match statistics remain separate.
The overall training batch is still 25,000 deals. Direct results have no automatic
pooled demotion rule; the planned 10k review uses separate pair results and
must not pool legacy substitution scores. The successor training authorization
remains in force; new generation labels follow the frozen roster and require
component-hash inspection before claiming policy-only or belief-only effects.

Operational source checkout: `/workspace/scratch/a1f2b806f0ac/bridge-direct`.
Authoritative pointer: `/workspace/scratch/a1f2b806f0ac/bridge-arena/runs/mixed-fork-25k/current.json`.
Run: sibling `g0001-direct`. Read `match-format-change.json` before recovery.
Use two workers; check both OS locks before restarting. All four active arena/
belief monitors received the correction without changing their schedules.
