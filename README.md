# Gen 9 team channel

> **This branch is the Gen 9 channel** (`work/ledger` is retired). **Use `tools/workq.py`** to lease,
> renew, submit, resolve and message (section "workq" below): each change is one commit on the
> current tip, so two leases cannot both win, and `STATUS.md` is regenerated in that commit. If you
> edit files by hand instead, follow the hand protocol below and **never touch `STATUS.md`**.

Branch `team/gen9` of `maxschireson/Single-Dummy-Bridge`. It is how the Gen 9 sessions talk to
each other and keep their task and experiment lists, because sessions cannot message each other
directly. It is a channel like `box/coordination`: **never merge it into source, never
force-push it.**

Who is who: [ROSTER.md](ROSTER.md). Where things stand: [STATUS.md](STATUS.md) (generated).
Source work does not live here; it lives on `feature/gen9` and branches cut from it (see
"Source branches" below).

## If you are a helper starting up

1. Clone only this branch and keep it apart from your source checkout:
   `git clone --single-branch -b team/gen9 https://github.com/maxschireson/Single-Dummy-Bridge ~/team`
2. Read this file, `ROSTER.md`, then every file in `inbox/<your name>/` and `inbox/all/`, oldest first.
3. Acknowledge: write one message to `inbox/g9/` (format below) saying you are up, with your
   session link, the tools you have (git push, `gh api`, Azure boxes through boxctl or not,
   sub-agents or not), and anything in your brief you would change.
4. Lease your first task (below) and start. With `workq` (next section), steps 2 to 4 are
   `hello`, `inbox`/`read`, `send g9 ...` and `lease`.

## workq

`tools/workq.py` does this page's protocol from the command line. It needs Python 3.8+ and git,
nothing else, and keeps its own clone in `~/.cache/workq`, so it never touches a checkout; it
works from any directory. Get it from this branch:

    git fetch origin team/gen9 && git show FETCH_HEAD:tools/workq.py > /tmp/workq.py
    Q="python3 /tmp/workq.py --as <your name>"
    $Q hello --role "<your role>" --session <your session link>     # once
    $Q watch          # at each check-in: changes since you last looked (* = yours), unread mail,
                      # leases about to end, submissions waiting for your review
    $Q inbox; $Q read <id>; $Q ack                                  # unread; read one; all read
    $Q send g9 "One-sentence point" --task G9-B2 --body "details"   # or --file note.md; TO may be all
    $Q next           # open tasks you may lease, best first
    $Q lease G9-B2 --hours 3          # at most 4; leasing again renews; refused if someone holds it
    $Q log G9-B2 "result, blocker or change of plan"
    $Q submit G9-B2 --branch feature/gen9-bidding-filter --commit 1a2b3c4 --note "done, tested, open"
    $Q release G9-B2 --note "partial work on ..."     $Q block G9-B2 --note "why, and what unblocks it"
    $Q resolve G9-B2 --resolution accepted --note ... # reviewer; experiments: adopted|rejected|inconclusive|retired
    $Q reopen G9-B2 --note "what must change" [--same-holder]
    $Q new "Title" --area bidding --kind module --owner bill --priority high --due 2026-11-13T10:00Z \
       --depends G9-B1 --goal "..." --done-when "..." --context "..."     # or --body-file; --proposed
    $Q edit E9-1 --file sharper.md    # sections and free header fields; never state, holder, lease or log
    $Q set G9-B2 priority=low reviewer=bill
    $Q fleet          # refresh the Boxes table in STATUS.md (box heartbeats, what the board says)
    $Q refresh        # regenerate STATUS.md after hand edits
    $Q check --ready G9-B7   # which executor sections a task lacks (Base, Interface, Done when, Time box, Tests, Results)
    $Q brief G9-B7    # all a fresh session needs to do the task: the file, the rules, the commands (docs/gen9/workflow.md §3)

It checks every header it writes and refuses a malformed one (`check` lists any on the branch),
applies the lease rules below (owner, `pool` or g9 may lease; `proposed` needs g9; an expired lease
may be taken over by the owner or g9 30 minutes after it ends), refuses to lease an experiment
whose hypothesis, primary metric and population, compute cap or stopping rule is empty, writes a
dated `## Log` line for every state change, and tells the other side (the reviewer on submit, the
holder on resolve or reopen, g9 and the owner on block). A refusal prints `refused: ...`, exits
with status 3 and writes nothing. Set `WORKQ_TRAILERS` to your session trailer to have it added to
the tool's commits. Tests: `python3 tools/test_workq.py`.

## Layout

| Path | What | Who writes |
| --- | --- | --- |
| `inbox/<name>/<stamp>-<from>-<slug>.md` | One message to `<name>`. One file per message, never edited afterwards | Anyone |
| `inbox/all/` | Messages for everyone | Anyone |
| `tasks/<ID>.md` | One task: header, goal, done-when, log | g9 and area leads create; the holder updates |
| `experiments/<ID>.md` | One experiment: hypothesis, metric, stopping rule, result | Whoever proposes; the holder updates |
| `STATUS.md` | Tasks and experiments by owner and state, waiting for review, agents, latest messages, boxes | Generated by `tools/workq.py` in each change's commit; do not edit by hand |
| `agents/<name>.json` | Role, session, last seen, which messages you have read | `workq hello`, `watch`, `read`, `ack` |
| `log/<date>.jsonl` | One line per change made with `workq`, read by `watch` | `workq` |
| `fleet.json` | The last `workq fleet` reading | `workq` |
| `tools/` | Scripts for this channel | will |

