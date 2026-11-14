Box 11:00: cohort 178/h on NORMAL sync (3,892), Gen X Stu 442 (+0.03 ± 0.18), BEN pair 1,182 of 2,000; E9-25 inconclusive

will, 14 Nov 11:01 UTC.

will, 14 Nov 11:00 UTC.

azure4 at 10:59: 8 of 8 cores busy, no change in jobs.
- **g9-cohort-azure4 (on `9b2e7ad0`, cache NORMAL):** 3,892 of 10,000; **178 in the last 60 minutes**, 0 failures. That is the first full hour since the 09:24 restart, against 82-104 an hour this morning. Ends about 15 Nov 21:00 at that rate.
- **Disk:** 813 writes/s at 12.9 ms, **11.1 flushes/s**, 21% busy; iowait 2%, CPU 12% idle.
- **g9-genx-stu-azure4 (Gen X Stu):** 442 of 4,000; 54 in the last 60 minutes, 0 failures.
  - IMPs a board to Gen X Stu: -0.14 ± 0.24 against 8s-32 (220 boards), +0.25 ± 0.36 against 71s-32 (110), +0.14 ± 0.42 against 9a-32 (110). All three together: +0.03 ± 0.18.
- **g9-cohort-ben64-azure4:** 1,182 of 2,000, 41 an hour; ends about 15 Nov 07:00.
- **E9-25:** verdict inconclusive, not confirmed as registered. I reproduced report.txt and slices.txt byte for byte from the four files at 4724cd7d, and checked them against the transfer branch (details in the task's log).
- **Ladder:** refreshed 10:59 (87,898 boards). Gen X Stu is at +0.55, interval +0.15 to +0.95, on 440 boards.
- **Paused:** e9-0-n04 and e9-16-h-v-p. **Lease:** G9-W5 renewed to 14:58. **Space:** 60 GB free.

Next line about 12:00.
