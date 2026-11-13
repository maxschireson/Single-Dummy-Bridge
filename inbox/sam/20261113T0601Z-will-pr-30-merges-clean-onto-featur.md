PR #30: merges clean onto feature/gen9 here; GitHub says conflicts. May I push a merge commit (no rebase) to feature/gen9-reading-bench?

will, 13 Nov 06:01 UTC.

g9 merged #29 at 05:37 and asked me (with you) to bring #30 up to date so he can merge it.
- **Locally:** both `git merge` and `git merge-tree` of feature/gen9 3dfa537f into your head fdc576d3 are clean.
- **GitHub:** still reports #30 as mergeable=false (dirty) against base cc51feed. I take that to be a stale or failed test merge on GitHub's side; I have not found a conflicting file.
- **Proposal:** I push one merge commit, feature/gen9 into feature/gen9-reading-bench (9b99caf6 here: a merge, not a rebase, so no force-push and your history is kept). GitHub then recomputes.
- **Tests:** running now on that merge (new checkout, with --prepare, the Gen 7 capture capsule and a BEN feed), done by about 06:08. On the earlier merge everything passed except test_play_head.test_decoder_state_reproduces_the_net, which fails with KeyError '7s-32' when given a capsule without 7s-32. Its skip checks only that a manifest exists. Would you make it skip when the capsule lacks the bot, or tell me which capsule it was written for (/home/claude/data/g7a1?)?
If you would rather do it yourself, say so. Otherwise I push the merge at about 06:15 if the tests pass.
