PRs #26, #29, #30 into feature/gen9: #29 and #30 pass; #26 is nearly all inside #29; ladder live

will, 13 Nov 05:23 UTC.

Tested on new checkouts of feature/gen9 at 14a7d694 (05:03 UTC). Each PR was merged locally (nothing pushed), then `scripts/run_tests.py --prepare --jobs 2` (DDS built, 13 nets restored), with GEN7_CAPSULE set to the Gen 7 capture capsule and BEN_FEEDS to one BEN feed so the data tests run.

**Readiness:**
- **#29** (feature/gen9-arena-arrival d029c7da): merges clean. 448 passed, 0 failed. Its one skip (test_arena9_pipeline's capsule test, which reads a fixed path /home/claude/capsule/recovery rather than an environment variable) passes with a capsule there: 18 of 18. **Ready.**
- **#30** (feature/gen9-reading-bench fdc576d3): merges clean. 424 passed, 1 failed. The failure is test_play_head.test_decoder_state_reproduces_the_net (new in #30): KeyError '7s-32', because the capsule I gave it has no 7s-32. Its default is /home/claude/data/g7a1/recovery (the Gen 7 alpha capsule), which I do not have, and its skip condition checks only that a manifest exists, so a capsule without 7s-32 fails it instead of skipping it. The reading bench's two data tests ran and passed. **Ready**, with that test unverified on its intended capsule; sam may want the skip to check for the bot.
- **#26** (feature/gen9-bidding-cards 82ab89fe): alone it conflicts with feature/gen9 in configs/gen9-proto-bots.json (both add bot entries at the same place; the fix is to keep both). 22 of its 23 commits are already in #29. Merged after #29 it is clean and adds only its last commit, docs/gen9/bidding.md (+24 lines). **Ready after #29**, or close it as merged through #29.
- **All three** in the order #29, #30, #26: clean. 460 passed, 1 failed (the same test_play_head test), 1 skipped (the same fixed-path test, which passes with the capsule). Reports are on request.

**Box:** cancelling e9-12-* and e9-4-* for the cohort, as you asked, needs a permission I do not have. workq lets only a job's owner or you cancel; my operator rights are priority, move and retry. Two ways:
- you add cancel to the operators' rights, and I make the one-line change to job_cancel;
- or you or the owners cancel when dave says the cohort is ready.
dave's preflight (priority 1, 1 core) is valid and starts when e9-12-x frees cores (about 05:36), since all 8 are busy.

**Ladder:** live on the arena page since 05:21 (gh-pages 03619d6). I checked from azure4 that index.html carries the two lines and that ladder.js and ladder.json are served with the hashes I pushed. Hourly refresh from now; 9a-32's edge sentence arrives with dave's next ladder.json.
