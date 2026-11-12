PR #28 reviewed and merged (a file with no tests now fails the run; checked on a fresh clone of 5625123)

dave, 12 Nov 08:56 UTC.

From dave. Empty test file: 'no tests', exit 1. test_system.py (24) and test_gen9_cards.py (18 under pytest): exit 0. Your D4 follow-ups (sim KeyError message, the *.log ignore that dropped demo-run.log, gzip mtime in snapshots) are fixed on my next branch, feature/gen9-arena-arrival, which carries D7 and the D6 rehearsal.
