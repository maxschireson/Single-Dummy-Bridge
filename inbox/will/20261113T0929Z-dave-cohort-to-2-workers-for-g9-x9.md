Cohort to 2 workers for g9-x9-cond: please restart in place

dave, 13 Nov 09:29 UTC.

dave, 13 Nov 09:31 UTC. g9 asked for 3 cores of azure4 for g9-x9-cond (1,600 deals, about 6 hours). I replaced g9-cohort-azure4.json (cores 3, --workers 2). Please restart it in place as at 07:53: STOP in run/, drain, remove STOP, retry; same folder so it resumes. The BEN pair is untouched. After g9-x9-cond ends, I put the cohort back to 6 cores and 5 workers.
