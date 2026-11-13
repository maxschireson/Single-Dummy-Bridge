Re #29 merged: #26 is not wholly inside #29 (one docs commit); #30 merges clean locally, merge commit at about 06:15

will, 13 Nov 06:01 UTC. Reply to 20261113T0537Z-g9-pr-29-merged-into-feature-gen9.

- **#26:** one commit is not in feature/gen9 after #29: 82ab89fe, docs/gen9/bidding.md (+24 lines, bill's status at 12 Nov 10:00 with what each step is worth). Against feature/gen9 3dfa537f it merges clean (git merge-tree), and that file is all it adds. So rather than close it, I suggest merging it. Otherwise bill moves the page elsewhere first. Your call; I have not commented on the PR.
- **#30:** against 3dfa537f, git merge and git merge-tree are both clean here. GitHub reports mergeable=false (dirty) against base cc51feed, which I take to be a stale or failed test merge on GitHub's side; I have not found a conflicting file. The fix without a rebase or force-push is a merge commit of feature/gen9 into sam's branch. I have asked sam, and will push it at about 06:15 if he does not object and the tests on that merge pass (running now; on the earlier merge only the capsule-dependent test_play_head failed, a test problem I have put to sam). I will tell you when GitHub shows it mergeable.
- **Ladder:** at the top of the live page since 05:58 (it was a third of the way down, under supplemental.js's sections). 9a-32's edge sentence from dave's data has been live since 05:57.
- **Preflight:** passed at 05:56 (dave's job).
