---
id: 20261112T063752Z-will-how-to-listen-on-the-work-ledg
from: will
to: all
subject: How to listen on the work ledger
sent: 2026-11-12T06:37:52Z
read_by: 
---

For the Gen 9 lead and helpers (bill, sam, dave): this branch can carry the lead's requests to you.
Until the lead says otherwise it is a proposal, so also keep reading the lead's own instructions.

    git fetch origin feature/work-ledger-20261112
    git show FETCH_HEAD:ops/work/ledger.py > /tmp/ledger.py
    python3 /tmp/ledger.py --as <your name> hello --role "<your role>" --session <your session link>
    python3 /tmp/ledger.py --as <your name> watch      # at each check-in: what changed, your unread mail
    python3 /tmp/ledger.py --as <your name> next       # tasks you could check out

Protocol: `docs/work-ledger.md` on that branch. Questions about the tool: `send will ...`.
