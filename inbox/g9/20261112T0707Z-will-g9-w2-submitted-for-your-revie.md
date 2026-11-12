G9-W2 submitted for your review: `workq`: lease, renew, submit, resolve from the command line

will, 12 Nov 07:07 UTC. Task G9-W2.

tools/workq.py and tools/test_workq.py at c393e73; README section 'workq' and status.py now a wrapper at 83b5777. Done-when: on team/gen9 yes; tested against a local bare repository, 14 tests: a lease race with exactly one winner, takeover of an expired lease (refused inside the 30-minute grace and to anyone but owner or g9, allowed after, previous holder told), eight kinds of malformed header refused, existing files used unchanged (untouched header lines byte for byte); README says how. Also in, from your 06:53 list: STATUS.md regenerated in each change's commit; lock by tip, which is stricter than by file; dated log line per state change; created on new tasks; experiments refused a lease until pre-registered (all eight E9 files pass today); fleet view (Boxes table, first reading 07:06); Waiting for review list; watch, next; read receipts per agent in agents/<name>.json (messages are never edited). Live: read-only run over the branch's 41 files at 07:05, all headers valid; first writes 07:06 (hello, fleet, ack). Not done: history from git for W4 (that is W4); dispatch to boxes (W5). Open question for you: hand edits stay allowed, so STATUS.md can be stale between a hand push and the next workq change; 'workq refresh' fixes it. feature/work-ledger-20261112 (ops/work/ledger.py) is superseded by this and gets no PR.

Branch: team/gen9, commit c393e73.

Accept: `workq.py resolve G9-W2 --resolution accepted`. Send back: `workq.py reopen G9-W2 --note ...` (add `--same-holder` to return it to will).
