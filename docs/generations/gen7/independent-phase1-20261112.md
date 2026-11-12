# Independent collector: Gen 7 phase 1

Authorized by the phase 1 handoff on main at `62bd8a2` and the user's standing instruction to apply collection handoffs to this collector. Phase 2 stays closed.

Source run: `/workspace/work/gen6-fast-selfplay`, immutable identity `63d7bee704eae61f070af1dca0476e2171b66b4fb084a1b78c11df18d76ed5e7`. Successor: `/workspace/work/gen7-phase1-independent`. Feed: `arena-gen7-phase1-independent-feed`. The successor consumes only unplayed source families; old episodes and receipts stay in their original feed.

The fast-only source retained only Gen6 fast, BEN16 and the audit reference. `prepare_gen7_alpha.py --actor-source /workspace/work/gen6-gen7-capture-ben64` restores exact historical actors from the verified direct predecessor. It requires every retained actor to be identical and refuses artifact collisions; this argument supplies actors, never deals. Its manifest records both sources. BEN64 still uses the original frozen bidder and 64-sample config.

`configs/round7-independent-phase1.json` is the authorized full five-pair plan with explicit generation 7 labels. Policy v4 and all cardplay parameters are unchanged from the shared plan. Generation labels affect reporting only. The exporter includes common/native/play/bidding/total views for generation 7.

The collector's existing gap capture and guess-size logging are ported verbatim into this main-based checkout; main did not include them. Per-band 2, edges 0.125/0.5, extra CPU share 1.5, tie probability 0.5 remain unchanged. BEN has no forks. No models are trained. The watchdog derives local services from the frozen actor specs and supports BEN16 at8087 and BEN64 at8089. Publication includes the preparation/preflight code and plan in the recovery capsule.

Validation: 54 upstream Gen7 tests passed before launch integration, the new actor-ancestry rejection test passed, and all 11 capture tests passed, including identical root/audit cards with capture off/on, dedicated RNG draws, propensities, budget skips and legal forced continuations. A real-network unpublished preflight covers the historical anchors, Gen6 and BEN64; an additional BEN16 check runs before launch. Preflight episodes are not published as completed arena boards.

Phase 1 ends when pooled family-deduplicated completed boards reach 2,000 in each of the five pairs. The hourly collection watcher checks that rule and writes STOP for this collector at that boundary; it must not open phase 2. The shared runtime has no per-pair target, so paired counts may exceed 2,000 while slower anchors finish. Dashboard intervals remain descriptive.

Recovery follows `environment.json`, `handoff.json` and `RECOVERY.md` in the new run and feed. Preserve locks and STOPs, verify frozen source/model hashes, and do not restart the drained Gen6 predecessor. Other collectors are outside this cutover.
