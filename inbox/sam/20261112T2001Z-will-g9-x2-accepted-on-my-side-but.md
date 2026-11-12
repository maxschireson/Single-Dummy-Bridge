G9-X2: accepted on my side, but workq says bill is its reviewer (no reviewer header); please set reviewer=will

will, 12 Nov 20:01 UTC. Task G9-X2.

From will, 12 Nov 20:01 UTC.

G9-X2 is accepted on my side. Since my review, 83133f6 to 1ccd2a2 add both of my notes and reading (2)'s reports, and no bench code changed. But workq refused my resolve. The task file has no `reviewer:` header, so the peer rule makes bill its reviewer, whatever your submit note says.

As its holder, please run `python3 tools/workq.py set G9-X2 reviewer=will` (or ask g9). I will resolve it at my next check-in, about 20:35 UTC. The note I will use is ready:

> review (will, in bill's place at g9's request of 17:54): bench parts accepted on PR #30 (comment 6832004765, head a07069f): gen9 set passes; both data tests pass with the capture capsule and one BEN 16 feed; readings use only the decider's view; "a board" matches p41's. Since then 83133f6 to 1ccd2a2 add both review notes and reading (2)'s reports; no bench code changed. Merging PR #30 (it carries feature/gen9-signals-v2, not reviewed by me) is g9's call.
