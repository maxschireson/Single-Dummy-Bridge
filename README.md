# Azure fleet: experiment queue and messages

Four test machines run bridge-bot work for Max: `azure1` to `azure4`, each an Azure Standard_F8as_v6
(8 cores, 32 GB) in East US. One Claude session operates them ("the operator"). This branch is where
the operator and other sessions agree on what the machines do. It is a channel, like the feed and
`box/*` branches: never merge it into source.

Max asked for it on 12 November 2026: another session is prioritizing ideas for Gen 8, and the two
need a way to pass messages about how the machines are used, "with that chat directing but
reasonably respecting your priorities".

## Who decides

1. Max's direct instructions come first, to either session.
2. The Gen 8 planning session ("the director") decides how the fleet's time is split between
   experiments, by posting messages here.
3. The operator runs the machines, and keeps its own priorities in `EXPERIMENTS.md`. When a direction
   would displace an entry of higher priority, the operator says so here before acting and follows
   the director's answer; if the two still disagree, it is Max's call.

Only the operator starts and stops work on the machines. Two sessions sending commands to the same
machine would trip over each other, so the director directs here and the operator acts.

## Files

| File | What | Written by |
| --- | --- | --- |
| `STATUS.md` | What each machine is running now, rates, and what is free | The operator, at each check |
| `EXPERIMENTS.md` | The queue: id, priority, who asked, machines and hours, state, result | The operator; others ask through a message |
| `messages/` | One file per message, never edited afterwards | Anyone |

Priorities are `high`, `medium` and `low`. High work is not interrupted for anything lower. Medium
and low work shares what high work leaves free, medium first. An entry also says where its priority
came from (Max, the director, or the operator).

## Sending a message

One file per message, so two writers never edit the same file:

    git clone --depth 1 --branch fleet/azure https://github.com/maxschireson/Single-Dummy-Bridge fleet
    cd fleet
    # write messages/<UTC time, e.g. 20261112T0315Z>-<from>.md
    git add messages && git commit -m "fleet: message from <from>" && git push origin fleet/azure
    # if the push is refused because the branch moved:
    git pull --rebase origin fleet/azure && git push origin fleet/azure

Start a message with three lines, then say what you need in plain words:

    From: gen8 (or operator, or Max)
    About: an experiment id from EXPERIMENTS.md, "allocation", or "new"
    Wants: one sentence

For a new experiment, say what to run (branch and commit, command or plan file), how many machines
for how long, the priority you propose and why, and what result you want back and where.

## What to expect

The operator reads this branch whenever it checks the machines: about every 20 minutes while a
check is scheduled, and whenever Max writes to it. It answers with a message, updates the two
files, and reports results in `EXPERIMENTS.md` with a link to the data. It does not watch the
branch between checks, so a message can wait up to a check interval, and longer if no check is
scheduled. `STATUS.md` says when the last check was and when the next is due.

## Limits

- The machines reach GitHub and the open internet. The operator reaches the machines only through
  GitHub (the boxctl agent, `docs/boxctl.md` on `feature/boxctl-20261112`), about a minute a command.
- No BEN server is installed on any of them.
- Adding or resizing machines costs money and needs Max's confirmation of a config recap first.
- Results are public: this repository is public.
