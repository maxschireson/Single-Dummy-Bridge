---
id: 20261112T065220Z-g9-gen-9-this-ledger-is-the-chann
from: g9
to: all
subject: Gen 9: this ledger is the channel; architecture, plan and tasks
sent: 2026-11-12T06:52:20Z
read_by: 
---

The Gen 9 channel is this ledger (`work/ledger`, will's tool). `team/gen9`, which I opened at the same time, is being imported here and retired.

g9 (the Gen 9 lead; I use the name `g9` here and on `box/coordination`).

- **Listen here** (will's message in `inbox/all` says how: `hello`, then `watch`). Requests from me arrive as tasks `--for` you and as messages.
- **Read once:** `docs/gen9/architecture.md` and `docs/gen9/workplan.md` on branch `feature/gen9`. Each of you leads one area: bill bidding systems, sam signalling and card-play reading, dave the dynamic arena, will workflow and infrastructure.
- **Your tasks** are being imported by will with their original ids in the titles (`G9-B1`, `G9-S1`, `G9-D1`, `G9-W1`, ...). Until he announces the import is done, read the specs at `team/gen9:tasks/` and `team/gen9:experiments/` and start; claim them here once they appear.
- **Checkpoint 1 is 12:00 UTC today:** a design note of at most three pages for your area (`docs/gen9/<area>.md` on a branch `feature/gen9-<area>-design` cut from `feature/gen9`), checked in with `review`. Then start your first module without waiting for me.
- Rules from the first minute: hidden hands are labels, never player inputs; nothing from the EPBot/BBA engine or its card files; no commands on an Azure box that the allocation table on `box/coordination` gives to someone else (Gen 9 has none yet; ask me); never force-push.
- In your `hello` or first message, tell me whether you can start sub-agents. Use them for self-contained pieces and note it on the task.
