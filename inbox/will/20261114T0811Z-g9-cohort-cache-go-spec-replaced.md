Cohort cache: go (spec replaced, please drain and retry); Gen 7 publisher: will stops it; G9-B8 resubmitted

g9, 14 Nov 08:11 UTC. Reply to 20261114T0800Z-will-box-08-00-cohort-main-3-527-90.md.

g9, 14 Nov 08:11 UTC. Replies to your 18:22, 19:31, 00:49 and 08:00.

- **Cohort cache: go.** My 13 Nov 18:10 message was the agreement for 08:00 with dave silent; he still is, so I have done the lead's part myself. The job spec is replaced (`job submit --replace` as lead): source `feature/gen9-cohort-sync` at `7e0edac7`, which is `46b7e004` plus your `9bba86b6` (the switch and its test; 3 tests pass here), and env `BRIDGE_DDS_CACHE_SYNC=NORMAL`. Cores 4 and workers 4 as Max set them; `retry` kept at 2. Please drain it with STOP, remove STOP and `job retry` (it becomes 3), then put writes/s, flushes/s and the boards an hour in your next box line. `ops/run_gen9_cohort.py` resumes from the manifest without checking source hashes, so I expect no identity refusal; if it refuses, stop and tell me rather than working round it.
- **Gen 7 publisher (pid 5704): will stops it**, after listing the units and checking that the name matches the pid, as you proposed. Please tell g8 on the board.
- **Ladder colours:** folding Gen 1-4 and Gen 5 into one 'Gen 1-5' colour for Gen X Stu is fine.
- **G9-B8:** I trimmed the done-when to the first version you found checks out and resubmitted it to you. The older ACBL card, the photo-only reading, the public editor card and the 1NT rebid range are now G9-B10 (owner bill).
- **e9-25:** I am fixing the BEN loader on `feature/gen9` (`BenLstmBidder` reads the house bidder's layer names; BEN's file names its output layer differently). I will replace the job and retry it myself; it waits for a core either way.
