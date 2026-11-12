D6: four choices answered; release held about an hour for a fix in the shell's mixture, then one rehearsal

g9, 12 Nov 11:32 UTC.

D6: your four choices answered; release is held for one fix in the shell's mixture (mine), about an hour; then one rehearsal and will may release

g9, 12 Nov 12:08 UTC. Task G9-D6.

I was away from 08:10 to 11:20 UTC, which is why you waited. So that it does not happen again: for D6, if I have not answered a release request within 30 minutes, will may release it once the rehearsal page shows the checks in point 6.

1. **Occasions.** Bids: `auction` (identical evidence counts once). Cards: `play`. Known flaw, accepted for now: two plays of a deal that agree for the first tricks and then part count the shared tricks twice; a per-decision unit is a later change.
2. **Epochs.** Five epochs: 600, 1,200, 1,200, 1,600, 1,600 (6,200 boards). Floors: `guest-a` 300 boards a pair from epoch 2; `guest-b` 300 a pair in epochs 4 and 5 (not 200).
3. **Shares of the scheduled boards, for this run only** (`rules-arrival.json`; rules v0 stays as accepted): nothing trains on this run, so self-play at 0.10, promotion at 0.30, the rest to admission and panel pairs by the gain rule. Say so on the page.
4. **Open the test by plan.** Yes: `activate 9a-32` and `open-test 9a-32` against `8p-32` before epoch 2. The page shows its state; it is not expected to decide.
5. **Predictions I am changing in the task before the run** (logged there): item 2, `guest-a`'s learned honesty 0.65 to 0.8 (sam: the reader measures the effective value); item 3 is split by epoch, because in epoch 4 the bot knows `guest-b` only by its arrival prior.
6. **Why the release is held.** I checked the wiring against the packages and found an error of mine in the shell, not in your pipeline. In `read_calls` the rows of a mixture are on different scales: a replay row is a true log-likelihood of the calls (several nats below zero even for a hand that fits), a card row and a scorer row are near zero for a hand that fits, and `flat` is zero. So within a board `flat` and `card` outweigh a held net whatever the experience says, and against `guest-b` the bot would read a house auction mostly as flat. The fix: rows of one kind are mixed exactly as now; each kind is then taken relative to its own average over the layouts, so a mixture with weight p on the right profile reads at most -log p nats worse than knowing the profile. Replay will apply only where every candidate is a held net. `arrive` also gets bill's finding that a house player is about 0.15 from its own best card (distances count from 0.15), so a guest who bids a held system is not read by its card alone for a whole epoch.
   I will push to `feature/gen9` and tell you the commit. Then: merge, run the full-path rehearsal again, and add to its page, for `guest-b` after its first epoch, the mean over the floor boards of the auction's contribution to the true layout's log weight for `9a-32` and for `8p-32`. **Release check:** `9a-32`'s is not below `8p-32`'s by more than 0.3 nats on `guest-b`, and is above it on `guest-a`. If that holds, submit; if not, send me the page.
7. **Box order.** E9-0 and E9-11 start at 13:00. D6 at priority 1 goes in as soon as it is released and takes the whole box.
