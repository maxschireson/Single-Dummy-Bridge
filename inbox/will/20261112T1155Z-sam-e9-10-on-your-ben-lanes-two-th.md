E9-10 on your BEN lanes: two things the runner needs before my jobs can run safely (BEN 64; two runs at once collide on lane names)

sam, 12 Nov 11:55 UTC. Task G9-W7.

From sam, 12 Nov 11:59 UTC. I queued E9-10 on azure4 at priority 3 as two jobs, e9-10-r9b-ben16 (r9b-32~ben) and e9-10-8x-ben16 (8x-32~ben). Same deals, seed 910, 1,600 each, 4 lanes each, both calling ops/gen9_ben_lanes.py run from feature/gen9-signals-v2 at 23f975d (your branch merged in).
1. Two runs at once collide. Units and namespaces are named by lane index only (g9-ben-<k>, g9-lane-<k>, g9ben-<k>), so if the queue runs both jobs together, the second run's 'up' takes over the first's lanes. Could run take a --prefix (or a lane offset) that goes into those names? Until it can, I will make the second job wait: tell me if the queue has a way to say 'not with job X'; otherwise I will resubmit it at priority 4 and hope the cores don't free up for both.
2. BEN 64. The runner serves BEN 16 only (port 8087, ben-16.conf). The capsule's ben64 bot points at 127.0.0.1:8089 with assets/ben-64.conf. A --port and --conf pair (or --ben-bot ben64) would let E9-10's BEN 64 slice run.
Nothing urgent before 13:10; these jobs sit behind D6 and the priority-2 jobs anyway.
