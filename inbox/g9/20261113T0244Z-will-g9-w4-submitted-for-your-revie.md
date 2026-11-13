G9-W4 submitted for your review: Queue metrics: are there too few thinkers or too few executors

will, 13 Nov 02:44 UTC. Task G9-W4.

reports/queue-metrics.md and tools/queue_metrics.py (4 tests) on team/gen9 at 6ca28d5; reading of the first day in reports/queue-metrics-notes.md: no shortage of executors; leases far inside their boxes; the constraint was the architect's availability (08:07-11:23 and the evening), eased by the 11:53 rules and the tools that enforce them; azure4 0.0 idle core-hours from 15:03; suggestions: an evaluation lead, automatic reviewer reassignment for a silent peer, g9 not holding experiment leases, per-pair sandbox_rate in job files.

Branch: team/gen9.

Accept: `workq.py resolve G9-W4 --resolution accepted`. Send back: `workq.py reopen G9-W4 --note ...` (add `--same-holder` to return it to will).
