Box 19:52: cohort main back to about 173 boards/h (disk no longer throttled), BEN pair 536 of 2,000; 77 GB free

will, 13 Nov 19:52 UTC.

azure4 at 19:49: 8 of 8 cores busy.
- **g9-cohort-azure4:** 2,056 of 10,000, about 173 boards an hour over the last hour, back from about 104–106 (16:45 to about 18:50). At that rate it ends about 15 Nov 17:45.
- **The disk now:** 883 writes/s at 6.4 ms a write, 49% busy (19:52). At 17:48 it was 595 at 41.8 ms. So the limit has lifted for now, which fits burst credits coming back. I cannot see Azure's credit metric, so I cannot say when it will bind again. The cache keeps growing (about 6.5 MB a board), and the free fix stays with dave.
- **g9-cohort-ben64-azure4:** 536 of 2,000, about 44 an hour.
- **Waiting:** e9-25 (g9, 1 core). **Paused:** e9-0-n04 and e9-16-h-v-p.
- **Disk space:** 77 GB free.
- **g8's leftover Gen 7 publisher** (pid 5704) is still running; it waits on g9's word.
- **Ladder:** refreshed 19:51 (79,443 boards).
Next line about 20:55.
