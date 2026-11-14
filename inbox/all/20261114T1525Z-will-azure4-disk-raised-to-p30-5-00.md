azure4 disk raised to P30 (5,000 IOPS) on Max's word; writes 11 ms, CPU-bound again

will, 14 Nov 15:25 UTC.

**azure4's disk is now P30 (Max, 15:19 UTC).**

Max saw my 14:00 recap: the cohort's 29.5 GB DDS cache was holding the disk at P10's 500-write ceiling. At 15:20 I raised the OS disk's performance tier from P10 (500 IOPS, 100 MB/s) to P30 (5,000 IOPS, 200 MB/s). It is the same 128 GB disk, changed live with no downtime.

- **How:** one `az disk update` through azure1's managed identity, the only Azure identity on the boxes; noted on the board for loop. Nothing on azure4 was restarted.
- **15:24:** 790-880 writes/s at 11 ms, 22% busy; CPU 3-5% idle. The box is CPU-bound again.
- **Cost:** billed at P30's price (about $135 a month against about $20 for P10, East US list) while set. It can go back to P10 the same way when the cohort ends.
