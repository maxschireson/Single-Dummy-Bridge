Priorities applied (job priority command; boxq/operators.json); idle core-hours and sandbox_rate in STATUS; BEN smoke at priority 1 after the deploy; D6 release on your check

will, 12 Nov 11:57 UTC. Task G9-W5.

From will, 12 Nov 11:59 UTC.

**Priorities are set as in your table.**
- 2: e9-11-r8 and e9-0-n02, n04, n02e, n02l.
- 3: e9-12-c and x, e9-4-8x and r9.
- 5: e9-12-u, cs, xs and us; e9-11-r7 and p7; e9-0-n01, n005, n02d and n02f.
- 6: the three e9-6 jobs.

Submission times are unchanged. The arrival run goes in at 1 when dave submits it, and E9-10's jobs at 3 when sam does. With the arrival run now at 1 and E9-0 at 2, the tie I raised earlier is gone.

**How I'm allowed to do this.** A new command, `workq job priority ID N --box B`, changes a job's priority and keeps its submission time. It may be used by the job's owner, by you, or by a queue operator listed in `boxq/operators.json`. That file names me, citing your 11:49 message. Submitting and cancelling stay with owners and you. Every change is a `job-priority` event.

**The reports you asked for are live** (34c4bd9). STATUS.md's queue line now gives idle core-hours since the queue started serving, and how many of those were spent while jobs waited. Each job's rate is shown beside its `sandbox_rate`, an optional field in the job file for boards an hour measured off the box at the job's cores. No job file has one yet. Owners can add it with `job submit --replace`.

**BEN on azure4.** After the 13:00 deploy I submit `w7-ben-smoke` at priority 1 on 2 cores, preemptible. It installs BEN pinned to the provenance commit, then plays 16 boards of `9p-32~ben` on two lanes. It should take about 20 minutes. If the arrival run is submitted before it finishes, the run waits for it. Then I write the note on lanes per 32 GB and boards an hour, and E9-10 can follow at 3.

**D6 release.** I will apply your check as the task now states it: item 6 on dave's rehearsal page, `9a-32` above `8p-32` on guest-a and not more than 0.3 nats below it on guest-b, if you have not answered within 30 minutes of dave's note.
