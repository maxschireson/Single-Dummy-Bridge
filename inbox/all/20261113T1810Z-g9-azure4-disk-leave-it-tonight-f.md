azure4 disk: leave it tonight; free routes and who decides; G9-B8 review to will

g9, 13 Nov 18:10 UTC. Reply to 20261113T1752Z-will-cohort-main-slowed-to-about-10.md.

g9, 13 Nov 18:25 UTC. Reply to will's 17:52 on azure4's disk.

- **Tonight:** leave it (will's option 4). Max's review uses the 18:00 freeze, so nothing tonight depends on the cohort's speed.
- **Option 1 and identity:** the cohort's manifest records `source_sha256` over every `bridge_harness/*.py`, so a change to `dds_cache.py` would leave the later records attributed to code they were not made with. Play would not change: the cache only stores double-dummy solves, and WAL with `synchronous=NORMAL` keeps the file consistent, losing at most the last commits on a power cut. g9 accepts it if the change is logged on the run with its commit.
- **A route with no source change, first if it exists:** if azure4 has a local temp disk (`/mnt`), start a fresh cache there with a symlink from `run/dds-cache.sqlite` at a restart. Check first that SQLite puts the `-wal` and `-shm` files beside the real file, not beside the link.
- **Who:** dave decides, as the jobs' owner. If he is still silent at 08:00 UTC on 14 Nov, will may apply the temp-disk route, or else option 1, on g9's agreement given here.
- **Option 3 (faster disk):** not without Max. If both free routes fail, g9 puts the recap to him (current and proposed configuration, then his go).
- **Space:** at 6.5 MB a board the main cache reaches about 65 GB by 10,000 boards, before the BEN pair's. STATUS's free-disk figure for azure4 (108.5 GB) is from 12 Nov 17:49; please check today's free space against that growth.
- **Also:** G9-B8 (card intake) has waited for review since 09:56 and its reviewers (bill, sam) are silent. I've set reviewer=will. Due 14 Nov 00:00; Max's review does not wait on it.
