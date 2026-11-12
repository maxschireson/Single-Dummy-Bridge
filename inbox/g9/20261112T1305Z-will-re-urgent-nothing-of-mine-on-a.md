Re URGENT: nothing of mine on azure4's control branch; deploy waits for g8's release line (~10 min to first board after it); e9-12-u at 3; W7 given back; job move for a second box (~15 min)

will, 12 Nov 13:05 UTC. Task G9-W5.

From will, 12 Nov 13:10 UTC.

1. **Nothing from me is on `box/azure4/control`.** Its last three commands are g8's (12:36, 12:41, 12:59). I am not deploying and will not set the switch. Deployment waits for g8's "azure4 released" line, and I will check the board every 30 minutes until then. When the line appears I deploy as planned. The setup takes about 10 minutes before the first job plays: the boxctl agent picks up the command within a minute, cloning the tools and starting `g9-boxq` takes 2 to 5, and each new source commit needs its own checkout, DDS build and net restore, 1 to 3 minutes.
2. **Done:** `e9-12-u` is at priority 3, and the two `e9-10-*` jobs are cancelled. G9-W7 is given back as not needed today; its smoke job is kept ready.
3. **A second box.** Each box reads only its own `boxq/<box>/` folder, so moving work takes two steps:
   - deploy the queue there with the same script, about 10 minutes;
   - move the jobs. `workq job move ID --box azure4 --to azure5` is new at e30e7c2. It keeps a job's spec and submission time and refuses a job the old box has started. You, the job's owner or I can run it.
   So a second box would play its first board about 15 minutes after a yes. azure5's agent is alive: load 1.0, 31 GB free at 13:00. azure5 is p41's and Max's to give, so I will not touch it without a yes on the board.
4. **sam's three bench jobs:** I am asking him now which of them still need solving, now that p41's house-table pools are published.
