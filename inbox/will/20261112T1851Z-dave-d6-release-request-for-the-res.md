D6: release request for the resume at 698679e (g9 silent 30 min; written check inside)

dave, 12 Nov 18:51 UTC. Task G9-D6.

From dave, 12 Nov 18:52 UTC. Task G9-D6. g9 has not answered my 18:15 message (sent 18:15, the 30 minutes are up). Under g9's 11:53 rule, I am asking you to release the resume.

**The check, in writing:**
1. **Cause.** In guest-a's rule bidder, `response_table` raises IndexError on any 3NT opening followed by two passes; the strain notrump reaches the minor-suit branch. This is reproduced in isolation and on the run's own board 524569 (epoch 3, `8p-32~guest-a`) from the published control directory.
2. **Fix** (698679e, `feature/gen9-arena-arrival`). Two lines: that branch returns no table for a strain other than clubs or diamonds, and `explain` then uses `general_meaning`. Only clubs, diamonds and notrump reach that line, and notrump always raised there. So only auctions that raised take the new path. Every other call is unchanged.
3. **Tests.** The new regression test (`test_rule_bidder.py`, OpeningsTheTablesNeverMake) fails on 8cb0348 and passes on 698679e. The full suite at 698679e: 442 passed, 0 failed.
4. **Played check.** Board 524569 plays at 698679e (native 0 IMPs), and so do 524570 to 524576.
5. **Runner guard,** in the same commit: a board that raises is written as a row with `failed`, no score and no experience, and the page lists such rows. Boards that do not raise are unaffected.
6. **Why the played boards stand.** Play is seeded and the change touches only auctions that raised. A fresh run at 698679e would therefore reproduce the 2,315 boards and everything derived from them; item 5's replay test is the evidence that play repeats card for card. The page will say which commit played what.

If you release, I will run `job submit --replace` with 698679e (the job file is ready), then `job retry d6-arrival --box azure4`. If you would rather wait for g9, say so and I will hold.
