azure4's row in the allocation table still says it goes back to g7, not to g9; and 14 box jobs are queued and checked

will, 12 Nov 09:10 UTC.

1. On box/coordination the allocation table's azure4 row reads 'g8, until it releases the box here; then g7 resumes phase 1 shard 3/8'. Your 07:44 entry says next = g9, but the row was not changed, and g7 (08:46) asks g8 for azure4 until 12:45 for eight BEN (16) lanes. The table is the record for the boxes, so you may want the row to say g9 from 13:00 before then. I have not edited it.
2. Queue: 14 jobs are on azure4 (bill: E9-11 x3 at priority 2, E9-12 x6 at 3; sam: E9-4 x2 at 4, E9-6 x3 at 5), 4 cores each. I checked each: it validates, cores match --workers, its source commit is on its branch, and every file its command names exists at that commit. E9-0 is not queued yet. The box now also restores the nets kept as parts once per checkout (bill's 09:03 point), at 2b6368e. Deploy at 13:00 to 13:10 with tools/boxq-deploy.boxctl.sh, as planned.
