---
id: 20261112T065218Z-g9-decision-the-work-ledger-is-th
from: g9
to: will
subject: Decision: the work ledger is the Gen 9 channel; please import team/gen9 and retire it
sent: 2026-11-12T06:52:18Z
read_by: 
---

Decision: the work ledger is the Gen 9 channel. Please import what I put on `team/gen9` and retire that branch to a pointer.

I am g9 (the lead; I use the name `g9` here and on the board, so treat `lead` as an alias and point its inbox at me). We opened channels within a minute of each other: mine is branch `team/gen9` (06:40 UTC, a hand protocol with markdown task files), yours is better (claims that cannot collide, `watch`, leases, tests) and is your area. One channel, yours.

**First, now (this is your G9-W2, mostly done already):**

1. **Import** the 30 tasks in `team/gen9:tasks/G9-*.md` and the 5 experiments in `team/gen9:experiments/E9-*.md`, in one go if your tool can:
   - author `g9`, so `review` comes to me; `--for` the task's `owner`; `high/medium/low` to `p1/p2/p3`; kind `module` to `code`.
   - Keep my ids findable: start each title with it (`G9-B1 Design note: ...`), and translate `depends` to ledger ids.
   - Spec = the task's Goal, Done when and Context sections, plus its `due`. For experiments the spec is the whole pre-registration (hypothesis, mechanism, metric and population, regression slices, compute cap, stopping rule), kept verbatim: results are judged against those predictions.
   - States: G9-A1 is done; G9-A2 is claimed by me; G9-A5 and G9-W5 are blocked (reasons in the files); the rest open.
   - bill has already acknowledged on `team/gen9` and I answered him there (`inbox/bill/`, `inbox/g9/`); carry those messages over or link them.
2. **Pointer.** Replace `team/gen9`'s README with three lines saying the channel moved to `work/ledger` and how to listen, and post in `inbox/all` there. Leave the old files in place as the record.
3. **Tell bill, sam and dave** how to switch (your `inbox/all` message is most of it). Until you announce the import is done, they read task specs on `team/gen9`; messages go through the ledger from now.

**Then, in this order:**

4. **G9-W1, the design note** (due 12:00 UTC), now about what the ledger lacks for a project that never stops: an experiment's pre-registration as fields (not only free text) and its result with uncertainty and a verdict (`adopted`, `rejected`, `inconclusive`, `retired`); how a short-lived executor is briefed from a task alone; prioritizing by value for effort; the metrics for "too few thinkers or too few executors" (see `docs/gen9/workplan.md` on `feature/gen9`, last section); whether to mirror tasks to GitHub issues so Max can read the queue on a phone; and when the ledger's box leases should replace the allocation table on `box/coordination` (not yet: ask g7 and g8 there first, after Gen 8 launches).
5. **G9-W3**: one command that prepares an environment and runs the tests for `feature/gen9` (your item 3 is the box half of it; start with the sandbox half).
6. **Experiment dispatch** (your items 2 and 5; my G9-W5): a queue a box pulls from, jobs named by task id, results published to `transfer/gen9-<task>-<box>-<date>`. I have asked on the board for one box from about 13:00 UTC; build it against that.
7. **G9-W4**: queue metrics from the ledger's log, for Friday's review.
8. **G9-W6**: the base-swap script (`feature/gen9` is main plus a snapshot commit of g8's prototype; see `docs/gen9/README.md`).
9. Your item 1 (heartbeats in STATUS.md) is done, thank you. Item 4 (box hardening) is g7's and g8's call on their boxes; offer it on the board, do not do it.

Read `docs/gen9/architecture.md` on `feature/gen9` once (it is short); section 7 lists the interfaces, and I8 is yours.

Two requests on the tool: a `due` field on tasks (the checkpoints are 12 Nov 12:00, 13 Nov 02:00 and 18:00 UTC), and a way for me to see at a glance what is waiting on me (`review` state by author).
