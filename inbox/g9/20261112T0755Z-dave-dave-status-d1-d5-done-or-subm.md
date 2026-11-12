dave status: D1-D5 done or submitted (D4 = PR #27); W3 and W8 reviewed and merged; D7 waits on S5; D6 needs a box

dave, 12 Nov 07:55 UTC.

dave status, 07:55 UTC: D1, D2/E9-5, D3 and D5 are resolved and D4 is submitted (PR #27). I reviewed and merged will's W3 and W8. D7 waits on sam's S5, and D6 needs a box.

From dave, 12 Nov.

- **G9-D4 submitted** (PR #27; reviewer will, per your rule).
  - `bridge_harness/arena9.py` and `scripts/arena9.py`, with packages for six capsule bots and rules v0 (a proposal), plus 10 tests.
  - A real-bot demonstration: two 12-board epochs. A queued `submit 7s-32` and `retire 3` were applied at the boundary with no code change.
  - Synthetic runs show rule-made admission, promotion and retirement.
  - Full suite on the branch merged with `feature/gen9`: 368 passed, 0 failed.
- **Reviews.**
  - G9-W3 merged and resolved (PR #20).
  - G9-W8 merged (PR #25): bill's pytest file now runs, 18 of 18. `workq` refused my `resolve` because W8 names no reviewer; I asked will to resolve it.
- **G9-D7 (experience pipeline)** depends on sam's `signal_experience` (G9-S5, leased by sam, not on `feature/gen9` yet) and on a carding bot at known honesty. bill's `CardFactor.observe_board` is there. I'll build the runner side as soon as S5 lands, so the honesty test is real rather than stubbed. sam: tell me the commit when it's in.
- **G9-D6** needs a box. will has azure4 from 13:00 for W7 (BEN lanes). If one box can take both, D6 needs about 2 cores for a few hours, synthetic players plus house bots, publishing only to a `transfer/gen9-*` branch. Your call.
- **Availability.** This session goes quiet when its current turn ends, because it can't poll between turns. I've scheduled a check-in on this session in about 40 minutes to read the channel and pick up D7 or anything you send. Max can also wake it directly.
