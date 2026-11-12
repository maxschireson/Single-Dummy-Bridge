Re G9-X2 box time: no box before g8's release (15:00 at the latest); which bench jobs remain now p41's house pools are published; make them preemptible or submit after D6 starts; https fetch checked at deploy

will, 12 Nov 13:06 UTC. Task G9-X2.

From will, 12 Nov 13:06 UTC.

azure4 is g8's until its "azure4 released" line, 15:00 UTC at the latest. Nothing runs there before that, so there is no hurry to submit by 13:30.

1. **Which jobs remain.** g9, 13:02: p41's stored layouts and solves for the 530 house tables are published (`transfer/gen8-p41-reading-pools-20261112`), so only BEN's tables need solving. Does that make `g9-x2-rel-std-80` and `-50` unnecessary? Or does relabelling the defenders' spots change the plays enough that those decisions need new solves? Submit only the ones that still need the box.
2. **Priority 3 and 4 cores is right**, beside E9-12 in g9's 13:02 table. One thing first: make them preemptible, with resumption from `progress.jsonl`. A non-preemptible job holds its cores once it starts. If a bench job starts before dave submits the arrival run (priority 1, all 8 cores, also non-preemptible), the arrival run waits until the bench job ends, one to three hours. If resumption is too much work, submit them after the arrival run has started instead.
3. **git from github.com inside a job.** The repository is public, so an https fetch needs no credentials, but I have not seen one succeed from azure4. The deploy now prints "jobs can fetch the public repository over https" or "CANNOT", and I will pass that on. Nothing in the job's environment can push. To avoid depending on it, have the job read the feed branches from a transfer branch's files, or fetch them into `{work}/ben-feeds` once and keep them there.
