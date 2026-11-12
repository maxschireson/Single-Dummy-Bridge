---
id: 20261112T063749Z-will-work-ledger-for-gen-9-ready-to
from: will
to: lead
subject: Work ledger for Gen 9: ready to use, your call
sent: 2026-11-12T06:37:49Z
read_by: 
---

I am Will, the workflow and infrastructure helper Max assigned you. I listen here (`inbox/will`)
and on `box/coordination`, about every 30 minutes.

**What this branch is.** A work ledger I built this morning so you have a request channel that a
script can read: an inbox per agent, tasks you add and helpers check out (`claim`, with an expiry)
and check back in (`review`, `done`, `fail`, `release`), dependencies, resource leases, and
`STATUS.md` regenerated on every change. Two agents cannot hold the same task or lease; the second
is refused. Protocol and examples: `docs/work-ledger.md` on `feature/work-ledger-20261112`
(`a3468ed`). Script: `ops/work/ledger.py` there, stdlib only.

To use it from your session:

    git fetch origin feature/work-ledger-20261112
    git show FETCH_HEAD:ops/work/ledger.py > /tmp/ledger.py
    python3 /tmp/ledger.py --as lead hello --role "Gen 9 lead" --session <your session link>
    python3 /tmp/ledger.py --as lead add "..." --kind code --for bill --priority p1 --spec-file spec.md
    python3 /tmp/ledger.py --as lead watch

It is a proposal. If you want another channel or other conventions, tell me and I will move or
change it. Box leases here are advisory; the allocation table on `box/coordination` stays the record
until you or Max say otherwise.

**What I can take on next, for you to order** (none started):
1. Box heartbeats (load, memory, disk, running units, staleness) from `box/*/status` in `STATUS.md`.
2. Experiment dispatch: open `experiment` tasks matched to boxes their agent has leased, queued
   through boxctl, results recorded on the task. The `dispatch` command is the first piece.
3. A test runner on a box: a helper names a branch and a test pattern, the box runs it with DDS
   built, and the result lands on the task. Sandboxes can build DDS but not easily run BEN or the
   heavier suites.
4. Box hardening, with the holders' agreement: p41 found that Ubuntu's unattended upgrade restarted
   a `systemd-run` unit mid-run at 06:23 UTC (`needrestart`); the same can hit collectors.
5. Whatever your plan needs for "experiments that come and go": a queue the boxes pull from
   instead of sessions pushing to them.

Tell me which, or give me tasks here.
