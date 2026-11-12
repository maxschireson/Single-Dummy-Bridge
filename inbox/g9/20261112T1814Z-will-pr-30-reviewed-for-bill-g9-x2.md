PR #30 reviewed for bill: G9-X2 parts accepted; it also carries unreviewed signals-v2 (your call to merge)

will, 12 Nov 18:14 UTC. Task G9-X2.

From will, 12 Nov 18:14 UTC.

I reviewed PR #30 for bill and **accept the G9-X2 parts**: the bench stage, its report script, its tests and its report. The review is on the PR, comment 6832004765.
- The gen9 set passes: 229 tests.
- Both data-dependent bench tests pass with the capsule and one BEN 16 feed.
- The readings use only the decider's view.
- The "tricks a board" units match p41's.

**For you:** the PR also carries `feature/gen9-signals-v2`, about 90 files: signal code, E9-14's head, E9-15's expert, carding and run configs. I did not review that. Merging PR #30 into `feature/gen9` brings it in. Bill would have been the reviewer, so whether to merge now is yours.

G9-X2 is still leased to sam in workq, not submitted, so I cannot resolve it there yet.
