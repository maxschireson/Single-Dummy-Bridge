Cohort running again on changed code (Max 09:17): source-amendments in the run folder; flushes 140/s -> 13/s

will, 14 Nov 09:33 UTC.

**The cohort is running again since 09:24 UTC, on the changed code with the cache syncing NORMAL. Max's word, 09:17: "Fix it so that it can run with changed code. Producing the boards is more important."**

**The fix: branch `feature/gen9-cohort-amend` at `9b2e7ad0`.** That is `7e0edac7` plus `check_source` in `bridge_harness/mixed_arena.py`.
- The pinned source passes as before.
- A changed source passes only if the run folder's `source-amendments.json` lists its sha256 with a reason. The accepting entry is logged.
- Anything else is refused, and the message names the refused hash in full.
- The manifest identity, the runtime files, the bots and the corpus are all still checked. tests/test_source_amendments.py has 5 tests.

**On the box:**
- **Spec:** source `9b2e7ad0`, and the job now also publishes `run/source-amendments.json`. A direct commit (`8c0d4cb`) on Max's word.
- **Hash:** the first start refused as designed and named source `3f3c01afe8b6...`. I computed the same hash in the job's checkout.
- **Amendment:** written to `{out}/run/source-amendments.json`, with the reason, Max's and your words, and 3,617 receipts before. `verify_generation` then passed on the box, and the retry (count 5) started at 09:24:31.
- **e9-0-n04:** it had picked up the free cores at about 09:19. Its state is now paused (4 cores).

**First numbers at 09:32:**
- **Cohort:** 3,638 receipts, 0 failures; 21 in the first 7 minutes. Not yet an hourly rate.
- **Disk:** 497 writes/s at 10.6 ms, **12.9 flushes/s (about 140 before)**, 17% busy (50-77% before); iowait 1%, CPU 12% idle.

g9: the spec is yours to change back if you want. Gen X Stu, the BEN pair and the rest are unchanged.
