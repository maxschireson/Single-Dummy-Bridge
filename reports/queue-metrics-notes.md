## Reading of the first day, 12 Nov 06:47 to 13 Nov 02:45 UTC (will)

This covers one day with five agents, and the tables below come from the channel's own history. The rules applied are the workplan's ("What would change the numbers"). This replaces the 09:47 reading.

- **Executors: no shortage all day.**
  - After the first 90 minutes, every task that waited more than an hour for a lease was waiting on something other than hands. G9-D6 was rewritten by g9 at 08:06. E9-10 was re-sharpened and reassigned at 11:50. G9-A6 is g9's review package. G9-B5 depends on G9-B3. E9-13 belongs to bill, who is absent. E9-16 is g9's own. G9-W7 was put off by g9 at 13:02.
  - More executors would have found nothing ready to take.
- **Task size: the time box did not bind.**
  - Of 40 ended leases, 30 used a quarter or less of their box, renewals included. One ran past it: G9-B3, by 27 minutes.
  - The long leases are experiments a lead keeps for the whole day, renewed five or six times (sam's E9-4 and E9-6, about 19 hours). Leads use a lease to mean "this is mine", not as a time box for one piece of work.
  - bill's E9-11 and E9-12 lapsed because his session stopped at 11:16. That is an absence, not a task-size problem.
- **Review: the constraint was the architect's availability, at two times.**
  - g9 wrote nothing to the channel from 08:07 to 11:23. It gave 18 verdicts in the 07:00 hour and none from 08:00 to 11:00. E9-7 and G9-X1 waited 168 minutes for a verdict.
  - In the evening, E9-17 waited 150 minutes and E9-10 67. E9-10 then got a stand-in verdict.
  - g9 received 107 messages; the median wait before reading was 39 minutes, the longest 318.
  - Module reviews by peer lead worked throughout: 10 verdicts from bill, dave, sam and will, with a median of about 40 minutes.
- **What changed during the day, and whether it was used.**
  - g9's 11:53 rules:
    - another lead may give an experiment's verdict 60 minutes after its submission (used once: E9-10, 22:14);
    - a blocking request unanswered for 30 minutes goes to will when it is a release with a written check (used once: D6's resume at 18:55). dave's first D6 release, at 13:21, was on a check g9 had given him directly.
  - workq now applies the stand-in rule itself. It also gained `job priority`, `job move` and `job retry` for the box queue.
- **An absent lead.** bill has been silent since 11:16. His review of G9-X2 went to will at g9's request, but workq still named bill as reviewer until sam set `reviewer=will` by hand. His leases lapsed with nobody told. Absence can be seen in the channel (`last_seen`, lapsed leases); nothing acts on it yet.
- **The box.** azure4 served Gen 9's queue from 15:03.
  - Through 02:39 it had **0.0 idle core-hours**, about 93 core-hours used, and 9,400 boards finished in five jobs.
  - d6-arrival failed once, at 17:53, on an auction no Gen 9 code had seen (another system's 3NT opening). It resumed in its own folder at 18:59 with `job retry`, after a two-line fix and a written check, and finished at 00:54.
  - The box's ETA misled twice, because it uses one rate for every board while boards in that run cost 12.5 to 50 CPU-seconds by pair.
  - Max's 00:04 pause for 8X cancelled 23 jobs at 00:09 to 00:10, and his 01:13 reversal restored 7 by `job retry` at 01:15. It cost no box time: no cancelled job had started, and the kept jobs ran on.
- **What the day implies.**
  - Four leads with no executors were enough for the work. The constraint is one architect who reviews, decides and also executes, and whose session can stop for hours. Rules that let others act on a written check after a set time, enforced by the tools, took most of the cost of that out.
  - Suggestions, in the workplan's terms:
    - an evaluation lead for experiment verdicts, since the 60-minute stand-in is a stopgap;
    - when a peer reviewer is silent for more than two hours, its reviews move to g9 or to another lead by rule, not by hand;
    - g9 does not hold experiment leases (G9-A7 and E9-0 were g9's for about 19 hours);
    - job files carry a per-pair `sandbox_rate`, so the queue's ETAs can be trusted.
- **Limits of the measurement.**
  - Lease length is not work time.
  - bill keeps no read state.
  - Read times come from read commits, and a "read all" marks everything before it.
  - One day is one sample: the first 90 minutes were a burst, and the evening had fewer agents awake.

To rerun: `python3 tools/queue_metrics.py --notes reports/queue-metrics-notes.md --out reports/queue-metrics.md --json reports/queue-metrics.json`
