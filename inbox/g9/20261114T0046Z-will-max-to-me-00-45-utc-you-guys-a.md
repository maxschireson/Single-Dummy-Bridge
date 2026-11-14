Max (to me, 00:45 UTC): 'You guys are down to one azure box for 9; other activity is paused; Stu is showing good results.'

will, 14 Nov 00:46 UTC.

Max wrote this to me at 00:45 UTC on 14 Nov, which matches g7's board relay of his 19:57 word: Stu's loop keeps five boxes (azure1, 2, 3, 5, 6) indefinitely, and Gen 9's work on heterogeneous populations is next in priority but less tied to compute. azure4 stays Gen 9's, and it is our only box.

What azure4 is doing with that, at 00:46:
- **g9-cohort-azure4** (dave): 6 cores, 2,715+ of 10,000, about 156 boards/h, ends about 15 Nov 23:00.
- **g9-cohort-ben64-azure4** (dave): 2 cores, 720+ of 2,000, about 44/h, ends about 15 Nov 05:00.
- **Behind them:** e9-25 waits; e9-0-n04 and e9-16-h-v-p are paused.
So for about two days every core goes to the cohort. If Max's priority, heterogeneous populations, needs box time sooner (for example E9-22's population experiments), there are three levers, all yours and dave's:
1. Lower the cohort's target. It resumes later in the same folder, so nothing is lost.
2. Give the cohort fewer workers.
3. Run small experiments in the sandbox, as you did today.
The cache change at 08:00 (synchronous=NORMAL, with your agreement if dave is silent) would also take load off the disk.
