g9-boxq serving on azure4 since 15:03; d6-arrival running on all 8 cores since 15:04; rate check in ~10 minutes

will, 12 Nov 15:06 UTC. Task G9-W5.

From will, 12 Nov 15:06 UTC.

**`g9-boxq` has served on azure4 since 15:03 UTC**, on g8's release line of 14:59. It started beside `g8-publish`, which made its last push at 15:06, and I posted the start on the board.

**What is running.** `d6-arrival` has held all 8 cores since 15:04. Everything else waits, among them sam's four `g9-x2-*` bench jobs at priority 3.

**What the box has.**
- The jobs' Python is the box venv: tensorflow 2.21, h5py 3.14, numpy 2.5.
- The capsule is present, with 13 bots.
- 102 GB of disk and 27 GB of memory are free.
- Jobs can fetch github.com over https.

**One fault at the start, fixed.** The first deploy (15:02) stopped before changing anything. The boxctl config on the box names its remote `repo`, not `repo_url`. The fix is d987e96, and the second deploy ran at 15:03.

**Your rate check.** About 10 minutes into the job I will post its boards an hour against your estimate: 33 CPU-seconds a floor board and 21 otherwise.
