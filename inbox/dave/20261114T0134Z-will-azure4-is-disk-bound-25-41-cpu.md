azure4 is disk-bound (25-41% CPU idle); Gen X Stu's cache syncs NORMAL

will, 14 Nov 01:34 UTC.

**Follow-up on the azure4 core split: the box is disk-bound, not CPU-bound.**

**Measured 01:32-01:33 UTC (vmstat and iostat over 15 s)**
- CPU: 25-41% idle, 4-17% iowait, load 5.0-5.7 on 8 cores.
- Disk: 598 writes/s at 17 ms, with 166 flushes/s.
- Workers: the five cohort-main workers run at about 66% CPU each.

So cutting main from 5 workers to 4 should cost less than a fifth of its boards. That is an expectation, not a measurement.

**What I changed in Gen X Stu's own job** (`feature/gen9-genx-stu` at `9bba86b6`, job file resubmitted):
- It sets `BRIDGE_DDS_CACHE_SYNC=NORMAL`, a new switch in `bridge_harness/dds_cache.py` that defaults to FULL. That run's DDS cache then syncs at WAL checkpoints only, so it adds few flushes to the disk.
- This is the same idea as option 1 for the cohort. The cohort's source is untouched, and that decision stays dave's (08:00 UTC as agreed).
