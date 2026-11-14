Cohort refused 7e0edac7 (Pinned generation source changed); job failed at 09:08, spec untouched: please replace back to 46b7e004

will, 14 Nov 09:13 UTC.

**The cohort refused the new source, as you said it might. I stopped there, and the job is now `failed`.**

**What I did** (your 08:11 instructions):
- Drained the cohort with STOP at 09:01; it ended at 3,617 receipts, 0 failures.
- Removed STOP and ran `job retry`, which made the retry count 3. The box started it at 09:07:20 on `7e0edac7`.

**What happened:** `ops/run_gen9_cohort.py` resumed the manifest (`resuming 75b739377506`). Then `ops/gen5_runtime.py` refused in `verify_generation` (`bridge_harness/mixed_arena.py:122`):

```
if source_hash() != manifest['source_sha256']: raise ValueError('Pinned generation source changed')
```

The runtime itself checks the hash of `bridge_harness/`, and `dds_cache.py` is in it. It failed three times (exit 1), and boxq marked it `failed` at 09:08. The run folder is untouched: 3,617 receipts, the publisher's last push included them.

**Not changed:** I have not touched the spec. Replacing it is yours, and anything else would be working around the check.

**To get it running again:**
1. Replace the spec with the previous source, `feature/gen9-cohort` at `46b7e004`. The env line can stay or go, because that code ignores it. Keep 4 cores and 4 workers.
2. Tell me, and I retry it (count 4).

**Cores:** since 09:08, e9-25 has 1 core (your fix), Gen X Stu 2 and the BEN pair 2. When the cohort is queued again at priority 1 it takes the 3 free cores plus e9-25's: e9-25 is preemptible and has the lower priority, so the box stops it.

**Disk at 09:12, with the cohort down:** 62 writes/s at 2.7 ms, 0.5 flushes/s. So nearly all of the earlier load (570-830 writes/s, about 140 flushes/s) was the cohort's cache.

**For a later, new run only:** an un-pinned way to get NORMAL is to prepare a new run with the switch in its source from the start. Gen X Stu's run does that.
