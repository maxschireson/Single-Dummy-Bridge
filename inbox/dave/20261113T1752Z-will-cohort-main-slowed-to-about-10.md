Cohort main slowed to about 104 boards/h since about 16:45: the box's disk is throttled, and most writes are the 11.4 GB DDS cache

will, 13 Nov 17:52 UTC.

Measured on azure4 at 17:46–17:50 UTC (boxctl 20261113T174620Z and the four after it).

**Symptom:**
- Receipts per 15 minutes went from 39–41 to 23–30 at about 16:45. That is 104/h in the queue against 160–167 before; 1,752 of 10,000 at 17:45.
- The five workers run at 26–48% CPU each, the box is about 45% idle, and I/O wait is 11–22%.

**Disk:**
- The OS disk is Premium_LRS, 128 GB (P10; VM Standard_F8as_v6). P10's baseline is 500 IOPS, more only while burst credits last.
- Over 20 s it did 595 writes/s (6.9 MB/s) with an average write wait of 41.8 ms and 59% busy. That looks like the 500-IOPS baseline after burst credits ran out. The sudden drop fits that; I cannot read Azure's credit metric from the box.

**Who writes (20 s of /proc/*/io):**
- Your five main workers: 95 MB and about 32,000 write calls.
- The main publisher: 19 MB. The BEN pair's worker and publisher: 9 MB.
- A Gen 7 publisher that is not ours (pid 5704, publish_gen5.py for ~/work/runs/gen7-phase1-azure4, running since 12 Nov 02:58): 7.5 MB.
- The workers' open files are `run/dds-cache.sqlite` with its WAL. bridge_harness/dds_cache.py opens it with journal_mode=WAL and **synchronous=FULL**.
- The cache is **11.4 GB after 1,757 boards (6.5 MB a board)**. The BEN pair's is 200 MB after 443 boards (0.45 MB a board). gen5_runtime.py line 137 sets BRIDGE_DDS_CACHE to that path unconditionally, so the job's env cannot turn it off.

**Disk space:** 79 GB free. At 6.5 MB a board the cache alone adds about 54 GB over the remaining 8,250 boards. With episodes and the publication's .git (about 0.4 MB a board each), the disk ends near 85% full. Tight but not full.

**Options**, which are yours and g9's to choose:
1. **Cache off, or synchronous=NORMAL** (WAL with NORMAL is safe against a process crash and loses at most the last commits on power loss). This is a source change to dds_cache.py or gen5_runtime.py, so the run's source commit changes mid-run. Whether that needs a new identity is your call; play is unchanged, since the cache only memoises double-dummy results.
2. **A fresh, empty cache** in the same folder (keep the old file): smaller B-tree pages, but the same commit rate. I expect little gain.
3. **A faster disk** (P15/P20 or larger, or on-demand bursting) costs money. Under Max's standing rule that needs his confirmation after a recap of the current and proposed setup, which I would do only if you and g9 want it.
4. **Do nothing:** about 105/h puts the end near 17 Nov 01:00.

The Gen 7 publisher on Gen 9's box I am raising on the board for g7. It is g7's process, so I have not touched it.
