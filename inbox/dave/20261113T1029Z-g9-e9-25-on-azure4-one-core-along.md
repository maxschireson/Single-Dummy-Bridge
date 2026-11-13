E9-25 on azure4: one core alongside the cohort, or wait?

g9, 13 Nov 10:29 UTC.

g9, 13 Nov 10:31 UTC. E9-25 (registered from E9-24) needs BEN's bidding net, which only azure4 has (will, 10:28). It is a 1-core job of about 2 to 3 hours (at most 3,000 positions; scripts on feature/gen9 at 9bb9aed, dry run checked in the sandbox). azure4's eight cores are in real use (cohort 5 workers, BEN pair 2), so a ninth process would slow the cohort by about an eighth while it runs, about 40 boards of the 3,000 expected by the review. Your call: run it now alongside (I submit at priority 3, 1 core), or I wait until a core frees. The queue still counts 3 idle cores because the cohort's file says 3; I will not submit until you answer, so the stale count does not decide it.
