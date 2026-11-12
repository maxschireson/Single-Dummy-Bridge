G9-W1 submitted for your review: Design note: work queue and experiment registry for a project that never stops

will, 12 Nov 07:10 UTC. Task G9-W1.

docs/gen9/workflow.md, about 1,500 words. Interface change in its first lines: I8 gains workq as the writer of lifecycle fields, five optional header fields and three checks; nothing else changes. Decisions in it for you: the optional fields; executor-ready sections and 'workq brief' (with a three-line start prompt that works for a sub-agent or a chat Max opens); a Result check at submit for experiments (Evidence, Sample, Revisit if); generation-free ids from the next channel on; value-for-effort ordering with a 20% exploration share and a cap of two open sweeps per area; a pinned GitHub issue as Max's phone view plus decision issues only when you raise them (not built until you agree); box leases in workq only after Gen 8 launches and with g7's and g8's agreement. Measured: read 0.7 s, write 2.4 s per change; the retry ceiling of about 700 writes an hour is an estimate. Starting W3 now.

Branch: feature/gen9-workflow-design, commit 57c43dd.

Accept: `workq.py resolve G9-W1 --resolution accepted`. Send back: `workq.py reopen G9-W1 --note ...` (add `--same-holder` to return it to will).
