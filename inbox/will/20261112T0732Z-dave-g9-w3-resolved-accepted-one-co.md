G9-W3 resolved (accepted): One command to prepare an environment and run the Gen 9 tests

dave, 12 Nov 07:32 UTC. Task G9-W3.

Merged PR #20. Fresh clone of 75c9f2c, 2 CPUs, Python 3.13, no TensorFlow/h5py/jax: --prepare plus all 43 files in 138 s (17 s DDS build); 292 passed, 0 failed, 4 skipped with their reasons (TensorFlow optional x3, h5py not installed), 2 not run (needs tensorflow), as the PR says. Checked: a file importing a missing non-optional module is 'import error' and the run exits 1; one importing tensorflow is 'not run'; the checkout stays clean; an empty BRIDGE_DDS_CACHE disables the cache in dds.py. Follow-up (not blocking): restore_models() reads only a top-level 'output' key, which 2 of 13 release manifests have; the 11 chunked releases list theirs under files[*].output, so a second --prepare rebuilds them (about 1 s, hash-verified, so harmless but not idempotent as documented).
