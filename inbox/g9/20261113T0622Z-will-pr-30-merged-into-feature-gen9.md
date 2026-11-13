PR #30 merged into feature/gen9 (094db2d7)

will, 13 Nov 06:22 UTC. Reply to 20261113T0616Z-g9-go-for-the-gen-9-cohort-on-azu.

- **The merge:** I pushed the merge commit of feature/gen9 3dfa537f into feature/gen9-reading-bench as c877d10b. It is a merge, not a rebase, so nothing was force-pushed. sam had not replied when I pushed. GitHub then showed #30 mergeable (clean), and I merged it by REST, pinned to c877d10b: feature/gen9 is now 094db2d7.
- **Tests on that tree** (new checkout, --prepare, the Gen 7 capture capsule and a BEN feed): 461 passed, 1 failed. The failure is test_play_head's capsule test (KeyError '7s-32' with a capsule that has no 7s-32), a skip condition for sam to tighten.
- **#26:** left open for its docs commit, as you say.
- **Box:** with E9-4's jobs cancelled, azure4 is free for dave's cohort jobs. I validate each job file as it lands and keep e9-0-n04 and e9-16-h-v-p behind them.
