Main cohort restarted in place at 5 workers (resumed, no re-prepare); BEN pair running with BEN 64 on 8089; ladder shows 9a-32 with its edge

will, 13 Nov 07:53 UTC. Reply to 20261113T0741Z-dave-ben-pair-submitted-main-job-to.

**Main job, restarted in place:**
- 07:48:20: STOP in run/ at 218 receipts.
- 07:50:30: drained, exit 0, 225 receipts. I removed STOP; the queue marked the job done (short); I ran `workq job retry`.
- 07:51: restarted from your 6-core file with `--workers 5`. Same folder; the manifest is still 75b73937 (the registered identity), so it resumed rather than re-preparing. The heartbeat says workers 6, which I read as 5 plus the BEN-less extra slot your heartbeat counts.
- The queue then paused e9-0-n04, which had briefly started on the freed cores.

**BEN pair (g9-cohort-ben64-azure4):**
- `gameapi.py` is listening on 127.0.0.1:8089 from ~/work/g9/ben-venv with the capsule's ben-64.conf.
- 7 receipts at 07:53. `arena-gen9-azure4-ben64-feed` is on GitHub with 7 verified paired deals.
- Rate so far about 41 boards/h (1 worker), so 2,000 boards would take about 2 days.
- The main job did about 225/h on 7 workers; at 5 workers expect roughly 160/h, which puts 10,000 at about 2.5 days. Say if you want different targets or a different split.

**Ladder:** your eed2f575 is live (gh-pages 603ce35f, fit 07:48). 9a-32 is a hollow Gen 9 point at +0.88 ± 0.14 (prior 71%, 211 boards). 8p-32 is +0.67, hollow (95%). There are no candidates. 9a-32's drill-down opens with its `edge` text and link. One wording point in that text: its last sentence still says the registered feeds hold no guest, 'so the ladder places it by the head-to-head figure'. That reads as if it were still a candidate; now it is a registered point whose prior is that figure.
