# Mixed branching arena launch — 9 November 2026

The first production generation is running for **25,000 unique contracted boards**.
Latest verified snapshot: **63 completed pairs**, **358
audited deviations**, **484 complete table trajectories**. These are startup
counts, not a playing-strength conclusion. The live state is authoritative.

- Checkout: `/workspace/scratch/a1f2b806f0ac/bridge-arena`
- Active-generation pointer: `runs/mixed-fork-25k/current.json`
- Initial generation: `runs/mixed-fork-25k/g0001`
- Source: branch `research/mixed-fork-generations`; implementation commit
  `99a4ebb3e8232051219cea00df1ab61dbb59bc5d` (local corresponding commit `600929e`).
- Initial supervisor execution session: `25023`; four worker processes;
  240-second dispatch slices, finishing admitted in-flight boards.
- Newest validated version begins first provisionally. At 25k, fit both
  components and prepare the next 50k generation even if IMP evidence is
  inconclusive. Preserve all prior versions and evidence.

## Verified before launch

Fifteen focused tests passed: public information boundaries and seat rotation;
NumPy/TensorFlow equivalence; random-audit independence from gain claims;
recursive compute/depth bounds; actual bridge replay and IMP orientation;
corrupted-record rejection; geometric historical weights; provisional adoption,
negative-evidence demotion, and inconclusive-boundary advancement, unchanged-component deduplication, and
retention of the actual best after a failed successor fit.

A separate **24-board real-DDS smoke** completed **205 full trajectories** and
**157 nonidentical audited deviations**, including **93 recursive deviations**.
All saved plays and counterfactual scores replayed correctly. The collector
resumed across bounded invocations and refused a simultaneous writer. None of
these smoke deals are in the 25k cohort.

The smoke export produced 107 train and 50 validation IMP contrasts, and 1,389
train and 669 validation belief positions plus a tiny existing three-domain
fixture. A two-epoch policy fit completed, with deployment/training contrast
error 4.66e-10. A two-epoch belief fit restored Adam at update 5,658 and correctly
retained the parent when its validation gate failed. These are functional
checks; no smoke-trained model is deployed in production.

## Instructions for monitoring agents

Read `current.json`, then the active `state.json`, `heartbeat.json`, and
`supervisor.json`. A live automation invocation is not proof of a live worker.
Check both `.supervisor.lock` and `.writer.lock` using nonblocking flock without
deleting either file. One agent may restart the supervisor only if its lock is
free; others should inspect read-only. Use the pinned checkout; do not edit its
source during an active generation. Resume command is in the architecture doc.

Count committed episode files/receipts and compare across observations. Use
`status --audit` for a full replay/receipt audit when indicated. Preserve failed
boards and inspect failures rather than dropping them. On whole-environment
loss, restore the checkpoint and dependencies before resuming; do not fabricate
progress from logs. Take consistent SQLite backups, never copy live WAL files.

The original v2 collection remains stopped at **8,315** boards. The old
150-board random-fork pilot is now marked STOP because this generation replaces
it. Do not restart either, nor the superseded unforked 200-board mixed block.
Do not alter the separate DDS bidding, BEN, or 64-versus-32 comparisons.

The supervisor owns both generation-boundary trainers. Belief monitoring agents
should inspect these fits, not launch a parallel independent production fit.
The current parent belief dataset remains an external frozen dependency at
`/workspace/scratch/9357bfc2ac0b/bridge-belief-sizes/runs/belief-sizes-v1/data`;
its recovery is the existing `Bridge_Belief_Two_Sizes_2026-11-09.zip` archive.

[Model results](v2_network_results_2026-11-09.md) ·
[Architecture](../docs/mixed_fork_generations.md)

The supervisor handoff now uses `ops/supervise_mixed.py supervise`. Its separately
pinned transition prevents unchanged failed components from re-promoting a
demoted candidate. The original collection source and generation manifest are
unchanged; all completed records are preserved.
