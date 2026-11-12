# Work ledger

Tasks, inboxes and resource leases for the agents working on this project. Written only by
`ops/work/ledger.py` (on the source branch that carries it); read `STATUS.md` for the current view.
Protocol: `docs/work-ledger.md`. This is a channel branch, like `box/*` and the feed branches:
never merge it into source, never force-push it.

| Path | What |
| --- | --- |
| `STATUS.md` | Generated after every change: agents, unread mail, tasks by state, leases |
| `agents/<name>.json` | Who is working here: role, session, last seen |
| `tasks/<id>.json` | One task: spec, state, claim (who has it checked out, until when), events, outputs |
| `inbox/<name>/<id>.md` | Messages to one agent; `inbox/all/` is for everyone |
| `leases/<resource>.json` | Who holds a resource (for example `box:azure2`) and until when |
| `log/<date>.jsonl` | One line per change |
