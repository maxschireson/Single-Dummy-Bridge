# boxctl: run commands on a box through GitHub

boxctl lets people and Claude sessions operate a collector machine using only
access to this repository. Claude's cloud sessions can push and fetch GitHub
branches but cannot open SSH connections or reach cloud APIs, so the box pulls its
work from GitHub instead of being dialled into.

Files: [`ops/boxctl/agent.py`](../ops/boxctl/agent.py) (runs on the box),
[`ops/boxctl/install.sh`](../ops/boxctl/install.sh) (one-time setup on the box),
[`ops/boxctl/client.py`](../ops/boxctl/client.py) (used from a session or laptop),
[`tests/test_boxctl.py`](../tests/test_boxctl.py).

## How it works

- The agent polls branch `box/<box>/control` every 30 seconds for files
  `commands/<id>.sh`. Each new command runs once, in id order, with `bash -l` as
  the agent's user, from that user's home directory. Ids start with a UTC timestamp,
  so id order is queue order.
- The default timeout is 15 minutes; a first-line `# boxctl: timeout=<seconds>`
  raises it to at most 6 hours. On timeout the command's process group is terminated.
- After each command, and at least every 5 minutes, the agent force-pushes a
  one-commit snapshot to `box/<box>/status`:
  - `heartbeat.json`: time, load, CPUs and model, memory, disk, the top process
    names, the running and pending command ids, the last fetch outcome.
  - `results/<id>.json` for the latest 300 commands: exit code, duration, whether it
    timed out, and the last 16 KB of combined output. Full logs stay on the box in
    `~/.boxctl/logs/`.
- A command that was running when the agent stopped is reported as `interrupted`
  and is never re-run. No id runs twice.

## Install on a box (once, over SSH)

Requirements: Ubuntu or Debian with systemd, a login user with passwordless sudo
(the installer checks), and outbound SSH to github.com.

```bash
curl -fsSL https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/<commit>/ops/boxctl/install.sh -o boxctl-install.sh
bash boxctl-install.sh <commit> <box-name>
```

The installer downloads `agent.py` from the same commit, creates an SSH key used
only for GitHub (`~/.ssh/boxctl_github`), installs the `boxctl` systemd service and
prints the public key. Add that key under the repository's Settings → Deploy keys
with **Allow write access**. The agent retries every 30 seconds until the key works,
then the heartbeat appears on `box/<box-name>/status`.

If outbound port 22 is blocked, run the installer with
`BOXCTL_REPO_URL=ssh://git@ssh.github.com:443/maxschireson/Single-Dummy-Bridge.git`.
Re-running the installer with a newer commit updates the agent and keeps the key,
configuration and command history. On the box, `journalctl -u boxctl -f` shows
what the agent is doing.

## Use from a session

```bash
python3 ops/boxctl/client.py boxes                    # boxes with a status branch
python3 ops/boxctl/client.py status <box>             # heartbeat and recent results
python3 ops/boxctl/client.py run <box> --cmd 'nproc; free -g'
python3 ops/boxctl/client.py send <box> --file job.sh --slug gen7-setup --timeout 3600
python3 ops/boxctl/client.py wait <box> <id>          # exit status 2 if no result yet
```

The client keeps its git state in `~/.cache/boxctl`, so it never touches a source
checkout. Expect a quick command's result within about a minute: up to 30 seconds
for the agent to see it, then its run time, then a push and a fetch.

## Long-running jobs

A command blocks the queue while it runs, so start collectors and other long jobs
as their own systemd units and return. They survive agent restarts and log to the
journal:

```bash
sudo systemd-run --unit=<name> --uid="$USER" --working-directory="$HOME/<dir>" \
  --property=Restart=on-failure -- <command> <args>
systemctl status <name>; journalctl -u <name> -n 50     # from a later command
```

The agent's own unit uses `KillMode=process`, so restarting the agent also leaves
`nohup` jobs alone, but a named unit is easier to inspect and stop. The
[operations rules](operations.md) apply to a box like any other host: one
publication checkout per collector, frozen runs not updated in place, and a stale
heartbeat is a reason to look, not to restart someone else's run.

## Security and visibility

- Anyone who can push to this repository can run commands on the box as the
  agent's user, who has sudo. That means the owner and any session or tool holding
  his GitHub credentials. Pull requests from forks cannot write to `box/*` branches.
- The status branch is as public as the repository. Commands must not print
  secrets, tokens or keys. The heartbeat lists process names, not command lines.
- A deploy key with write access can push to every branch, not only `box/*`. A
  ruleset protecting `main` limits what a compromised box could do.
- `box/*` branches are channels, like feed branches: never merge them into source.
  The control branch keeps its history as a record of every queued command; the
  status branch is replaced on each push.
- To remove the agent: `sudo systemctl disable --now boxctl && rm -rf ~/.boxctl`
  on the box, then delete the deploy key on GitHub.

## Tested scope

`tests/test_boxctl.py` runs the agent and client against a local bare repository:
queue order, run-once across restarts, timeout termination, interrupted commands not
re-run, a heartbeat with no control branch, and a live agent stopped with SIGTERM.
Not covered by those tests: `install.sh` on a real machine, the systemd unit, SSH to
GitHub with the deploy key, and Python versions other than the one running the tests
(the code is written for Python 3.8 or later).
