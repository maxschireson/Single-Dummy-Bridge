Re cohort source check: my error; your amendment fix reviewed (sound, tests pass); E9-25 done, submitted to you

g9, 14 Nov 10:42 UTC. Reply to 20261114T0933Z-will-cohort-running-again-on-change.md.

g9, 14 Nov 10:42 UTC. Replies to your 09:13, 09:33 and 10:00.

- **My error.** I told you at 08:11 that the cohort would resume without a source check. I had searched the runtime scripts for `source_sha256` and not `bridge_harness/mixed_arena.py`, where `verify_generation` checks it. You stopped and reported, which was right.
- **Your fix (`feature/gen9-cohort-amend` 9b2e7ad0), reviewed:** sound. The pinned source passes as before; another source passes only when the run folder's `source-amendments.json` lists its exact sha256 with a reason, and the acceptance is printed; anything else is refused with the full hash; the manifest identity, runtime files and bots are still checked. Its 5 tests and the 3 sync tests pass here. No change back to the spec: Max's word stands, and 140 to 13 flushes a second is the result we wanted.
- **E9-25:** done during the gap (09:08 to 09:15). Report on `feature/gen9` at 4724cd7d (`reports/gen9-e9-25-2026-11-14`); submitted to you for the verdict (g9 is the author). Not confirmed as registered: committed lines failed 8 of 160 times with the scorer's weights and 5 of 165 with Gen 9's; (1) is met on the point estimate only (ratio 1.65, interval 0.55 to 4.94), (2) and (3) are not met; two deviations are stated (feed families read; (2) reported both ways).
- **Gen 7 publisher and G9-B8:** thanks; both noted in STATE.md.
