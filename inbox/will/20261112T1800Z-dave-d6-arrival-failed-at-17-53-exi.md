d6-arrival failed at 17:53 (exit 1, 2 restarts): please send the log tail; do not restart

dave, 12 Nov 18:00 UTC. Task G9-D6.

From dave, 12 Nov 18:03 UTC. Task G9-D6.

**`d6-arrival` failed at 17:53 UTC, after 2,315 of 6,200 boards.** The queue's status shows `last_exit` 1 and 2 restarts. The last resume was at 17:50:44, and it ended at 17:53:48.

The records stop in epoch 3, at 17:45:51, in the floor pair `8p-32~guest-a`. Indices 524288 to 524568 are done, 281 of 300, and 524569 to 524587 never finished. Epochs 1 and 2 are complete (1,800 rows), with no duplicated rows. Because each restart failed within minutes, the cause is probably one board that raises an exception every time.

- **will:** please send me the tail of the job's log in `~/work/g9/runs/d6-arrival` (the traceback). Please do not restart the job: until the cause is fixed, it fails the same way.
- **What I am doing:** reproducing it here from the published control directory, by playing indices 524569 onward of `8p-32~guest-a` in epoch 3 with the run's code.

The control directory supports resuming, so a fixed source can continue from the first unfinished board. That needs a new job file, with g9's agreement since the source would change.
