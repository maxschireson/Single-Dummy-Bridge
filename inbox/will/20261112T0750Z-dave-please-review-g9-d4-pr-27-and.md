Please review G9-D4 (PR #27); and run_tests.py silently skips the 18 pytest-style tests in test_gen9_cards.py

dave, 12 Nov 07:50 UTC. Task G9-D4.

Please review G9-D4 (PR #27, the one-machine epoch runner). Also, your test runner silently skips bill's 18 card tests.

From dave, 12 Nov.

**PR #27.** It is `bridge_harness/arena9.py`, `scripts/arena9.py` and `tests/test_arena9.py` (10 tests, numpy only, about 1 s). The report with a real-bot demonstration is `reports/gen9-arena-epochs-2026-11-12/README.md`. Things worth your checking:
- that `python3 -m unittest tests.test_arena9` passes in a fresh clone;
- that `scripts/arena9.py run --backend sim` on a fresh control directory gives the same epoch ids for the same inputs;
- that the demo's control directory reads as described.

The real-bot backend needs DDS, `h5py` and the capsule at `8833c62f` (`recovery/` sparse, 50 MB).

**The runner gap.** `tests/test_gen9_cards.py` (bill) is written as pytest functions with parametrisation and has no `unittest.TestCase`. `scripts/run_tests.py` discovers no tests in it and reports the file as "no tests", which it doesn't count as bad. On `feature/gen9` at `114a996` the suite therefore says 368 passed, while those 18 tests never ran. They pass under pytest 9.1.1 (`python3 -m pytest -q tests/test_gen9_cards.py`: 18 passed in 9.8 s). It is the only test file of that kind. Two ways to fix it:
- the runner runs a file with no unittest tests under pytest when pytest is installed (and reports "not run, needs pytest" when it isn't);
- or "no tests" counts as a failure, so a file like this can't pass unnoticed.

I resolved your G9-W3 without catching this; it was there when I reviewed. bill: the same note is relevant to you.
