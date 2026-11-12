G9-W6 submitted for your review: Script for the base swap

will, 12 Nov 07:33 UTC. Task G9-W6.

tools/base_swap.py and tools/test_base_swap.py (4 tests, synthetic repo) on team/gen9. Dry run reports hooks and drift; --apply rebuilds with --rebase-merges in a temporary worktree onto a new local branch, stops cleanly on a conflict, and checks every Gen 9 file change is the same patch; --also carries PR branches; --push never forces or rewrites. Trial on a copy (reports/base-swap-trial-2026-11-12.md): feature/gen9 at c69ea1e (26 Gen 9 commits, 8 merges) onto a stand-in main = main + snapshot content + the prototype's two later commits (to e9fde92, rule bidder r2). No conflicts; 57 of 57 Gen 9 file changes the same patch; one hook (a line in reports/README.md); five drifted files, all from r2. Gen 9 tests on the rebuilt branch: 171 pass, but tests/test_gen9_cards.py fails 5 of 18 there (passes 18 of 18 on feature/gen9): after 1NT-2H r2 super-accepts 3S where the card IR says 2S. Told bill. Suggestion for G9-A5: run the Gen 9 test set on the rebuilt branch before feature/gen9 is pointed at it.

Branch: team/gen9, commit 43c9a33.

Accept: `workq.py resolve G9-W6 --resolution accepted`. Send back: `workq.py reopen G9-W6 --note ...` (add `--same-holder` to return it to will).
