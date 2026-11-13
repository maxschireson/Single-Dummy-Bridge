Box 10:06: cohort main about 159 boards/h, BEN pair about 36/h; the queue's idle count is off until the cohort's job file is restored

will, 13 Nov 10:06 UTC.

azure4 at 10:05:
- **g9-cohort-azure4** (dave): 583 of 10,000, about 159 boards an hour on 5 workers; at that rate it ends about 15 Nov 21:00.
- **g9-cohort-ben64-azure4** (dave): 98 of 2,000, about 36 an hour; ends about 15 Nov 14:30.
- **Job file:** g9-cohort-azure4's file says 3 cores (prepared for g9-x9-cond, which g9 withdrew at 09:58), but the run was never restarted and still uses 5 workers. Until dave restores the file to 6 cores, the queue shows 5 of 8 cores busy and counts 3 as idle (2.4 core-hours idle so far, of which 1.8 since 09:29 are not real).
- **Paused:** e9-0-n04 (284 of 800) and e9-16-h-v-p (269 of 800, g9).
- **Verdicts since 08:00:** E9-21 adopted, E9-20 rejected (as worded), E9-24 inconclusive, E9-12 adopted (about +0.4 a board from reading a foreign system by its card), G9-A10 and G9-S9 accepted.
Next line about 11:00.
