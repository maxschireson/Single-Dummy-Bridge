D6: will's review done (32dcf6f); your call on card occasions; a full-path rehearsal is running

dave, 12 Nov 10:07 UTC. Task G9-D6.

From dave, 12 Nov 10:10 UTC. Task G9-D6.

**Box source** is now `feature/gen9-arena-arrival` at `32dcf6f`. It merges bill's `feature/gen9-bidding-cards` through `ad8c5ca` (d4515bd and 514e046, the fresh-checkout restores; the rb cards with responses; the sharpened profile statistic) and sam's `feature/gen9-signals-v2` through `96716fb` (7ef3cb8, emission counts in card_delta; carding fields v1.1). Full suite at 4354b64: 432 passed, 0 failed; one test added since.

**Will's review of D7, done:**
1. **Occasions: your call before the job starts.** The unit is now a rules-file setting, `experience.occasions`, which the runner reads and every epoch manifest pins through the rules sha. Default, and what `rules-arrival.json` says now: your unit (family, seats, auction) for both bid and card statistics. So a floor deal with the same auction against `9a-32` and against `8p-32` counts once. For bids that is right: will found all 24 such bid deltas in the rehearsal identical. For cards there are two other settings:
   - `opponent`: both plays count, identical ones included (8 of the 20 in the rehearsal were identical).
   - `play`: the occasion also holds every card played at the table, so an identical play counts once and a different play twice.
   I would use `play` for cards. Under `auction`, all 20 second plays are dropped, including the 12 made in different tricks against different defenders. Under `play`, only the identical ones go. Changing it is one line in `rules-arrival.json`.
2. **Shared tables.** A table that two regimes share is now credited to every declared bidder those regimes seated there, as will proposed. His reproduction is a test.
3. **The page.** It now gives distinct boards beside the deltas (board-sides).
4. **The job file.** Its source is now 32dcf6f.

**guest-b's bidding net (bill's 09:03 note).** Its package named the Gen 6 bidder's hash (5b7ea255, copied from the base bot), but it bids the Gen 5 net (9ee52f3b). I fixed the package. The runner now refuses a package whose override file is not the net it names, and the pair manifests record the override's hash. guest-b's identity changes; it is not registered anywhere yet.

**Item 2's prediction (sam, 09:20).** Sam suggests registering guest-a's pooled honesty at 0.65 to 0.8 after epoch 2 (spots 0.7 to 0.8, the lead 0.5 to 0.7), not 0.8. His reason is that the reader measures effective honesty. The task text is yours to change.

**A second rehearsal is running.** The first one had no guest-b and no retirement. This one runs the box run's events file on 16-board epochs (floors 4 and 3), in a fresh worktree of 4354b64 where only bill's on-first-use code restores the nets. I will send the result when it finishes, probably within the hour.

**Still open: floor share.** From epoch 4, floors take 1,000 of 1,200 boards (guest-a 600, guest-b 400), which leaves the scheduler 200. The choices are to keep that, or use 1,600-board epochs from epoch 4: 6,200 boards in all, about 7 hours at the task's rate of 5,400 boards in 5 to 6 hours.

**Release.** I submit the job when you release it. The box opens at 13:00; the latest start is 02:00 tomorrow.
