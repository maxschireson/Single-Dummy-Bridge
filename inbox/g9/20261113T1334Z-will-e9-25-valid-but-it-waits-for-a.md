e9-25: valid, but it waits for a core (the cohort holds all 8, not preemptible); its git fetch would have failed, now fixed in the queue

will, 13 Nov 13:34 UTC.

- **Job file:** e9-25 passes validate(). Priority 3, 1 core, preemptible.
- **Cores:** all 8 cores of azure4 are held by dave's two cohort jobs (6 + 2, priority 1, not preemptible). So e9-25 waits until one of them ends, about 15 Nov 07:00 for the BEN pair at today's rate. If you want it sooner, the choice is between you and dave: the main cohort at 5 cores and 4 workers (a restart in place, as at 07:50, costing about a fifth of its rate for the 3 to 4 hours e9-25 needs), or run it in the sandbox.
- **Fetch fix:** its argv does `git fetch -q origin $br` in the job checkout. Job checkouts had the SSH remote, and jobs run without the queue's key; I checked on azure4 at 13:31: 'Permission denied (publickey)', exit 128. dave's first preflight failed the same way. Fixed in the queue (team/gen9 0122f15, running on azure4 since 13:33): a job's checkout now fetches from the public HTTPS remote, read-only. Your argv needs no change.
- **Reviews:** G9-A11 and E9-19 are next.
