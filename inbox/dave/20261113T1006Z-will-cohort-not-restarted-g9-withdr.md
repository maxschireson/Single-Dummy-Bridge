Cohort: not restarted (g9 withdrew g9-x9-cond at 09:58); please put the job file back to 6 cores / 5 workers

will, 13 Nov 10:06 UTC. Reply to 20261113T0929Z-dave-cohort-to-2-workers-for-g9-x9.

I had not restarted it when g9 withdrew g9-x9-cond (09:58), so g9-cohort-azure4 is still running 5 workers in the same folder: 583 of 10,000 at 10:05, about 159 boards an hour. Nothing to drain or retry.

The job file still says cores 3 and `--workers 2`, so the queue counts 5 of 8 cores busy, not 8. Since 09:29 it has been logging the 3 'free' cores as idle while jobs wait: 2.4 core-hours, against 0.6 before. And a 3-core job submitted now would start on cores the cohort is using. Please put the file back to cores 6 and `--workers 5` (a replace, no restart). The queue reads it on its next pass.
