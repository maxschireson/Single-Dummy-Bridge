G9-X2 asks you for box time: three bench jobs at priority 3, 4 cores each, ready to submit; I submit them at 13:30 unless you say otherwise

sam, 12 Nov 12:39 UTC. Task G9-X2.

From sam, 12 Nov 12:50 UTC.
g9's G9-X2 (Gen 9 readers on p41's reading bench, scored in double-dummy tricks saved) says: solve in the sandbox for two hours, then ask will for a box job (priority 3) for the rest. The sandbox is solving now (BEN 64: about 30 s a table, it will finish its 300 there; BEN 16: 38 to 850 s a table, it will not). Three job files, all on feature/gen9-reading-bench at 8075a34, each one argv of scripts/gen9_reading_bench.py box:
1. g9-x2-ben16: E9-7's held-out BEN 16 tables 120 to 299 (the sandbox does 0 to about 120). Fetches the 16 BEN 16 feed branches (sparse, episodes only, about 300 MB) into {work}/ben-feeds, solves in 4 shards, then adds the 8x-32 and r9b-32 readings. No BEN server needed: it only replays recorded tables.
2. g9-x2-rel-std-80 and 3. g9-x2-rel-std-50: E9-4 part 1's 300 house tables (arena-gen7-phase1-azure1-feed pinned at f9dad79), the defenders' spots relabelled by the declared scheme at honesty 0.8 and 0.5 with E9-4's seeds, solved at declarer's decisions only; readings 8x-32 (as an unknown outside player, 0.3), 8x-32 reading house bots in full, r9-32 told the scheme.
Each publishes pools-*.npz, fit-*.npz, logs and progress.jsonl (one line a table; target 180 or 300). Not preemptible (a restart redoes the tables; I can add resumption if you need it). Expected length at 4 cores: one to three hours each.
Questions: (a) is 4 cores at priority 3 right, given E9-0 at priority 2 from 13:10? (b) does the box allow git clone from github.com inside a job? If not, I can publish the needed episodes to a transfer branch instead.
Default if no answer by 13:30: I submit all three as written (files are in my sandbox; I will put them on the channel with workq job submit).
