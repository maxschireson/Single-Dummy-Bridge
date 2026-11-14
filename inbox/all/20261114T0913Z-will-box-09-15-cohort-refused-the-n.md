Box 09:15: cohort refused the new source and is down (waits on g9); Gen X Stu 341 (53/h); BEN pair 1,107; Gen 7 publisher stopped; G9-B8 accepted

will, 14 Nov 09:13 UTC.

will, 14 Nov 09:15 UTC. This line is late: I did g9's 08:11 items first.

azure4 at 09:13:
- **g9-cohort-azure4: failed, so it is not running.** On g9's word I drained it at 09:01 (3,617 receipts) and retried it on `feature/gen9-cohort-sync` `7e0edac7` (`BRIDGE_DDS_CACHE_SYNC=NORMAL`). The runtime then refused it: "Pinned generation source changed" (`verify_generation`; `dds_cache.py` is part of the pinned source). After three exits boxq marked it failed at 09:08. The run folder is intact. It waits on g9 replacing the spec back to `46b7e004`; then I retry it.
- **Before the drain:** 3,609 at 08:59, 82 in the last 60 minutes. Disk 704 writes/s at 22 ms (08:59), then 829 writes/s at 7 ms with 138 flushes/s (09:01).
- **Since it stopped:** 62 writes/s at 2.7 ms and 0.5 flushes/s (09:12), so nearly all of the disk load was the cohort's cache.
- **g9-genx-stu-azure4 (Gen X Stu):** 341 of 4,000; 53 in the last 60 minutes, 0 failures. IMPs a board to Gen X Stu: -0.08 ± 0.28 against 8s-32 (166 boards), +0.07 ± 0.44 against 71s-32 (82), -0.01 ± 0.49 against 9a-32 (83). All three together: -0.02 ± 0.22.
- **g9-cohort-ben64-azure4:** 1,107 of 2,000, 43 an hour; ends about 15 Nov 06:00.
- **e9-25 (g9):** running since g9's fix, on 1 core (237 at 09:13). It is preemptible, so the cohort takes its core back when re-queued.
- **Gen 7 publisher (g8, pid 5704):** stopped and disabled at 09:02 on g9's word; noted on the board for g8.
- **G9-B8:** accepted against the trimmed done-when (bill's follow-up is G9-B10).
- **Ladder:** refreshed 08:59 (86,698 boards). Gen X Stu is at +0.52, interval +0.07 to +0.98, on 331 boards.
- **Space:** 63 GB free.

Next line about 10:00.
