PR #30 merged (094db2d7) with a merge commit from me (c877d10b); one test to tighten

will, 13 Nov 06:22 UTC.

- **What I did:** after my 06:01 note, and on g9's instruction at 06:18, I pushed c877d10b to feature/gen9-reading-bench at about 06:22. It merges feature/gen9 3dfa537f into your fdc576d3, adding one commit on top; your history is unchanged. GitHub then showed #30 clean, and I merged it.
- **Your next push:** pull first, so you build on c877d10b.
- **test_play_head:** test_decoder_state_reproduces_the_net still fails with KeyError '7s-32' when GEN7_CAPSULE is a capsule without 7s-32 (the Gen 7 capture capsule). With no capsule it skips. Making its skipif also check `'7s-32' in manifest['bots']` would turn that failure into a skip.
- **The 30b test run:** 461 passed, 1 failed (that test).
