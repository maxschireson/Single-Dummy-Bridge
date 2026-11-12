D6: release check met on 8cb0348; the arrival run is submitted (priority 1, azure4)

dave, 12 Nov 13:21 UTC. Task G9-D6.

From dave, 12 Nov 13:22 UTC. Task G9-D6.

**The release check is met on your fix. The arrival run is submitted:** `d6-arrival` on azure4, priority 1, 8 cores, source `feature/gen9-arena-arrival` at 8cb0348, which merges feature/gen9 cc51fee. The full suite passes there (440, 0 failed).

The check used the same deals as before (seed 9157) and the epoch-5 snapshot of rehearsal 2. 9a-32 minus 8p-32, paired by deal:

| Guest | Model | Difference (SE), deals | Threshold | Before the fix |
| --- | --- | --- | --- | --- |
| guest-a | arrival | +5.06 (0.91), 60 | > +3 | +4.68 (0.78) |
| guest-a | snapshot | +5.11 (0.93), 60 | > +3 | +4.72 (0.79) |
| guest-b | arrival | -0.152 (0.012), 100 | > -0.45 | -0.49 (0.10) |
| guest-b | snapshot | -0.004 (0.0004), 100 | > -0.15 | -0.45 (0.12) |

The arrival figure for guest-b sits inside your -log 0.70 = 0.36 bound. The rows and summary are in `check/release-8cb0348/` on `transfer/gen9-arrival-rehearsal-2-20261112` (39f63e5). The rehearsal's own page there predates the fix: its item 6 for guest-b (-0.71 and -1.13) is with the card on the nets.

**The run's results** will publish every 10 minutes to `transfer/gen9-d6-arrival-azure4-<day>`: `results.jsonl`, `report.md`, `replay.json` and `control/*`. The page is written once all five epochs are done. On your estimate it ends about 21:30 UTC if it starts at 15:00. I will watch it from the start and send you the page.
