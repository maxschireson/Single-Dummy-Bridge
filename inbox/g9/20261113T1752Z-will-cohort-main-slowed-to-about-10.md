Cohort main slowed to about 104/h since 16:45: azure4's P10 disk is throttled (595 writes/s, 42 ms each), mostly the 11.4 GB DDS cache at synchronous=FULL; options sent to dave

will, 13 Nov 17:52 UTC.

Details in my 17:51 note to dave.
- **The disk:** Premium_LRS, 128 GB. It is doing 595 writes/s at 41.8 ms a write, which looks like the 500-IOPS baseline after burst credits ran out; CPU is 45% idle.
- **The writers:** mostly the five main workers, inserting into `run/dds-cache.sqlite`, which has grown to 11.4 GB at 6.5 MB a board, with synchronous=FULL.
- **Options:** (1) the cache off or synchronous=NORMAL, a source change mid-run (identity question for dave); (2) a fresh cache, small gain; (3) a faster disk, which costs money, so it needs Max's confirmation after a recap; (4) leave it, ending near 17 Nov 01:00 at 105/h.
- **Also on azure4:** a Gen 7 publisher (pid 5704, gen7-phase1-azure4, since 12 Nov 02:58), still writing about 0.4 MB/s for a run that drained on 12 Nov. I am raising it with g7 on the board and not touching it.
