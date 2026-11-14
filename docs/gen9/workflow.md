# Gen 9 workflow: a work queue for a project that never stops

> Design note for G9-W1, by will (workflow and infrastructure), 12 November 2026. For review by g9.
> **Interface change (section 7, I8):** the task and experiment files keep their format; `tools/workq.py`
> becomes the writer of their lifecycle fields (it is on `team/gen9` since 07:06 UTC, G9-W2), and this
> note proposes five optional header fields (`parent`, `budget`, `value`, `effort`, `reviewer`) and
> three checks (executor-ready, experiment result at submit, archive). No other interface changes.

## 1. What stays and what changed

**Stays.** One markdown file per task, experiment and message on a channel branch, a `key: value`
header plus sections, git history as the record, everything readable on GitHub. Agents and people
read the same files; nothing needs a server.

**Changed already (W2).** One program writes lifecycle fields. Each change is a commit on the
branch tip pushed without force; a rejected push makes it re-read the tip and re-check before trying
again, so a lease cannot be granted twice and a half-applied change never lands. STATUS.md is
rebuilt inside that commit, every state change writes a dated `## Log` line, every header is
validated on write, and the other party is messaged (reviewer on submit, holder on resolve).

**Measured from a session sandbox, 07:10 UTC:** a read of the whole branch 0.7 s, a write 2.4 s;
84 files, 34 commits in the channel's first 30 minutes. Each change reads the whole tree. **Estimate, not
measured:** retries stay rare while writes average more than about 5 s apart (some 700 an hour);
today's rate is about one a minute. Past that, split the channel by area (one branch each, same
tool) before reaching for a service.

## 2. Life cycle and format

States stay as they are: `proposed → open → leased → submitted → resolved`, and `blocked`. The
prospectus's `running` and `evaluated` are not new states: a running experiment is `leased` with
its box jobs listed in a `jobs:` field (W5), and for an experiment `submitted` is evaluation
pending. Fewer states keeps every tool and reader simple.

**Leases** last at most 4 hours and are renewed while working; an expired lease may be taken over
by the owner or g9 thirty minutes after it ends, with the previous holder told. **Dependencies**
inform but do not block: a lease before a dependency resolves is allowed and logged (W2 after W1
is the pattern g9 asked for), and STATUS shows `after G9-x`.

**Proposed optional fields**, all ignored by older readers:

| Field | Meaning | Why |
| --- | --- | --- |
| `parent` | The task, experiment or bot this builds on | Prospectus: ideas enter with a parent; integration is deliberate |
| `budget` | Box-hours this may use, as a number | Lets `workq` sum committed compute against boxes (§4) |
| `value`, `effort` | Expected gain in a named unit; agent-hours | Ordering by value for effort (§4) |
| `reviewer` | Who reviews, if not g9 | Already honoured by `submit` and the review list |

**Experiments.** Leasing is refused until hypothesis, primary metric and population, compute cap
and stopping rule are filled (in since W2; all eight E9 files pass). Proposed for `submit`: refuse
an experiment whose `## Result` is still `_not yet_` or lacks three lines, `Evidence:` (prediction,
double-dummy proxy or played boards), `Sample:` (count and interval), and `Revisit if:` (the
conditions under which the idea is worth trying again, so a later agent can tell a dead end from
an idea tested too narrowly). Verdicts stay `adopted | rejected | inconclusive | retired`; nothing
is deleted.

**Never stops.** Ids lose the generation from the next channel on (`B-123`, with `gen:` as a
field), because a standing population has no generation boundary for work to cross. Resolved
files older than 14 days move to `archive/<YYYY-MM>/` (`workq archive`); ids are never reused.

## 3. Briefing an executor

An executor is a fresh session given one task and nothing else. A task is **executor-ready** when
its file has these sections, and `workq check --ready ID` says which are missing:

- **Base**: branch and commit to start from.
- **Interface**: the files, functions and schemas it may change, and what it must not touch.
- **Done when**: statements a reviewer can check.
- **Time box**: hours; the lease is no longer.
- **Tests**: the W3 command and which test files must pass.
- **Results**: branch name, report path, reviewer.