`<stamp>` is UTC, `YYYYMMDDTHHMMZ`. `<from>` and `<name>` are roster names (`g9`, `bill`,
`sam`, `dave`, `will`). Example: `inbox/g9/20261112T0710Z-bill-up.md`.

## Messages

- A message is a new file. Never edit or delete one; answer with a new file in the sender's inbox.
- First line: what you need or what you are reporting, in one sentence. Then details. Link
  task ids, branches and commits (full branch name, short sha).
- Poll (`workq watch`, or `git pull --rebase` and list your inbox and `inbox/all/`) at least every 10 minutes
  while idle and at every natural break (at most 30 minutes apart) while working.
- Anything Max should decide goes to `inbox/g9/` with `DECISION:` at the start of the first
  line. g9 collects those for him. Do not wait on one unless your task says to; pick the most
  reasonable reading, say which you took, and carry on.

## Tasks: check out, work, check in

A task file starts with a header of `key: value` lines between two `---` lines:

    ---
    id: G9-B1
    title: Card IR v0
    area: bidding            # architecture | bidding | signals | arena | workflow
    kind: design             # design | module | experiment | review | ops
    owner: bill              # who is responsible; `pool` = any executor may lease it
    state: open              # proposed | open | leased | submitted | resolved | blocked
    holder:                  # who holds the lease now
    lease_until:             # UTC; at most 4 hours ahead; renew while you work
    priority: high           # high | medium | low
    depends:                 # task ids, comma separated
    due: 2026-11-12T12:00Z
    branch:                  # where the work is
    resolution:              # when resolved: accepted | dropped | superseded
    ---

then `## Goal`, `## Done when`, `## Context`, `## Log`.

By hand (`workq` does each step for you, with the same rules):

- **Check out (lease).** Set `state: leased`, `holder: <you>`, `lease_until: <UTC>`; commit
  `task(<ID>): lease by <you>`; `git pull --rebase`; push. The push is the lock. If it is
  rejected, pull again; if the file now names another holder or the rebase conflicts in that
  file, you did not get the task: drop your change.
- **While working.** Renew `lease_until` before it passes. Add a dated line to `## Log` when
  something changes that another session would want to know (a result, a blocker, a change of
  plan). Work only on tasks you hold.
- **Check in.** Set `state: submitted`, fill `branch` (and the commit or PR in the log), write
  what was done, what was tested and what is unresolved; push; then send one message to the
  reviewer (see Review).
- **Who reviews** (g9, 12 November 07:28 UTC): a `module` task is reviewed by its owner's peer lead,
  bill and sam each other's, dave and will each other's; design notes, experiment verdicts and every
  other kind go to g9. A `reviewer:` header overrides both. `workq submit` tells the right one, and
  STATUS.md's "Waiting for review" lists each submission under its reviewer.
- **Review.** The reviewer either sets `state: resolved` with a `resolution`, or sets
  `state: open` (or back to `leased` for the same holder) with what must change in the log.
- **Give a task back.** `state: open`, clear `holder` and `lease_until`, say in the log where
  the partial work is.
- **Blocked.** `state: blocked` with the reason and what would unblock it; message whoever can.
- **Expired lease.** A lease more than 30 minutes past `lease_until` may be taken over by its
  owner or g9, with a log line. Nobody else takes it without asking.
- **New tasks.** Area leads create tasks in their own area (`state: open`, or `proposed` when
  it needs g9's agreement first). Ids: `G9-<letter><number>`, letters A architecture,
  B bidding, S signals, D arena, W workflow, X cross-area.

## Experiments

Same life cycle as a task, in `experiments/<ID>.md` (ids `E9-<number>`), with these sections
filled **before** it runs: hypothesis; the mechanism you expect; primary metric and the
population it is measured on; regression slices; compute cap; stopping rule. After it runs:
result with its uncertainty and sample count, kind of evidence (prediction, double-dummy
proxy, or played boards), where the data and code are, and one of
`adopted | rejected | inconclusive | retired`. Negative and inconclusive results are kept.
An experiment that stops being worth its compute is `retired` with a line saying why, not
left running.

## Git rules for this branch

- `git pull --rebase` before every push. Never force-push. Small commits, one concern each.
- Message files never conflict (unique names). A task or experiment file has one writer at a
  time: its holder, or its reviewer once it is submitted.
- End commits with your own session trailer.
- Nothing secret here: the repository is public.

## Source branches

- `feature/gen9`: the Gen 9 integration branch. g9 merges into it. Design notes live there
  under `docs/gen9/`.
- Your work: `feature/gen9-<area>-<slug>` cut from `feature/gen9`; open a PR into
  `feature/gen9` when a piece is ready, and name the PR in the task log.
- Experiments that need engine code not yet on `feature/gen9`: a `research/gen9-<slug>` branch
  with the base commit named in the experiment file.
- The repository's own rules still hold (`AGENTS.md`, `CONTRIBUTING.md` on `main`): hidden
  hands are labels and never player inputs; frozen runs, manifests and feeds are not edited;
  feed, transfer, box and team branches are never merged into source.
- Nothing made with the EPBot/BBA bidding engine or its card files goes into Gen 9 (Max,
  12 November 2026).

## Boxes

The Azure boxes are allocated on `box/coordination` (`BOARD.md`). Gen 9 has none yet. Ask g9
in your inbox message if a task needs one; do not queue commands on a box that the allocation
table gives to someone else.
