G9-D4 submitted for your review: Registry, epoch manifest and a one-machine epoch runner

dave, 12 Nov 07:50 UTC. Task G9-D4.

PR #27 into feature/gen9 (reviewer: will, per g9's 07:27 rule). bridge_harness/arena9.py, scripts/arena9.py, configs/players (6 capsule bots), configs/arena9 (rules v0 proposal, demo rules), 10 tests on synthetic boards, and a real-bot demonstration: two 12-board epochs where a queued submit 7s-32 and retire 3 are applied at the boundary with no code change (reports/gen9-arena-epochs-2026-11-12). Full suite on the merged branch: 368 passed, 0 failed. Not done: rule-made decisions with real bots (epochs too short), slots by push for several collectors (D6), BEN.

Branch: feature/gen9-arena-epochs, commit b565182.

Accept: `workq.py resolve G9-D4 --resolution accepted`. Send back: `workq.py reopen G9-D4 --note ...` (add `--same-holder` to return it to dave).
