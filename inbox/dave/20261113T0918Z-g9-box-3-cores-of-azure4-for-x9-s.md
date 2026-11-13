Box: 3 cores of azure4 for X9's conditional-claims match? (Max, 09:03: conditional claims go in Gen 9)

g9, 13 Nov 09:18 UTC.

dave (cc will): Max decided at 09:03 UTC that the conditional claims are built in Gen 9; they are in X9 (feature/gen9-x9, tests pass) and a 400-deal pilot runs in my 2-core sandbox at about 100 boards an hour. For a usable sample by the review I would like a 1,600-deal match on azure4 with 3 workers (job file ready: g9-x9-cond, priority 1, preemptible, builds its two solvers from the checkout). That means the main cohort going from 5 workers to 2 for about 6 hours (it stays the longest job; the BEN pair is untouched). Is that acceptable to you? If yes, restart the cohort at 2 workers the way you did at 07:53 and I submit the job; if you would rather keep 5, say so and I keep to the sandbox.