`workq brief ID` prints the task file, then the rules that always hold (hidden hands are labels and
never inputs; nothing from EPBot/BBA; frozen runs and feeds are not edited; never force-push; end
commits with your session trailer), then the exact commands to lease, log and submit. Starting an
executor then takes three lines, the same whether it is a sub-agent or a chat Max opens:

    You are executor billx1 on the Gen 9 channel (branch team/gen9 of maxschireson/Single-Dummy-Bridge).
    git fetch origin team/gen9 && git show FETCH_HEAD:tools/workq.py > /tmp/workq.py
    python3 /tmp/workq.py --as billx1 brief G9-B7    # then do that task, and only that task

Executors are named `<lead>x<n>` so STATUS shows whose they are; the lead reviews; the session ends
at submit. Whether sub-agents may be started is with Max (g9 has put it to him).

## 4. Priority by value for effort

g9 sets the class (`high | medium | low`). Within a class `next` orders by `value × probability ÷
effort` when both fields are present, else by due date. Three guards from the prospectus:

- **Exploration share**: a fixed part of box-hours (proposed 20%) goes to experiments marked
  `explore: yes` even when their score is low.
- **Incubation**: changes that need training before they can play well carry `incubate: <hours>`
  and are judged after it, not on their first match.
- **Sweeps**: at most two open parameter-sweep experiments per area, so cheap sweeps cannot fill
  the queue.

The estimates are guesses and are used for ordering only. W4 compares estimated effort with lease
time and box-hours actually used, which says how much to trust them.

## 5. Too few thinkers or too few executors (W4)

From the git history of each file and its log lines, per owner and kind:

| Signal | Reading |
| --- | --- |
| `pool` tasks open and unleased for more than an hour | add executors |
| Submitted work waiting more than two hours for review | the reviewer is the bottleneck: add a lead or split an area |
| Leases that expire unfinished; tasks given back | tasks are too big: a decomposition problem |
| Boxes idle (from `fleet` readings) while experiments wait | add executors; boxes full means more executors add nothing |
| Reopen count per submission | briefs or reviews are unclear |

The first report goes in Friday's review, with the starting numbers in the work plan as the
baseline.

## 6. A phone view: GitHub issues or STATUS.md

STATUS.md renders on GitHub mobile but is long. A full mirror of tasks to issues would be a second
place to answer things and would notify on every change, so I propose two narrow uses instead:

1. **One pinned issue, "Gen 9 queue"**, whose body `workq` rewrites from a short summary (decisions
   waiting, reviews waiting, blocked, in progress, next checkpoint). As far as I know, editing an
   issue body sends no notification (to be checked before building), so it is a page Max can open,
   not a stream.
2. **A `DECISION:` becomes an issue only when g9 chooses to raise it**, labelled `decision` and
   assigned to Max, so he is notified exactly for what needs him. `workq` copies his reply on the
   issue into `inbox/g9/`, so the channel stays the record.

Both need `gh api` (REST), which works from g9's and my sessions; sam has no `gh`, and the tool
skips the step where it is missing. Neither is built until g9 agrees.

## 7. The two boards

- **Now.** `box/coordination` keeps the allocation table and the prose between g7, g8, p41 and
  dash; `fleet/azure` keeps the operator's experiment list. Gen 9 reads both (`workq fleet` shows
  the table's "Now" column beside each box's heartbeat) and asks for boxes on the board.
- **After Gen 8 launches, and only with g7's and g8's agreement on the board:** box leases become
  `workq` resources with the same lock and expiry, and the table on the board is generated from
  them; the prose stays on the board. The operator's experiments become E-files.
- **When the arena is a standing population:** one channel for the project, not one per
  generation, with every session (g7, g8, dash, the trainers) an agent on it under its own name.

## 8. Next

After review: the executor-ready check and `brief`, the experiment submit check, `archive`,
value-for-effort ordering, and the pinned issue if g9 wants it. In parallel, as ordered: W3 (test
runner), W6 (base swap script), W5 (box queue, when g9 has a box), W4 (metrics, Friday morning).
