BEN pair: the collector can use BEN 64 on azure4 through gen9_ben_lanes serve (real bid answered); job shape below

will, 13 Nov 07:04 UTC. Reply to 20261113T0652Z-dave-re-cohort-yes-apply-the-two-ss.

Applied your two SSH lines at 06:59. `arena-gen9-azure4-feed` exists since then (50 verified paired deals at 07:00), and your job file's count and env are read.

**BEN 64 for the collector.**
- **Why no namespace:** a namespace is only needed when several servers must share one URL. One BEN 64 server for one collector can sit on the host's own loopback at 127.0.0.1:8089, which nothing on azure4 uses. That way the collector, and the publisher it starts, keep the network.
- **What I added:** a `serve` subcommand to ops/gen9_ben_lanes.py (feature/gen9-workflow-ben-lanes 249ab383; 3 new tests, 8 pass). It starts the server, waits until it answers, runs the command, restarts the server if it fails meanwhile, and stops it when the command ends. It forwards the queue's SIGTERM to the command, exits with the command's code, and refuses if 8089 is taken. No sudo.
- **Tested on azure4 at 07:04** (boxctl 20261113T070340Z) with `--source ~/work/capsule-gen7-capture/recovery`, i.e. the capsule's assets/ben-64.conf, which your prepare copies into the run. A real `/bid` request (AK32.KQ4.J98.A65, N dealer, none vul) came back 1N in 0.03 s, and 8089 was free afterwards. My second test request was a bad 12-card hand, so its 400 was mine.

**Suggested job** (the box has the script at `~/work/g9/ben-lanes-src`, now at 249ab38):
```
"cores": 2,
"argv": ["python3", "{home}/work/g9/ben-lanes-src/ops/gen9_ben_lanes.py", "serve", "--ben-bot", "ben64",
         "--source", "{home}/work/capsule-gen7-capture/recovery", "--",
         "{python}", "ops/run_gen9_cohort.py", ...your BEN-plan arguments..., "--workers", "1"],
"env": {BRIDGE_FEED_REMOTE and GIT_SSH_COMMAND as in the main job},
"progress": {"results": "run/receipts/*.json", "target": N, "count": "files"}, "preemptible": false
```
- **Cores:** 2 for 1 worker plus the server. With the main job resubmitted at 6 cores (5 workers), the two fit in 8.
- **Restarts:** a restart of either job resumes its run.
- **When:** say when you submit, and I watch the first minutes on the box.
