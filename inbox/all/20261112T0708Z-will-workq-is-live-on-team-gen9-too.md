workq is live on team/gen9 (tools/workq.py): lease, submit and message with it

will, 12 Nov 07:08 UTC.

Nothing you have done needs redoing: hand edits still work, and the tool reads them.

To use it (Python 3.8+ and git; it keeps its own clone in ~/.cache/workq and never touches your checkout):

    git fetch origin team/gen9 && git show FETCH_HEAD:tools/workq.py > /tmp/workq.py
    Q="python3 /tmp/workq.py --as <your name>"
    $Q hello --role "<role>" --session <link>      # once
    $Q watch                                       # each check-in: changes, unread mail, leases ending
    $Q lease G9-B2 --hours 3 | $Q submit G9-B2 --branch ... --commit ... --note ... | $Q send g9 "..." --body ...

What it adds over the hand protocol: a lease, submit or resolve is refused rather than half-applied
when someone else changed the branch first; it writes the dated log line; it tells the reviewer on
submit; STATUS.md is regenerated in the same commit, so please stop editing STATUS.md by hand. If
you edit task files by hand, `$Q refresh` brings STATUS.md back in line. Experiments are leased only
once their hypothesis, metric and population, compute cap and stopping rule are filled (all eight
are). Everything is in README.md, section "workq". Problems with the tool: `$Q send will ...`.
