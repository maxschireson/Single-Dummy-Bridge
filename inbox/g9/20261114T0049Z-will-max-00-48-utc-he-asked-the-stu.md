Max (00:48 UTC): he asked the Stu team to give us their latest to put in the arena

will, 14 Nov 00:49 UTC.

Max to me at 00:48 UTC: 'I asked the Stu team to make sure you had access to their latest to put in the arena.' At 00:51 I asked loop and stu-dash on the board for:
- the bot id (stu2, or round 3's net when it lands);
- the branch and commit, its config and its nets with hashes;
- per-worker memory (they report 3 to 4 GB with bf16, and --recycle 20);
- which harness plays it;
- whom to measure it against first.

azure4 has 32 GB with about 9 GB in use, so memory fits a few of their workers. Cores do not fit: the cohort holds all 8. My proposal, once their bot is in hand, is a pair job of 2 cores (stu latest against 8s-32, or whichever opponent they name) beside the cohort trimmed to 4 workers, resuming in the same folder. Then a feed for the dashboard to register, as for the cohort. Your call and dave's on the trim; I prepare the job file and validate it either way.
