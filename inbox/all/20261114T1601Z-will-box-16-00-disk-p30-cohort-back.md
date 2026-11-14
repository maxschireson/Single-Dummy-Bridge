Box 16:00: disk P30, cohort back to ~184/h (4,716), Gen X Stu 700 (-0.11 ± 0.15), BEN pair 1,372

will, 14 Nov 16:01 UTC.

will, 14 Nov 16:00 UTC.

azure4 at 15:59: 8 of 8 cores busy, no change in jobs. The OS disk has been P30 since 15:20 (Max's word; my 15:25 line).
- **g9-cohort-azure4:** 4,716 of 10,000; 170 in the last 60 minutes and 92 in the last 30 (about 184 an hour), against 136 in the hour before. 0 failures. Ends about 15 Nov 21:00 at that rate.
- **Disk:** 826 writes/s at 6.6 ms (8.7 MB/s), 30 flushes/s, 19% busy; iowait 1%, CPU 12% idle. The cache is 30.6 GB, and its WAL is unchanged at 747 MB.
- **g9-genx-stu-azure4 (Gen X Stu):** 700 of 4,000; 53 in the last 60 minutes, 0 failures.
  - IMPs a board to Gen X Stu: -0.17 ± 0.20 against 8s-32 (349 boards), +0.27 ± 0.30 against 71s-32 (175), -0.38 ± 0.34 against 9a-32 (175). All three together: -0.11 ± 0.15.
- **g9-cohort-ben64-azure4:** 1,372 of 2,000; 35 in the last 60 minutes. Ends about 15 Nov 10:00.
- **Ladder:** refreshed 16:00 (90,690 boards). Gen X Stu is at +0.43, interval +0.09 to +0.77, on 699 boards.
- **Paused:** e9-0-n04 and e9-16-h-v-p. **Space:** 52 GB free.

Next line about 17:00.
