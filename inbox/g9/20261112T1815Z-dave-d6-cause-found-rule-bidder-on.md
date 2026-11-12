D6: cause found (rule bidder on another system's 3NT); fixed at 698679e; resume or restart is your call (default: resume at 18:52)

dave, 12 Nov 18:15 UTC. Task G9-D6.

From dave, 12 Nov 18:22 UTC. Task G9-D6. A decision for you; my recommended default is at the end.

**The cause.** In epoch 3, on board 524569 of `8p-32~guest-a`, the house net opened 3NT and the next two hands passed. guest-a's rule bidder explains the opponents' calls by its own tables, and in `response_table` it reached the one-level-minor branch with the strain notrump (`st.shown[seat].len[4]`, IndexError). Nothing in our tables opens 3NT, so it had not happened before. I reproduced it here from the published control directory, and with three calls in isolation (3NT, pass, pass).

**The fix** is on `feature/gen9-arena-arrival` at 698679e:
1. **Rule bidder** (2 lines): `response_table` returns no table for an opening it never makes at that point, and `explain` falls back to `general_meaning`. Only C, D and notrump reach that branch, and notrump always raised there, so only auctions that raised take the new path. A regression test fails on the old code and passes on the new.
2. **Runner:** a board that raises is recorded with its error and no score or experience, and the page lists such boards. One bad board can no longer stop the run.
3. **Checked:** board 524569 now plays (native 0 IMPs), and so do the next seven floor deals. The affected tests pass (rule bidder, arena9, pipeline).

g8's 5b007c3 and r2/r3 (will's pointer) change 521 lines of the rule bidder. They would change guest-a's bidding on many auctions, so I have not used them.

**Resume or restart.** Play is seeded and the fix changes only auctions that raised. A fresh run at 698679e would therefore produce the same 2,315 boards card for card, and the same snapshots, ratings and schedules, as the run we have. So resuming in the same folder is equivalent to a fresh run at 698679e, and saves about 3 hours of the box. The page would say:
- epochs 1 to 3 were opened under 8cb0348, and epoch 3's last 685 boards and epochs 4 and 5 were played at 698679e;
- the change and why the played boards stand.

Restarting from scratch is the strict reading of "no code change after the run starts", at the cost of those 3 hours.

**Times:**
- Resume: about 3,885 boards and 6 hours, ending about 00:30 UTC if it starts by 18:45.
- Restart: about 8.5 hours, ending about 03:15 UTC.

Either way it ends before the freeze. E9-0 and E9-12 wait behind it.

**Default** (your 11:53 rule): if you have not answered by 18:52, I ask will to release the resume on the written check above, then run `job submit --replace` with 698679e and `job retry d6-arrival`. If you prefer a restart, say so, and I will submit a new job id with a fresh output folder.
