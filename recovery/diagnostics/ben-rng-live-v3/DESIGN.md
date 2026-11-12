# Diagnostic live collector and crash continuation

Diagnostic only. Production 65a remains stopped with unresolved 003062. Candidate 1bd stays STOP. No production commits or promotion.

## Live V3 experiment

The driver connects three actual normal ProcessPoolExecutor futures and the candidate BEN per-board worker/server executor to an accepted-record journal. It uses frozen production play/validate/receipt/state/export functions. BEN runs the isolated claim RNG wrapper, which is an explicit behavior change relative to unchanged production. Before server startup the accepted RNG is copied to a private working state. Only successful worker and server lifecycle completion permits the episode, receipt and resulting RNG to enter the accepted journal. Normal commits carry the accepted BEN state unchanged.

Eight newly played diagnostic records: BEN1082 and BEN2561, self1930 through1935. After the first four completions the journal is copied, exported and restored. A separate subprocess continues with BEN2561 and three new self boards. The five records with prior references (1082,2561,1930/31/32) exactly match root/tie-audit cards, probabilities, auctions, assignments, seeds and scores. Final RNG bytes exactly match the prior persistent-server isolated-protocol reference. All eight pass full runtime replay. The first phase commit order includes normal completions both before and after the BEN commit. Restore/export counts, statistics, identities and allocation agree. BEN workers exit0; servers exit0 after intentional shutdown. Shared OOM counter is32 throughout this test, compared with28 in the previous pass; that intervening change has no victim attribution.

## Crash continuation correction

The preserved V3 adapter uses sequence-derived generation directories and a fixed NEXT marker. A SIGKILL after episode write preserves the old accepted state but leaves a directory that blocks continuation with FileExistsError. resume-result.json records this failure. Changing generation names alone also leaves a collision at NEXT after next_fsync; the failed log and intermediate adapter are retained.

adapter_v31.py uses unique generation and temporary-marker names. It preserves orphan files and traverses only CURRENT's accepted chain. Twenty actual SIGKILL tests, ten BEN and ten normal, verify old-or-complete-new state at each write boundary, successful subsequent continuation, duplicate rejection if already committed, exact RNG, and agreement with the real exporter. These tests reuse records newly played by V3; they are transaction tests, not additional live plays. V3.1 was not used in the earlier live futures experiment.

## Remaining gates

No adoption or unchanged-production equivalence is established; dead-server RNG is unavailable. Before adoption, exercise V3.1 end-to-end with a fresh isolated-protocol run, injected server/worker failures and collector interruption while work is in flight, then restore and continue against a persistent reference. Validate immutable runtime/protocol binding and snapshot publication under concurrent commits. Current production's episode scanner must never scan unaccepted journal directories or reconstruct their receipts. Power-loss behavior, long-run scaling of the nested marker chain, and production migration remain unvalidated. Do not clear003062 or restart production unchanged.

Source digests are in diagnostic-manifest.json. Regenerable DDS caches were moved outside the archived diagnostic directory. All actual records, journal states, snapshots, exports, drivers, failure evidence and lifecycle logs are retained here.
