# Queue metrics, team/gen9, 13 Nov 2026 02:44 UTC

From the channel's history: 57 tasks and experiments, the first created at 06:47 UTC. The first 90 minutes (06:47 to 08:17) are counted apart from the rest. Times in minutes. Made by `tools/queue_metrics.py` (G9-W4).

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

## 1. Open and unleased

Time from a task being open (created, opened from proposed, given back, reopened) to its next lease.

| Owner | Waits, first 90 min | Waits, after | Open now, unleased |
| --- | --- | --- | --- |
| bill | 11: median 21, max 43 | — | G9-B5 1197, E9-13 893 |
| dave | 8: median 34, max 128 | 1: median 34, max 34 | — |
| g9 | 2: median 47, max 47 | — | G9-A6 1197, E9-16 707 |
| pool | 2: median 85, max 85 | — | — |
| sam | 12: median 38, max 249 | 3: median 9, max 46 | — |
| will | 7: median 16, max 176 | 2: median 0, max 0 | G9-W7 819 |

Open more than an hour before a lease (the workplan's signal to add executors): G9-A6 (g9, 1197, still open), G9-B5 (bill, 1197, still open), G9-D6 (dave, 128), G9-D7 (dave, 70), G9-S7 (sam, 74), G9-W4 (will, 176), G9-W7 (will, 819, still open), G9-X1 (pool, 85), E9-10 (sam, 249), E9-13 (bill, 893, still open), E9-16 (g9, 707, still open), E9-6 (sam, 74), E9-7 (pool, 85).

## 2. Leases

Length of each lease that has ended (start to submit, give-back or block), against its time box (renewals included).

| Holder | Leases | Ended | Median length | Longest | Ran past its end | Given back | Renewals |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bill | 11 | 9 | 19 | 267 | 3 | 0 | 4 |
| dave | 9 | 9 | 19 | 962 | 0 | 0 | 8 |
| g9 | 2 | 2 | 1135 | 1135 | 0 | 0 | 6 |
| sam | 17 | 13 | 40 | 555 | 0 | 0 | 27 |
| will | 9 | 7 | 8 | 315 | 0 | 1 | 11 |

Of 40 ended leases, 30 used a quarter of their time box or less and 1 ran past it. Leases held now: G9-S4 sam (1162 min, 6 renewals), G9-S7 sam (1116 min, 5 renewals), G9-W4 will (1021 min, 5 renewals), G9-W5 will (1097 min, 5 renewals), E9-11 bill (1118 min, 2 renewals, past its end by 688), E9-12 bill (1118 min, 2 renewals, past its end by 688), E9-4 sam (1157 min, 6 renewals), E9-6 sam (1116 min, 5 renewals).

Leases that ran past their end (the workplan's signal that tasks are too big): G9-B3 bill by 27, E9-11 bill by 688, E9-12 bill by 688.

## 3. Waiting for review

Time from submission to a verdict (resolved or sent back), by reviewer and by period.

| Reviewer | Kind | Reviews, first 90 min | Reviews, after | Sent back |
| --- | --- | --- | --- | ---: |
| bill | module | 1: median 2, max 2 | — | 0 |
| dave | module | 2: median 28, max 48 | 1: median 6, max 6 | 0 |
| g9 | design | 4: median 18, max 22 | — | 0 |
| g9 | experiment | 8: median 4, max 18 | 5: median 150, max 168 | 0 |
| g9 | module | 6: median 10, max 21 | — | 0 |
| g9 | ops | — | 1: median 99, max 99 | 0 |
| sam | module | 3: median 75, max 76 | — | 0 |
| will | experiment | — | 1: median 67, max 67 | 0 |
| will | module | 1: median 34, max 34 | 2: median 33, max 55 | 0 |

Waiting now: nothing.

Unreviewed for more than two hours (the workplan's signal that a lead or the architect is the bottleneck): G9-X1 168, E9-17 150, E9-7 168.

Verdicts by hour (UTC):

| Reviewer | 12 07:00 | 12 08:00 | 12 09:00 | 12 11:00 | 12 16:00 | 12 17:00 | 12 18:00 | 12 20:00 | 12 22:00 | 13 02:00 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bill | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| dave | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| g9 | 18 | 0 | 0 | 2 | 1 | 1 | 0 | 0 | 0 | 2 |
| sam | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| will | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 0 |

## 4. Messages

Messages received, how long they waited to be read (a read commit's time), and how many are unread now.

| Agent | Received | Read, wait (median, max) | Unread now | Oldest unread |
| --- | ---: | --- | ---: | --- |
| bill | 39 | keeps no read state | — | — |
| dave | 50 | 46: median 21, max 60 | 4 | 01:07 (97 min) |
| g9 | 107 | 101: median 39, max 318 | 6 | 00:06 (158 min) |
| sam | 47 | 47: median 6, max 559 | 0 |  |
| will | 36 | 36: median 14, max 37 | 0 |  |
| all (to everyone) | 17 | — | — | — |

Last seen (agents/*.json): bill 11:16, dave 00:57, g9 02:35, sam 00:14, will 01:55.

## 5. Boxes

- azure4: serving since 15:03 UTC, 8 cores; 2 running, 5 waiting, 5 done (9,400 boards), 0 failed now; idle 0.0 core-hours, 0.0 of them while jobs waited; updated 02:39 UTC.

