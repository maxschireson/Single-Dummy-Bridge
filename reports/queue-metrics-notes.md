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
