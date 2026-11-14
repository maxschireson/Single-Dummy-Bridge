Box 10:00: cohort back at ~164/h on NORMAL sync (flushes 140/s -> 13/s), Gen X Stu 388 (+0.01 ± 0.20), BEN pair 1,141 of 2,000

will, 14 Nov 10:00 UTC.

will, 14 Nov 10:00 UTC.

azure4 at 09:59: 8 of 8 cores busy.
- **g9-cohort-azure4:** running since 09:24 on `9b2e7ad0`, with the DDS cache syncing NORMAL (Max 09:17; my 09:33 message).
  - 3,714 of 10,000, 0 failures. 97 boards in the 34 minutes since the restart; 82 in the last 30 minutes, about 164 an hour, against 82-104 an hour on the throttled disk this morning.
  - Ends about 16 Nov 01:00 at that rate.
- **Disk (g9 asked for these):** 707 writes/s at 8.0 ms, **12.7 flushes/s (about 140 before)**, 17% busy. iowait 1%, CPU 7% idle: the box is now CPU-bound, not disk-bound.
- **g9-genx-stu-azure4 (Gen X Stu):** 388 of 4,000; 28 in the last 30 minutes, 0 failures.
  - IMPs a board to Gen X Stu: -0.11 ± 0.25 against 8s-32 (193 boards), +0.32 ± 0.40 against 71s-32 (97), -0.04 ± 0.47 against 9a-32 (96). All three together: +0.01 ± 0.20.
- **g9-cohort-ben64-azure4:** 1,141 of 2,000, about 40 an hour; ends about 15 Nov 07:00.
- **Paused:** e9-0-n04 (it took the free cores at 09:19 and was paused at 09:24) and e9-16-h-v-p. **Done:** e9-25 (g9).
- **Ladder:** refreshed 09:59 (87,270 boards). Gen X Stu is at +0.56, interval +0.13 to +0.98, on 386 boards.
- **Space:** 61 GB free.

Next line about 11:00.
