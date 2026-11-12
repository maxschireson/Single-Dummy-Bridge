# Queue metrics, team/gen9, 12 Nov 2026 09:47 UTC

From the channel's history: 50 tasks and experiments, the first created at 06:47 UTC. The first 90 minutes (06:47 to 08:17) are counted apart from the rest. Times in minutes. Made by `tools/queue_metrics.py` (G9-W4).

## Reading, as of 12 Nov 09:47 UTC (will)

These are three hours of one day. The rules come from the workplan's "What would change the numbers"; each tables section below says whether its signal fired.

- **Executors: no shortage visible.**
  - In the first 90 minutes, tasks waited a median of 11 to 47 minutes for a lease, depending on the owner, because all 30 were created at 06:47.
  - After that, nothing ready waited more than an hour. Four tasks are open and unleased now:
    - G9-A3 and G9-A6 are g9's own.
    - G9-B5 waits on G9-B3.
    - G9-W4 is this report, leased at 09:43.
  - E9-10, also g9's, shows as open but depends on E9-7.
  - So more executors would have had nothing ready to take.
- **Task size: the time box does not bind.**
  - All 29 leases that have ended used a quarter of their four hours or less, and none ran past its end.
  - Leads often lease when the work is nearly done; several leases started minutes before the submission. So lease length here measures the last step, not the work.
- **Review: the binding constraint is g9, and only since 08:00.**
  - In the 07:00 hour g9 gave 18 verdicts, in a median of 4 to 18 minutes depending on kind, which fits the "queue filled in about 20 minutes" observation.
  - g9 has given no verdict since then. It was last seen at 07:56; its last channel write was at 08:07.
  - The peer rule moved module reviews to the leads, and those flowed: 8 verdicts from bill, dave, sam and will.
  - What still goes only to g9: experiment verdicts (E9-7 and G9-X1, submitted 09:01), the D6 wiring checkpoint (09:13), and decisions. Its inbox holds 19 unread messages, the oldest from 07:55.
  - g9 also holds executor work: G9-A7/E9-0, leased until 11:41.
- **What this implies, provisionally.**
  - Four leads and no executors has been enough. The limit is one architect who both reviews and executes.
  - Options, in the workplan's terms:
    - g9 does not hold experiment work; E9-0 goes to a lead.
    - Experiment verdicts get a second reviewer: the evaluation lead the workplan already proposes ("whoever decides promotions should not be whoever submits candidates").
    - Decisions g9 has not answered within a set time go to Max through the queue issue.
  - Whether g9's silence is one long piece of work or an idle session is not known from the channel.
- **Limits of the measurement.**
  - Lease times do not show work time.
  - bill keeps no read state, so his reading time is unknown.
  - Read times come from read commits, and a "read all" counts every message before it as read then.
  - The box signals start when the azure4 queue runs, at 13:00.

The final numbers for Friday's review: rerun the command below on Friday morning, after a full day of history.

    python3 tools/queue_metrics.py --notes reports/queue-metrics-notes.md --out reports/queue-metrics.md --json reports/queue-metrics.json

## 1. Open and unleased

Time from a task being open (created, opened from proposed, given back, reopened) to its next lease.

| Owner | Waits, first 90 min | Waits, after | Open now, unleased |
| --- | --- | --- | --- |
| bill | 11: median 21, max 43 | — | G9-B5 180 |
| dave | 8: median 34, max 128 | — | — |
| g9 | 2: median 47, max 47 | — | G9-A3 180, G9-A6 180, E9-10 123 |
| pool | 2: median 85, max 85 | — | — |
| sam | 11: median 35, max 74 | — | — |
| will | 6: median 11, max 38 | 1: median 0, max 0 | G9-W4 180 |

Open more than an hour before a lease (the workplan's signal to add executors): G9-A3 (g9, 180, still open), G9-A6 (g9, 180, still open), G9-B5 (bill, 180, still open), G9-D6 (dave, 128), G9-D7 (dave, 70), G9-S7 (sam, 74), G9-W4 (will, 180, still open), G9-X1 (pool, 85), E9-10 (g9, 123, still open), E9-6 (sam, 74), E9-7 (pool, 85).

## 2. Leases

Length of each lease that has ended (start to submit, give-back or block), against its time box.

| Holder | Leases | Ended | Median length | Longest | Ran past its end | Given back | Renewals |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bill | 11 | 8 | 15 | 34 | 0 | 0 | 2 |
| dave | 8 | 7 | 17 | 26 | 0 | 0 | 0 |
| g9 | 2 | 0 | — | — | 0 | 0 | 0 |
| sam | 13 | 9 | 10 | 42 | 0 | 0 | 3 |
| will | 7 | 5 | 8 | 18 | 0 | 0 | 0 |

Of 29 ended leases, 29 used a quarter of their time box or less and 0 ran past it. Leases held now: G9-A7 g9 (126 of 240), G9-B3 bill (151 of 240), G9-D6 dave (52 of 240), G9-S4 sam (145 of 240), G9-S7 sam (99 of 240), G9-W5 will (80 of 240), G9-W7 will (117 of 240), E9-0 g9 (126 of 240), E9-11 bill (101 of 240), E9-12 bill (101 of 240), E9-4 sam (140 of 240), E9-6 sam (99 of 240).

## 3. Waiting for review

Time from submission to a verdict (resolved or sent back), by reviewer and by period.

| Reviewer | Kind | Reviews, first 90 min | Reviews, after | Sent back |
| --- | --- | --- | --- | ---: |
| bill | module | 1: median 2, max 2 | — | 0 |
| dave | module | 2: median 28, max 48 | — | 0 |
| g9 | design | 4: median 18, max 22 | — | 0 |
| g9 | experiment | 8: median 4, max 18 | — | 0 |
| g9 | module | 6: median 10, max 21 | — | 0 |
| sam | module | 3: median 75, max 76 | — | 0 |
| will | module | 1: median 34, max 34 | 1: median 11, max 11 | 0 |

Waiting now: G9-X1 (experiment, from sam, 46), E9-7 (experiment, from sam, 46).

Unreviewed for more than two hours (the workplan's signal that a lead or the architect is the bottleneck): none.

Verdicts by hour (UTC):

| Reviewer | 07:00 | 08:00 | 09:00 |
| --- | ---: | ---: | ---: |
| bill | 0 | 1 | 0 |
| dave | 1 | 1 | 0 |
| g9 | 18 | 0 | 0 |
| sam | 0 | 0 | 3 |
| will | 0 | 1 | 1 |

## 4. Messages

Messages received, how long they waited to be read (a read commit's time), and how many are unread now.

| Agent | Received | Read, wait (median, max) | Unread now | Oldest unread |
| --- | ---: | --- | ---: | --- |
| bill | 27 | keeps no read state | — | — |
| dave | 27 | 20: median 20, max 38 | 7 | 09:01 (46 min) |
| g9 | 48 | 29: median 6, max 39 | 19 | 07:55 (112 min) |
| sam | 23 | 23: median 7, max 40 | 0 |  |
| will | 17 | 17: median 13, max 32 | 0 |  |
| all (to everyone) | 10 | — | — | — |

Last seen (agents/*.json): bill 09:21, dave 09:13, g9 07:56, sam 09:40, will 09:24.

## 5. Boxes

No box serves the queue yet. Jobs waiting for one: 14 (56 cores asked, 16,000 boards), submitted from 08:35 UTC. The workplan's box signals (idle boxes while experiments wait; full boxes) start when the queue runs.

