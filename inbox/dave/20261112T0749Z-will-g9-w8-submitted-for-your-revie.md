G9-W8 submitted for your review: W3 follow-up: run pytest-style test files; --prepare idempotent for all releases

will, 12 Nov 07:49 UTC. Task G9-W8.

PR #25 into feature/gen9. Fresh clone of feature/gen9 at 2c4c8a2: all 50 files, 381 passed, 0 failed; test_gen9_cards.py 18 of 18 under pytest; second --prepare: 13 of 13 already restored. This sandbox had tensorflow-cpu and h5py already, so 0 not run here.

Branch: feature/gen9-workflow-tests-2, commit 1c67bee.

Accept: `workq.py resolve G9-W8 --resolution accepted`. Send back: `workq.py reopen G9-W8 --note ...` (add `--same-holder` to return it to will).
