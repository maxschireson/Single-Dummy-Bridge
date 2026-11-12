# Work ledger: tasks, inboxes and leases for the project's agents

Status: proposed on 12 November 2026 by `will` (Gen 9 workflow and infrastructure helper) for the
Gen 9 lead and its helpers. Not yet adopted for the Azure fleet: until the lead or Max says so, the
allocation table in `BOARD.md` on `box/coordination` remains the record of who holds which box.

Several Claude sessions work on this project at once and cannot message each other. Until now they
have coordinated in prose on `box/coordination`, with a hand-edited allocation table. That works for
two or three sessions on a few boxes. Gen 9 adds a lead with four helpers and wants tasks that are
checked out and back in and experiments that come and go, which needs state a script can read and
change without two sessions colliding.

The ledger is branch **`work/ledger`**, written only by [`ops/work/ledger.py`](../ops/work/ledger.py)
(standard library only, Python 3.8 or later, git 2.x). Its `STATUS.md` is the human view and is
regenerated with every change.

## How it stays consistent

Each change fetches the branch tip, applies the change to that tip, and pushes one commit without
force. If another agent pushed in between, the push is rejected and the change is applied again to
the new tip, re-checking its preconditions. So two agents cannot both check out the same task or
hold the same lease: the second one gets `refused: T004 is checked out by bill until ...` (exit
status 3). Unrelated changes made at the same moment both land. The script keeps its git state in
`~/.cache/workledger`, so it never touches a source checkout. Nobody edits the branch by hand.

## What is in it

| Thing | Path | Notes |
| --- | --- | --- |
| Agent | `agents/<name>.json` | Name, role, session link, last seen. Names are lower case (`lead`, `bill`, `sam`, `dave`, `will`); `all` is reserved |
| Task | `tasks/T001.json` | Title, kind (`design`, `code`, `experiment`, `research`, `review`, `ops`, `docs`), priority `p0` to `p3`, who it is for (or anyone), dependencies, spec, box needs, state, claim, outputs, result, and an event history |
| Message | `inbox/<name>/<id>.md` | Front matter (from, to, subject, task, reply_to, sent, read_by) and a markdown body. `inbox/all/` reaches everyone |
| Lease | `leases/<resource>.json` | Holder, purpose, task, since, until. Resources are names like `box:azure2`, `gpu:studio1`, `feed:arena-gen9-x` |
| Log | `log/<date>.jsonl` | One line per change, for `watch` |

## Task life

```
open --claim--> claimed --review--> review --done--> done
  ^                |  \--done/fail--------------> done / failed
  |                |--release--> open
  |                \--block----> blocked --reopen--> open
  \--------------------reopen (from any state)
cancel (author or holder) --> cancelled
```

- **Check out** with `claim ID --hours H` (default 4). The claim expires; renew it with `renew`
  or `claim` again. A claim that has run out shows as `claimed (lapsed)`. Taking over a lapsed
  claim needs `--takeover` and sends the previous holder a message; a live claim cannot be taken.
- A task **for** an agent can be claimed only by that agent, and a task with unfinished
  **dependencies** only once they are done, unless `--force` (when they agreed, or to start early).
- **Check in** with `review` (the task's author is told and accepts with `done` or sends it back
  with `reopen`), with `done`/`fail` and a result, or with `release` if unfinished.
- **Outputs** are `KIND=REF` pairs: `branch=feature/x@abc1234`, `report=reports/x/README.md`,
  `feed=arena-gen9-x-feed`, `pr=#15`. Results state tested scope and uncertainty, as for any
  [research handoff](../CONTRIBUTING.md#research-handoff).
- Closing, blocking, reviewing and reopening send the other party a message automatically.

## For the lead

```bash
L="python3 ops/work/ledger.py --as lead"
$L hello --role "Gen 9 lead" --session https://claude.ai/code/session_...
$L add "Convention card to rules-based scorer" --kind code --for bill --priority p1 \
       --spec-file /tmp/spec.md --effort 6
$L add "Bench the card scorer against the v1a net" --kind experiment --depends T001 --boxes 1 --box-hours 3
$L send all "Gen 9 plan v0" --file /tmp/plan.md
$L status            # or read STATUS.md on the branch
```

A spec says what to build, where the result goes and when it is done. Design-review checkpoints
are tasks of kind `review` that the build tasks depend on.

## For a helper

```bash
W="python3 ops/work/ledger.py --as bill"
$W hello --role "Gen 9 bidding systems helper" --session https://claude.ai/code/session_...
$W watch             # changes since you last looked (* = about you), unread mail, claims about to lapse
$W read <message id>
$W next              # open tasks you could check out now, best first
$W claim T001 --hours 3
$W note T001 "parser handles ACBL; WBF next"
$W review T001 --note "ready" --output branch=feature/gen9-cards@1a2b3c4
$W send lead "Question on T001" --task T001 --body "Should 2/1 GF be its own profile?"
```

A helper session that is listening runs `watch` at each check-in (every 20 to 30 minutes is
enough), reads what is new, and acts. `watch` refreshes the agent's `last_seen` at most every 15
minutes, which is how the lead can see who is alive.

## Experiments and boxes

An experiment is a task of kind `experiment` with `--boxes N --box-hours H`. Whoever runs it leases
the box (`lease box:azure2 --hours 3 --purpose "T007 card scorer bench" --task T007`) and can queue
its command through [boxctl](boxctl.md) from the ledger:

```bash
$W dispatch T007 azure2 --file job.sh --timeout 3600   # refused unless bill holds box:azure2
```

The boxctl command id is recorded on the task as an output (`boxctl=azure2/<id>`). Box leases here
are advisory for now: they do not replace the allocation table on `box/coordination` until the
lead or Max adopts them, and the [operations rules](operations.md) still apply (a lapsed lease or
an old heartbeat is a reason to ask, not to take over a running job).

## Fleet view

`ledger.py --as NAME fleet` reads every box's heartbeat from `box/<box>/status` and the "Now" column
of the allocation table in `BOARD.md`, stores them in `fleet.json` and adds a **Boxes** table to
`STATUS.md`: heartbeat time (flagged when more than 12 minutes old), load against CPUs, free memory
and disk, the boxctl command queue, what the board says, and any ledger lease. It takes about ten
seconds and changes nothing on the boxes or the board. The table is as fresh as the last `fleet`
run, whose time it shows.

## Not done yet

- No leases are imported from `BOARD.md`; the two would disagree if both were edited.
- No GitHub-side protection on the branch beyond the no-force convention.

## Tested scope

`tests/test_work_ledger.py` (10 tests) runs the script against a local bare repository, with each
agent in its own cache as separate sessions would be: a claim race in which a second agent checks
the task out between the first agent's read and push (exactly one holder results), unrelated
concurrent changes that both land, lapsed claims and leases needing `--takeover` and telling the
previous holder, dependencies and assignment checks, review and close messages, block, reopen and
cancel, read receipts and broadcasts, the allocation-table parser and the Boxes table, and the command line. Not covered: `dispatch` (it calls the
boxctl client, which has its own tests), and the live reads and pushes to GitHub, checked by hand
when the branch was opened (six boxes read in about nine seconds).
