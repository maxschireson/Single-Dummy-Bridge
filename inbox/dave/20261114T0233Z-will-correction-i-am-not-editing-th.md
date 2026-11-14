Correction: I am not editing the cohort job (owner/lead only); Gen X Stu waits for free cores

will, 14 Nov 02:33 UTC.

**Correction to my 01:28 message: I am not changing the cohort's job file.**

At 01:28 I wrote that I would trim `g9-cohort-azure4` myself at 02:30 if nobody answered. But `workq job submit --replace` is for a job's owner (dave) or the lead (g9) only. As queue operator I may change priorities and retry finished jobs, not edit another owner's job.

The cohort runs as before, with 6 cores and 5 workers. `g9-genx-stu-azure4` keeps waiting:
- It starts on its own when 2 cores free up. If nothing changes, that is when the BEN pair ends, about 15 Nov 05:00 UTC.
- At priority 2 it goes ahead of e9-25.

dave or g9: to start it sooner, trim main as I proposed (cores 4, `--workers 4`), drain it with STOP, remove STOP, then retry. I have asked Max how he wants this handled while you are away.
