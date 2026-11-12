G9-W3 submitted for your review: One command to prepare an environment and run the Gen 9 tests

will, 12 Nov 07:24 UTC. Task G9-W3.

PR #20 into feature/gen9. scripts/run_tests.py: --prepare builds DDS if missing or stale, installs numpy/scipy if missing (--with tensorflow,h5py,jax for the heavy ones), restores the 13 nets if missing; each test file in its own process with a time limit; a missing optional package is 'not run, needs X', never a pass or failure; skips listed with reasons; markdown and JSON reports. Done-when: PR yes; line in docs/gen9/README.md yes; one fresh-sandbox run: fresh clone of feature/gen9 at 297a913, 2 CPUs, no TensorFlow/h5py/jax: 185 s end to end, 292 passed, 0 failed, 4 skipped, 2 not run; with --with tensorflow,h5py (tensorflow-cpu) the five files holding those six pass all 53. So all 298 pass once those two are installed. For sam's sandbox (no gh, no jax): the runner needs neither; jax is used by no test on feature/gen9. Report: reports/gen9-test-run-2026-11-12/README.md. Not tested: a box run (estimate 80 to 90 s, floor set by test_gen7.py), BEN. Note: the DDS build is not byte-reproducible across directories.

Branch: feature/gen9-workflow-tests, commit 75c9f2c.

Accept: `workq.py resolve G9-W3 --resolution accepted`. Send back: `workq.py reopen G9-W3 --note ...` (add `--same-holder` to return it to will).
