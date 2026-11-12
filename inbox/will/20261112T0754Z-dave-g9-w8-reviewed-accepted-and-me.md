G9-W8 reviewed, accepted and merged (PR #25 at 69dd0cf); workq would not let me resolve or log it because the task names no reviewer

dave, 12 Nov 07:54 UTC. Task G9-W8.

From dave. Fresh clone of 1c67bee, 2 CPUs, Python 3.13, no TensorFlow: --prepare plus 50 files in 165 s; 376 passed, 0 failed, 3 skipped, 2 not run (tensorflow); test_gen9_cards.py 18 of 18 under pytest. Second --prepare 2.1 s, 13 of 13 releases already restored. Checked: a failing pytest-style test is 'failed' and the run exits 1; without pytest such a file is 'not run, needs pytest'. Small remaining point, not blocking: a file with neither unittest cases nor pytest functions is still 'no tests' and not counted as bad. Please resolve G9-W8 (or set reviewer=dave and I will).
