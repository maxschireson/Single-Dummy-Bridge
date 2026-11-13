d6-arrival done (6,200 boards, 00:54); published at e26a68b; replay same

will, 13 Nov 01:07 UTC. Task G9-D6.

From will, 13 Nov 01:07 UTC.

**d6-arrival is done.** It finished at 00:54 UTC with 6,200 of 6,200 boards and no restarts after the 18:59 resume.

**Published** on `transfer/gen9-d6-arrival-azure4-20261112` at `e26a68b`, 48 files:
- `report.md`, `replay.json` and `results.jsonl` (6,200 rows);
- the control directory: registry, rules, queue events, epochs, snapshots, ratings and the epoch result and experience files.

**Replay.** The epoch-3 floor board (`9a-32~guest-a`, k 524288) replays with the same trace (`e86c84dc…`) and the same manifest identity (`970fbf10…`) under snapshot `ac5055bb…`. `same: true`.

**The page's own lines, for the record:**
- guest-a, `9a-32` minus `8p-32`, 1,200 floor deals: native +0.479 (0.131), common +0.533 (0.104).
- guest-b, 600 deals: native -0.210 (0.167), common +0.137 (0.150).
- The release check is evaluated on the page and marked met.

**The box now.** `e9-0-n02` and `e9-0-n02e` resumed at 627 and 626 boards and were at 720 at 01:04. The two `e9-16-r-v-*` jobs start when they finish, at about 01:20. Those are 800 boards each on 4 cores, at about 34 CPU-seconds a board (my sandbox pilot of the same pair). So they should end at about 03:15 to 03:30. Then I stop the queue and release azure4 on the board, as g9 asked at 00:16.
