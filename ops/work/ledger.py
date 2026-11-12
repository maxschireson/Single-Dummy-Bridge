#!/usr/bin/env python3
"""work ledger: tasks, inboxes and leases for the agents of this project, kept on a git branch.

Every agent (a Claude session, a person, a script) names itself with --as NAME or $WORK_AGENT.
State lives on branch $WORK_BRANCH (default work/ledger) of $WORK_REPO (default the project's
GitHub repository). Each change is one commit made on the current tip and pushed without force;
if someone else pushed first, the change is re-read and re-applied, so two agents can never both
check out the same task or hold the same lease. Protocol: docs/work-ledger.md.

  ledger.py init                                    create the branch (once)
  ledger.py hello --role TEXT [--session URL]       register yourself, or refresh last_seen
  ledger.py status                                  summary; the branch's STATUS.md is the same view
  ledger.py watch [--all]                           what changed since you last looked, and your unread mail

  ledger.py add TITLE --kind K [--for AGENT] [--priority p1] [--depends T001,T002]
                [--spec TEXT | --spec-file PATH] [--effort HOURS] [--boxes N --box-hours H]
  ledger.py tasks [--state S] [--for AGENT] [--mine]
  ledger.py next [--for AGENT]                      open tasks you could check out now, best first
  ledger.py show ID [--json]
  ledger.py claim ID [--hours 4] [--force] [--takeover]     check out
  ledger.py renew ID [--hours 4]
  ledger.py release ID [--note TEXT]                check back in, unfinished
  ledger.py review ID [--note TEXT] [--output ...]  check in for review; the task's author is told
  ledger.py done ID --result TEXT [--output KIND=REF ...]
  ledger.py fail ID --result TEXT [--output ...]
  ledger.py block ID --note TEXT                    ledger.py reopen ID | cancel ID [--note]
  ledger.py note ID TEXT                            ledger.py edit ID [--priority/--for/--title/--depends/--spec]

  ledger.py send TO SUBJECT (--body TEXT | --file PATH) [--task ID] [--reply-to MSGID]   TO may be "all"
  ledger.py inbox [--all] [--agent NAME]            ledger.py read MSGID   (prints it and marks it read)

  ledger.py lease RESOURCE --hours H --purpose TEXT [--task ID] [--takeover]
  ledger.py unlease RESOURCE                        ledger.py leases
  ledger.py dispatch ID BOX (--cmd TEXT | --file PATH) [--slug S] [--timeout SEC]
                                                    queue a boxctl command for a task, if you hold box:BOX

  ledger.py fleet                                   read every box's heartbeat and the board's allocation table into
                                                    fleet.json, shown in STATUS.md (read-only for the boxes and the board)
  ledger.py export                                  the whole ledger as JSON, for other tools

$WORK_TRAILERS, if set, is appended to each commit message (for session attribution).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_REPO = "https://github.com/maxschireson/single-dummy-bridge"
DEFAULT_BRANCH = "work/ledger"
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
TASK_RE = re.compile(r"^T[0-9]{3,6}$")
RESOURCE_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}(:[A-Za-z0-9._-]{1,64})?$")
STATES = ("open", "claimed", "review", "blocked", "done", "failed", "cancelled")
FINAL = ("done", "failed", "cancelled")
KINDS = ("design", "code", "experiment", "research", "review", "ops", "docs")
PRIORITIES = ("p0", "p1", "p2", "p3")
BROADCAST = "all"

README = """# Work ledger

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
| `fleet.json` | Last `ledger.py fleet` reading: each box's heartbeat and the board's allocation table |
"""


class Conflict(Exception):
    """A precondition failed on the current tip: reported to the caller, never retried."""


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def short(t: str | None) -> str:
    return "" if not t else t[5:16].replace("T", " ")


def slugify(text: str, n: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n].strip("-") or "msg"


# ---------------------------------------------------------------- git storage

class Store:
    """One branch of one remote, kept in a private bare cache so no checkout is touched."""

    def __init__(self, url: str, branch: str):
        self.url, self.branch = url, branch
        self.ref = f"refs/heads/{branch}"
        self.local = f"refs/remotes/origin/{branch}"
        cache = Path(os.environ.get("WORK_CACHE", "~/.cache/workledger")).expanduser()
        self.cache = cache
        self.git_dir = cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".git")
        if not (self.git_dir / "HEAD").exists():
            cache.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init", "--bare", "-q", str(self.git_dir)], check=True)
        self.git("config", "remote.origin.url", url)
        self.before_push = None  # test hook: called with the new commit before it is pushed

    def git(self, *args: str, input: bytes | None = None, check: bool = True, env: dict | None = None,
            timeout: float = 300) -> subprocess.CompletedProcess:
        e = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        e.update(env or {})
        r = subprocess.run(["git", "--git-dir", str(self.git_dir), *args], input=input,
                           capture_output=True, timeout=timeout, env=e)
        if check and r.returncode != 0:
            raise SystemExit(f"git {args[0]} failed: {r.stderr.decode(errors='replace').strip()}")
        return r

    def out(self, *args: str, **kw) -> str:
        return self.git(*args, **kw).stdout.decode().strip()

    def fetch(self) -> str | None:
        r = self.git("fetch", "--quiet", "--no-tags", "--depth=1", "origin", f"+{self.ref}:{self.local}", check=False)
        if r.returncode == 0:
            return self.out("rev-parse", self.local)
        err = r.stderr.decode(errors="replace")
        if "couldn't find remote ref" in err or "could not find remote ref" in err:
            self.git("update-ref", "-d", self.local, check=False)
            return None
        raise SystemExit(f"git fetch {self.branch} failed: {err.strip()}")

    def read(self, tip: str | None) -> dict[str, bytes]:
        if not tip:
            return {}
        listing = self.git("ls-tree", "-r", "-z", tip).stdout.decode().split("\0")
        entries = [(line.split("\t", 1)[1], line.split()[2]) for line in listing if line]
        if not entries:
            return {}
        batch = self.git("cat-file", "--batch", input=("\n".join(sha for _, sha in entries) + "\n").encode()).stdout
        files, pos = {}, 0
        for path, sha in entries:
            nl = batch.index(b"\n", pos)
            size = int(batch[pos:nl].split()[2])
            files[path] = batch[nl + 1:nl + 1 + size]
            pos = nl + 1 + size + 1
        return files

    def commit(self, tip: str | None, changes: dict[str, bytes | None], message: str, author: str) -> str:
        index = self.git_dir / f"index-{os.getpid()}"
        env = {"GIT_INDEX_FILE": str(index), "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": "work-ledger@invalid",
               "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": "work-ledger@invalid"}
        try:
            if tip:
                self.git("read-tree", tip, env=env)
            else:
                self.git("read-tree", "--empty", env=env)
            lines = []
            for path, data in changes.items():
                if data is None:
                    lines.append(f"0 {'0' * 40}\t{path}")  # mode 0 removes the entry; works without a work tree
                else:
                    sha = self.out("hash-object", "-w", "--stdin", input=data)
                    lines.append(f"100644 {sha}\t{path}")
            if lines:
                self.git("update-index", "--add", "--index-info", input=("\n".join(lines) + "\n").encode(), env=env)
            tree = self.out("write-tree", env=env)
        finally:
            index.unlink(missing_ok=True)
        parents = ["-p", tip] if tip else []
        return self.out("commit-tree", tree, *parents, "-F", "-", input=message.encode(), env=env)

    def push(self, sha: str) -> bool:
        if self.before_push:
            self.before_push(sha)
        r = self.git("push", "--quiet", "origin", f"{sha}:{self.ref}", check=False)
        if r.returncode == 0:
            self.git("update-ref", self.local, sha, check=False)
            return True
        err = r.stderr.decode(errors="replace")
        if any(s in err for s in ("rejected", "fetch first", "non-fast-forward", "stale info", "cannot lock ref")):
            return False
        raise SystemExit(f"git push to {self.branch} failed: {err.strip()}")


# ---------------------------------------------------------------- ledger state

def parse_message(data: bytes) -> dict:
    text = data.decode()
    head, body = {}, text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            for line in text[4:end].splitlines():
                if ": " in line or line.endswith(":"):
                    k, _, v = line.partition(":")
                    head[k.strip()] = v.strip()
            body = text[end + 5:]
    head["read_by"] = [x for x in re.split(r"[ ,]+", head.get("read_by", "")) if x]
    head["body"] = body.strip("\n")
    return head


def format_message(m: dict) -> bytes:
    keys = ("id", "from", "to", "subject", "task", "reply_to", "sent")
    head = "".join(f"{k}: {m[k]}\n" for k in keys if m.get(k))
    head += f"read_by: {', '.join(m.get('read_by', []))}\n"
    return f"---\n{head}---\n\n{m['body'].rstrip()}\n".encode()


class State:
    def __init__(self, files: dict[str, bytes], agent: str, at: datetime):
        self.files, self.agent, self.at = files, agent, at
        self.changes: dict[str, bytes | None] = {}
        self.events: list[dict] = []

    def get(self, path: str) -> bytes | None:
        return self.changes[path] if path in self.changes else self.files.get(path)

    def paths(self, prefix: str) -> list[str]:
        ps = {p for p in self.files if p.startswith(prefix)}
        for p, d in self.changes.items():
            if p.startswith(prefix):
                (ps.add if d is not None else ps.discard)(p)
        return sorted(ps)

    def load(self, path: str) -> dict | None:
        d = self.get(path)
        return json.loads(d) if d is not None else None

    def save(self, path: str, obj: dict) -> None:
        self.changes[path] = (json.dumps(obj, indent=1, sort_keys=False) + "\n").encode()

    def put(self, path: str, data: bytes | None) -> None:
        self.changes[path] = data

    # collections
    def agents(self) -> dict[str, dict]:
        return {p[7:-5]: self.load(p) for p in self.paths("agents/") if p.endswith(".json")}

    def tasks(self) -> dict[str, dict]:
        return {p[6:-5]: self.load(p) for p in self.paths("tasks/") if p.endswith(".json")}

    def leases(self) -> dict[str, dict]:
        return {v["resource"]: v for v in (self.load(p) for p in self.paths("leases/") if p.endswith(".json"))}

    def messages(self, box: str | None = None) -> list[tuple[str, dict]]:
        prefix = f"inbox/{box}/" if box else "inbox/"
        return [(p, parse_message(self.get(p))) for p in self.paths(prefix) if p.endswith(".md")]

    def task(self, tid: str) -> dict:
        t = self.load(f"tasks/{tid}.json")
        if not t:
            raise Conflict(f"no task {tid}")
        return t

    def save_task(self, t: dict) -> None:
        self.save(f"tasks/{t['id']}.json", t)

    def event(self, op: str, target: str, note: str = "", **extra) -> dict:
        e = dict(at=iso(self.at), by=self.agent, op=op, target=target)
        if note:
            e["note"] = note
        e.update({k: v for k, v in extra.items() if v not in (None, "", [])})
        self.events.append(e)
        return e

    def task_event(self, t: dict, op: str, note: str = "", **extra) -> None:
        e = self.event(op, t["id"], note, **extra)
        t.setdefault("events", []).append({k: v for k, v in e.items() if k != "target"})

    def send(self, to: str, subject: str, body: str, task: str | None = None, reply_to: str | None = None) -> str:
        mid = f"{self.at:%Y%m%dT%H%M%SZ}-{self.agent}-{slugify(subject, 30)}"
        n, base = 1, mid
        while self.get(f"inbox/{to}/{mid}.md") is not None:
            n += 1
            mid = f"{base}-{n}"
        m = dict(id=mid, **{"from": self.agent}, to=to, subject=subject, task=task, reply_to=reply_to,
                 sent=iso(self.at), read_by=[], body=body)
        self.put(f"inbox/{to}/{mid}.md", format_message(m))
        self.event("send", f"{to}/{mid}", subject, task=task)
        return mid

    def flush_log(self) -> None:
        if not self.events:
            return
        path = f"log/{self.at:%Y-%m-%d}.jsonl"
        old = self.get(path) or b""
        self.put(path, old + b"".join((json.dumps(e) + "\n").encode() for e in self.events))


def claim_live(t: dict, at: datetime) -> bool:
    c = t.get("claim")
    return bool(c) and parse_time(c["expires"]) > at


def lease_live(l: dict, at: datetime) -> bool:
    return parse_time(l["expires"]) > at


def display_state(t: dict, at: datetime) -> str:
    s = t["state"]
    if s in ("claimed", "review") and t.get("claim") and not claim_live(t, at):
        return s + " (lapsed)"
    return s


def deps_pending(st: State, t: dict) -> list[str]:
    out = []
    for d in t.get("depends_on", []):
        dt = st.load(f"tasks/{d}.json")
        if not dt or dt["state"] != "done":
            out.append(d)
    return out


# ---------------------------------------------------------------- rendering

def render_status(st: State) -> bytes:
    at = st.at
    agents, tasks, leases = st.agents(), st.tasks(), st.leases()
    msgs = st.messages()
    L = [f"# Work ledger status", "",
         f"Generated {iso(at)} after a change by `{st.agent}`. Times are UTC. "
         f"Written by `ops/work/ledger.py`; do not edit by hand. Protocol: `docs/work-ledger.md`.", ""]

    L += ["## Agents", "", "| Agent | Role | Last seen | Unread | Session |", "| --- | --- | --- | ---: | --- |"]
    for name, a in sorted(agents.items()):
        unread = sum(1 for p, m in msgs if (p.startswith(f"inbox/{name}/") or p.startswith(f"inbox/{BROADCAST}/"))
                     and name not in m["read_by"] and m.get("from") != name)
        sess = a.get("session") or ""
        sess = f"[link]({sess})" if sess.startswith("http") else sess
        L.append(f"| {name} | {a.get('role', '')} | {short(a.get('last_seen'))} | {unread} | {sess} |")
    L.append("")

    order = {"claimed": 0, "review": 1, "blocked": 2, "open": 3}
    active = [t for t in tasks.values() if t["state"] not in FINAL]
    active.sort(key=lambda t: (order.get(t["state"], 9), t.get("priority", "p2"), t["id"]))
    L += ["## Tasks in progress and open", ""]
    if active:
        L += ["| Id | Pri | State | For | Held by, until | Needs | Title |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for t in active:
            c = t.get("claim") or {}
            held = f"{c['by']}, {short(c['expires'])}" if c else ""
            needs = []
            pend = deps_pending(st, t)
            if pend:
                needs.append("after " + ", ".join(pend))
            if (t.get("needs") or {}).get("boxes"):
                needs.append(f"{t['needs']['boxes']} box" + (f" x {t['needs'].get('box_hours')} h" if t['needs'].get('box_hours') else ""))
            L.append(f"| {t['id']} | {t.get('priority', '')} | {display_state(t, at)} | {t.get('for') or 'any'} | {held} | "
                     f"{'; '.join(needs)} | {t['title']} |")
    else:
        L.append("None.")
    L.append("")

    L += ["## Leases", ""]
    if leases:
        L += ["| Resource | Holder | Until | Task | Purpose |", "| --- | --- | --- | --- | --- |"]
        for r, l in sorted(leases.items()):
            until = short(l["expires"]) + ("" if lease_live(l, at) else " (lapsed)")
            L.append(f"| {r} | {l['holder']} | {until} | {l.get('task') or ''} | {l.get('purpose', '')} |")
    else:
        L.append("None.")
    L.append("")

    def pending(p: str, m: dict) -> bool:
        if p.startswith(f"inbox/{BROADCAST}/"):  # shown for a day; each agent's own count is in the table above
            return at - parse_time(m["sent"]) < timedelta(days=1)
        return m.get("to") not in m["read_by"]
    L += render_fleet(st.load("fleet.json"), leases, at)
    unread_all = [(p, m) for p, m in msgs if pending(p, m)]
    L += ["## Unread messages", ""]
    if unread_all:
        L += ["| To | From | Sent | Subject | Task |", "| --- | --- | --- | --- | --- |"]
        for p, m in sorted(unread_all, key=lambda x: x[1].get("sent", ""))[-30:]:
            L.append(f"| {m.get('to')} | {m.get('from')} | {short(m.get('sent'))} | [{m.get('subject', '')}]({p}) | {m.get('task') or ''} |")
    else:
        L.append("None.")
    L.append("")

    done = [t for t in tasks.values() if t["state"] in FINAL]
    done.sort(key=lambda t: t.get("closed", ""), reverse=True)
    L += ["## Recently closed", ""]
    if done:
        L += ["| Id | State | By | Closed | Title | Result |", "| --- | --- | --- | --- | --- | --- |"]
        for t in done[:20]:
            res = (t.get("result") or "").replace("\n", " ").replace("|", "/")
            L.append(f"| {t['id']} | {t['state']} | {t.get('closed_by', '')} | {short(t.get('closed'))} | {t['title']} | {res[:160]} |")
    else:
        L.append("None.")
    L.append("")
    return "\n".join(L).encode()


# ---------------------------------------------------------------- the ledger

class Ledger:
    def __init__(self, url: str | None = None, branch: str | None = None, agent: str | None = None):
        self.store = Store(url or os.environ.get("WORK_REPO", DEFAULT_REPO), branch or os.environ.get("WORK_BRANCH", DEFAULT_BRANCH))
        self.agent = agent or os.environ.get("WORK_AGENT")
        self.clock = now  # tests replace this

    def need_agent(self) -> str:
        if not self.agent or not NAME_RE.match(self.agent) or self.agent == BROADCAST:
            raise SystemExit("say who you are: --as NAME or WORK_AGENT=NAME (lower case, letters, digits, dashes; not 'all')")
        return self.agent

    def snapshot(self) -> State:
        tip = self.store.fetch()
        return State(self.store.read(tip), self.agent or "-", self.clock())

    def mutate(self, summary: str, fn, allow_create: bool = False):
        agent = self.need_agent()
        for attempt in range(10):
            tip = self.store.fetch()
            if tip is None and not allow_create:
                raise SystemExit(f"branch {self.store.branch} does not exist yet; run `ledger.py init` once")
            st = State(self.store.read(tip), agent, self.clock())
            result = fn(st)
            if not st.changes and not st.events:
                return result
            st.flush_log()
            st.put("STATUS.md", render_status(st))
            msg = f"{agent}: {summary}\n"
            if os.environ.get("WORK_TRAILERS"):
                msg += "\n" + os.environ["WORK_TRAILERS"].strip() + "\n"
            sha = self.store.commit(tip, st.changes, msg, f"{agent} (work ledger)")
            if self.store.push(sha):
                return result
            time.sleep(min(0.5 * (attempt + 1), 4))
        raise SystemExit("the ledger branch kept moving under this change; try again")

    # setup and presence
    def init(self):
        def fn(st: State):
            if st.files:
                raise Conflict(f"{self.store.branch} already exists")
            st.put("README.md", README.encode())
            st.event("init", self.store.branch)
        return self.mutate("open the work ledger", fn, allow_create=True)

    def hello(self, role: str | None, session: str | None, model: str | None, notes: str | None):
        def fn(st: State):
            path = f"agents/{st.agent}.json"
            a = st.load(path)
            new = a is None
            a = a or dict(name=st.agent, registered=iso(st.at))
            for k, v in (("role", role), ("session", session), ("model", model), ("notes", notes)):
                if v is not None:
                    a[k] = v
            a["last_seen"] = iso(st.at)
            st.save(path, a)
            if new:
                st.event("hello", st.agent, a.get("role", ""))
            return a
        return self.mutate(f"hello from {self.agent}", fn)

    def touch(self, st: State, min_gap_minutes: int = 15) -> None:
        a = st.load(f"agents/{st.agent}.json")
        if a and (not a.get("last_seen") or st.at - parse_time(a["last_seen"]) >= timedelta(minutes=min_gap_minutes)):
            a["last_seen"] = iso(st.at)
            st.save(f"agents/{st.agent}.json", a)

    # tasks
    def add(self, title: str, kind: str, for_: str | None, priority: str, depends: list[str], spec: str,
            effort: float | None, boxes: int | None, box_hours: float | None, parent: str | None = None):
        if kind not in KINDS:
            raise SystemExit(f"--kind must be one of {', '.join(KINDS)}")
        if priority not in PRIORITIES:
            raise SystemExit(f"--priority must be one of {', '.join(PRIORITIES)}")
        if for_ and for_ != "any" and not NAME_RE.match(for_):
            raise SystemExit(f"invalid --for {for_!r}")

        def fn(st: State):
            tasks = st.tasks()
            for d in depends + ([parent] if parent else []):
                if d not in tasks:
                    raise Conflict(f"no task {d}")
            n = max([int(k[1:]) for k in tasks] + [0]) + 1
            tid = f"T{n:03d}"
            t = dict(id=tid, title=title, kind=kind, priority=priority, state="open",
                     **{"for": None if for_ in (None, "any") else for_},
                     depends_on=depends, parent=parent, spec=spec, effort_hours=effort,
                     needs={k: v for k, v in (("boxes", boxes), ("box_hours", box_hours)) if v},
                     created=iso(st.at), created_by=st.agent, claim=None, outputs=[], result=None, events=[])
            st.task_event(t, "add", title)
            st.save_task(t)
            if t["for"] and t["for"] != st.agent:
                st.send(t["for"], f"New task {tid}: {title}", f"{st.agent} added task {tid} for you "
                        f"({kind}, {priority}).\n\n{spec}".rstrip(), task=tid)
            return tid
        return self.mutate(f"add task: {title}", fn)

    def claim(self, tid: str, hours: float, force: bool = False, takeover: bool = False):
        def fn(st: State):
            t = st.task(tid)
            c = t.get("claim")
            if t["state"] in FINAL:
                raise Conflict(f"{tid} is {t['state']}")
            if c and c["by"] == st.agent and t["state"] in ("claimed", "review"):
                c["expires"] = iso(st.at + timedelta(hours=hours))
                st.task_event(t, "renew", until=c["expires"])
                st.save_task(t)
                return t
            if t["state"] in ("claimed", "review") and c:
                if claim_live(t, st.at):
                    raise Conflict(f"{tid} is checked out by {c['by']} until {c['expires']}")
                if not takeover:
                    raise Conflict(f"{tid}'s claim by {c['by']} lapsed at {c['expires']}; ask them, or claim with --takeover")
                st.send(c["by"], f"{st.agent} took over {tid}", f"Your claim on {tid} ({t['title']}) lapsed at "
                        f"{c['expires']}; {st.agent} has checked it out. Say so in {st.agent}'s inbox if that is wrong.", task=tid)
            if t["state"] == "blocked" and not force:
                raise Conflict(f"{tid} is blocked; reopen it first or claim with --force")
            if t.get("for") and t["for"] != st.agent and not force:
                raise Conflict(f"{tid} is for {t['for']}; claim with --force if they agreed")
            pend = deps_pending(st, t)
            if pend and not force:
                raise Conflict(f"{tid} waits for {', '.join(pend)}; claim with --force to start anyway")
            sess = (st.load(f"agents/{st.agent}.json") or {}).get("session")
            t["claim"] = dict(by=st.agent, session=sess, at=iso(st.at), expires=iso(st.at + timedelta(hours=hours)))
            t["state"] = "claimed"
            st.task_event(t, "claim", until=t["claim"]["expires"], takeover=c["by"] if (takeover and c) else None)
            st.save_task(t)
            self.touch(st)
            return t
        return self.mutate(f"check out {tid}", fn)

    def _holder_op(self, tid: str, op: str, apply, allow_author: bool = False, allow_any: bool = False):
        def fn(st: State):
            t = st.task(tid)
            c = t.get("claim") or {}
            mine = c.get("by") == st.agent
            author = t.get("created_by") == st.agent
            if not (mine or allow_any or (allow_author and author)):
                who = f"checked out by {c['by']}" if c else "not checked out"
                raise Conflict(f"{tid} is {who}; only its holder" + (" or its author" if allow_author else "") + f" can {op} it")
            out = apply(st, t)
            st.save_task(t)
            self.touch(st)
            return out
        return self.mutate(f"{op} {tid}", fn)

    def renew(self, tid: str, hours: float):
        def apply(st, t):
            if t["state"] not in ("claimed", "review"):
                raise Conflict(f"{tid} is {t['state']}")
            t["claim"]["expires"] = iso(st.at + timedelta(hours=hours))
            st.task_event(t, "renew", until=t["claim"]["expires"])
            return t
        return self._holder_op(tid, "renew", apply)

    def release(self, tid: str, note: str):
        def apply(st, t):
            t["state"], t["claim"] = "open", None
            st.task_event(t, "release", note)
            return t
        return self._holder_op(tid, "release", apply)

    def review(self, tid: str, note: str, outputs: list[dict]):
        def apply(st, t):
            if t["state"] != "claimed":
                raise Conflict(f"{tid} is {t['state']}")
            t["state"] = "review"
            t["outputs"] += outputs
            st.task_event(t, "review", note, outputs=outputs)
            if t["created_by"] != st.agent:
                lines = [f"{st.agent} checked {tid} ({t['title']}) in for your review."]
                if note:
                    lines += ["", note]
                if outputs:
                    lines += [""] + [f"- {o['kind']}: {o['ref']}" for o in outputs]
                lines += ["", f"Accept: `ledger.py done {tid} --result ...`; send it back: `ledger.py reopen {tid} --note ...`"]
                st.send(t["created_by"], f"Review {tid}: {t['title']}", "\n".join(lines), task=tid)
            return t
        return self._holder_op(tid, "check in for review", apply)

    def close(self, tid: str, state: str, result: str, outputs: list[dict]):
        def apply(st, t):
            if t["state"] in FINAL:
                raise Conflict(f"{tid} is already {t['state']}")
            t["state"], t["result"] = state, result
            t["outputs"] += outputs
            t["closed"], t["closed_by"] = iso(st.at), st.agent
            holder = (t.get("claim") or {}).get("by")
            t["claim"] = None
            st.task_event(t, state, result, outputs=outputs)
            for who in {t["created_by"], holder} - {st.agent, None}:
                st.send(who, f"{tid} {state}: {t['title']}", f"{st.agent} closed {tid} as {state}.\n\n{result}", task=tid)
            return t
        return self._holder_op(tid, state, apply, allow_author=True)

    def block(self, tid: str, note: str):
        def apply(st, t):
            if t["state"] in FINAL:
                raise Conflict(f"{tid} is {t['state']}")
            t["state"], t["claim"] = "blocked", None
            st.task_event(t, "block", note)
            if t["created_by"] != st.agent:
                st.send(t["created_by"], f"{tid} blocked: {t['title']}", f"{st.agent}: {note}", task=tid)
            return t
        return self._holder_op(tid, "block", apply, allow_author=True)

    def reopen(self, tid: str, note: str):
        def apply(st, t):
            holder = (t.get("claim") or {}).get("by")
            t["state"], t["claim"] = "open", None
            t.pop("closed", None); t.pop("closed_by", None)
            st.task_event(t, "reopen", note)
            if holder and holder != st.agent:
                st.send(holder, f"{tid} reopened: {t['title']}", f"{st.agent}: {note}", task=tid)
            return t
        return self._holder_op(tid, "reopen", apply, allow_any=True)

    def cancel(self, tid: str, note: str):
        return self.close(tid, "cancelled", note or "cancelled", [])

    def note(self, tid: str, text: str):
        def apply(st, t):
            st.task_event(t, "note", text)
            return t
        return self._holder_op(tid, "note", apply, allow_any=True)

    def edit(self, tid: str, **fields):
        def apply(st, t):
            changed = {}
            for k, v in fields.items():
                if v is None:
                    continue
                if k == "depends_on":
                    for d in v:
                        if not st.load(f"tasks/{d}.json"):
                            raise Conflict(f"no task {d}")
                if k == "for":
                    v = None if v == "any" else v
                t[k] = v
                changed[k] = v
            st.task_event(t, "edit", ", ".join(f"{k}={v}" for k, v in changed.items()))
            return t
        return self._holder_op(tid, "edit", apply, allow_any=True)

    # messages
    def send(self, to: str, subject: str, body: str, task: str | None, reply_to: str | None):
        if to != BROADCAST and not NAME_RE.match(to):
            raise SystemExit(f"invalid recipient {to!r}")

        def fn(st: State):
            if task:
                st.task(task)
            self.touch(st)
            return st.send(to, subject, body, task, reply_to)
        return self.mutate(f"message to {to}: {subject}", fn)

    def mark_read(self, mid: str):
        def fn(st: State):
            hits = [p for p in st.paths("inbox/") if p.endswith(f"/{mid}.md")]
            if not hits:
                raise Conflict(f"no message {mid}")
            m = parse_message(st.get(hits[0]))
            if st.agent not in m["read_by"]:
                m["read_by"].append(st.agent)
                st.put(hits[0], format_message(m))
                self.touch(st)
            return m
        return self.mutate(f"read {mid}", fn)

    # leases
    def lease(self, resource: str, hours: float, purpose: str, task: str | None, takeover: bool):
        if not RESOURCE_RE.match(resource):
            raise SystemExit(f"invalid resource {resource!r} (for example box:azure2)")

        def fn(st: State):
            path = f"leases/{resource.replace(':', '--')}.json"
            l = st.load(path)
            if l and l["holder"] != st.agent:
                if lease_live(l, st.at):
                    raise Conflict(f"{resource} is held by {l['holder']} until {l['expires']} ({l.get('purpose', '')})")
                if not takeover:
                    raise Conflict(f"{resource}'s lease by {l['holder']} lapsed at {l['expires']}; ask them, or lease with --takeover")
                st.send(l["holder"], f"{st.agent} took over {resource}", f"Your lease on {resource} lapsed at "
                        f"{l['expires']}; {st.agent} now holds it for: {purpose}")
            if task:
                st.task(task)
            new = dict(resource=resource, holder=st.agent, purpose=purpose, task=task,
                       since=(l["since"] if l and l["holder"] == st.agent else iso(st.at)),
                       expires=iso(st.at + timedelta(hours=hours)))
            st.save(path, new)
            st.event("lease", resource, purpose, until=new["expires"], task=task)
            self.touch(st)
            return new
        return self.mutate(f"lease {resource}", fn)

    def unlease(self, resource: str):
        def fn(st: State):
            path = f"leases/{resource.replace(':', '--')}.json"
            l = st.load(path)
            if not l:
                raise Conflict(f"nobody holds {resource}")
            if l["holder"] != st.agent:
                raise Conflict(f"{resource} is held by {l['holder']}")
            st.put(path, None)
            st.event("unlease", resource)
            return l
        return self.mutate(f"release {resource}", fn)

    def fleet(self):
        snap = collect_fleet(self.clock())

        def fn(st: State):
            st.save("fleet.json", snap)
        self.mutate("fleet snapshot", fn)
        return snap

    def dispatch(self, tid: str, box: str, script: bytes, slug: str | None, timeout: int | None, check_lease: bool = True):
        st = self.snapshot()
        t = st.task(tid)
        if (t.get("claim") or {}).get("by") != self.need_agent():
            raise Conflict(f"{tid} is not checked out by {self.agent}")
        l = st.leases().get(f"box:{box}")
        if check_lease and not (l and l["holder"] == self.agent and lease_live(l, st.at)):
            raise Conflict(f"{self.agent} does not hold box:{box}; lease it first, or pass --no-lease-check")
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "boxctl"))
        import client as boxctl  # ops/boxctl/client.py
        cid = boxctl.send(boxctl.Remote(os.environ.get("BOXCTL_REPO", boxctl.DEFAULT_REPO)), box, script, slug or tid.lower(), timeout)

        def fn(st2: State):
            t2 = st2.task(tid)
            t2["outputs"].append(dict(kind="boxctl", ref=f"{box}/{cid}"))
            st2.task_event(t2, "dispatch", f"{box}/{cid}")
            st2.save_task(t2)
        self.mutate(f"dispatch {tid} to {box}", fn)
        return cid


# ---------------------------------------------------------------- fleet view

def board_allocation(text: str) -> dict[str, str]:
    """The 'Now' column of the allocation table in BOARD.md (branch box/coordination), by box."""
    out, on = {}, False
    for line in text.splitlines():
        if line.startswith("## Allocation"):
            on = True
            continue
        if on and line.startswith("## "):
            break
        if on and line.startswith("| ") and not line.startswith("| Box") and not line.startswith("| ---"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            m = re.match(r"([a-z0-9-]+)", cells[0])
            if m and len(cells) > 1:
                out[m.group(1)] = cells[1]
    return out


def collect_fleet(at: datetime) -> dict:
    """Read every box's heartbeat from box/<box>/status, and the board's allocation table. Read-only."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "boxctl"))
    import client as boxctl  # ops/boxctl/client.py
    remote = boxctl.Remote(os.environ.get("BOXCTL_REPO", boxctl.DEFAULT_REPO))
    heads = remote.out("ls-remote", "--heads", "origin")
    boxes = sorted({m.group(1) for m in re.finditer(r"refs/heads/box/([a-z0-9-]+)/status$", heads, re.M)})
    alloc = {}
    if re.search(r"refs/heads/box/coordination$", heads, re.M):
        local = "refs/remotes/origin/box/coordination"
        if remote.fetch("refs/heads/box/coordination", local):
            alloc = board_allocation((remote.blob(f"{local}:BOARD.md") or b"").decode(errors="replace"))
    rows = []
    for box in boxes:
        row = dict(box=box, board_now=alloc.get(box))
        local = boxctl.fetch_status(remote, box)
        hb = json.loads(remote.blob(f"{local}:heartbeat.json") or b"{}") if local else {}
        if hb:
            mem = hb.get("memory_mb") or {}
            disk = (hb.get("disk") or {}).get("home") or {}
            row.update(host=hb.get("hostname"), heartbeat=hb.get("time"), cpus=hb.get("cpus"),
                       load=(hb.get("load") or [None])[0], mem_free_gb=round(mem.get("MemAvailable", 0) / 1024, 1),
                       mem_total_gb=round(mem.get("MemTotal", 0) / 1024, 1), disk_free_gb=disk.get("free_gb"),
                       running=hb.get("running"), pending=len(hb.get("pending") or []),
                       fetch=(hb.get("last_fetch") or {}).get("outcome"), uptime_h=round(hb.get("uptime_s", 0) / 3600, 1))
        rows.append(row)
    return dict(at=iso(at), boxes=rows)


def render_fleet(f: dict | None, leases: dict, at: datetime) -> list[str]:
    if not f:
        return []
    L = ["## Boxes", "",
         f"Heartbeats from `box/<box>/status` and the allocation table on `box/coordination`, read at "
         f"{short(f['at'])} by `ledger.py fleet`. Heartbeats are pushed at least every 5 minutes.", "",
         "| Box | Heartbeat | Load / CPUs | Free memory | Free disk | boxctl queue | Board says (allocation table) | Ledger lease |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    snap = parse_time(f["at"])
    for r in f["boxes"]:
        l = leases.get(f"box:{r['box']}")
        lease = f"{l['holder']} until {short(l['expires'])}" if l else ""
        board = (r.get("board_now") or "").replace("|", "/")
        board = board[:90] + ("..." if len(board) > 90 else "")
        if not r.get("heartbeat"):
            L.append(f"| {r['box']} | none | | | | | {board} | {lease} |")
            continue
        age = int((snap - parse_time(r["heartbeat"])).total_seconds() // 60)
        hb = f"{short(r['heartbeat'])}" + (f" (**{age} min old**)" if age > 12 else "")
        queue = ("running " + r["running"].split("-", 2)[-1] if r.get("running") else "idle") + (f", {r['pending']} waiting" if r.get("pending") else "")
        L.append(f"| {r['box']} | {hb} | {r.get('load')} / {r.get('cpus')} | {r.get('mem_free_gb')} of {r.get('mem_total_gb')} GB | "
                 f"{r.get('disk_free_gb')} GB | {queue} | {board} | {lease} |")
    L.append("")
    return L


# ---------------------------------------------------------------- command line

def seen_path(store: Store, agent: str) -> Path:
    return store.cache / f"{store.git_dir.stem}.{store.branch.replace('/', '_')}.{agent}.seen"


def print_task(t: dict, at: datetime, st: State) -> None:
    c = t.get("claim") or {}
    print(f"{t['id']}  {t['title']}")
    print(f"  {t['kind']}, {t.get('priority')}, {display_state(t, at)}, for {t.get('for') or 'any'}; "
          f"added {short(t['created'])} by {t['created_by']}")
    if c:
        print(f"  checked out by {c['by']} since {short(c['at'])}, until {short(c['expires'])}")
    if t.get("depends_on"):
        pend = deps_pending(st, t)
        print(f"  depends on {', '.join(t['depends_on'])}" + (f" (waiting for {', '.join(pend)})" if pend else " (all done)"))
    if t.get("needs"):
        print(f"  needs {json.dumps(t['needs'])}")
    if t.get("spec"):
        print("  spec:\n    " + t["spec"].replace("\n", "\n    "))
    for o in t.get("outputs", []):
        print(f"  output {o['kind']}: {o['ref']}")
    if t.get("result"):
        print(f"  result: {t['result']}")
    print("  events:")
    for e in t.get("events", []):
        rest = " ".join(f"{k}={v}" for k, v in e.items() if k not in ("at", "by", "op", "note"))
        print(f"    {short(e['at'])} {e['by']} {e['op']}" + (f": {e['note']}" if e.get("note") else "") + (f" [{rest}]" if rest else ""))


def parse_outputs(items: list[str] | None) -> list[dict]:
    out = []
    for it in items or []:
        kind, sep, ref = it.partition("=")
        if not sep or not kind or not ref:
            raise SystemExit(f"--output takes KIND=REF, for example branch=feature/x@abc1234 or report=reports/x.md; got {it!r}")
        out.append(dict(kind=kind, ref=ref))
    return out


def text_arg(text: str | None, path: str | None) -> str:
    if path:
        return (sys.stdin.read() if path == "-" else Path(path).read_text()).rstrip()
    return (text or "").rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as", dest="agent")
    ap.add_argument("--repo")
    ap.add_argument("--branch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p = sub.add_parser("hello"); p.add_argument("--role"); p.add_argument("--session"); p.add_argument("--model"); p.add_argument("--notes")
    sub.add_parser("status")
    p = sub.add_parser("watch"); p.add_argument("--all", action="store_true"); p.add_argument("--no-heartbeat", action="store_true")
    p = sub.add_parser("add"); p.add_argument("title"); p.add_argument("--kind", required=True); p.add_argument("--for", dest="for_")
    p.add_argument("--priority", default="p2"); p.add_argument("--depends", default=""); p.add_argument("--parent")
    p.add_argument("--spec"); p.add_argument("--spec-file"); p.add_argument("--effort", type=float)
    p.add_argument("--boxes", type=int); p.add_argument("--box-hours", type=float)
    p = sub.add_parser("tasks"); p.add_argument("--state"); p.add_argument("--for", dest="for_"); p.add_argument("--mine", action="store_true")
    p = sub.add_parser("next"); p.add_argument("--for", dest="for_"); p.add_argument("-n", type=int, default=8)
    p = sub.add_parser("show"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("claim"); p.add_argument("id"); p.add_argument("--hours", type=float, default=4)
    p.add_argument("--force", action="store_true"); p.add_argument("--takeover", action="store_true")
    p = sub.add_parser("renew"); p.add_argument("id"); p.add_argument("--hours", type=float, default=4)
    p = sub.add_parser("release"); p.add_argument("id"); p.add_argument("--note", default="")
    p = sub.add_parser("review"); p.add_argument("id"); p.add_argument("--note", default=""); p.add_argument("--output", action="append")
    for name in ("done", "fail"):
        p = sub.add_parser(name); p.add_argument("id"); p.add_argument("--result"); p.add_argument("--result-file"); p.add_argument("--output", action="append")
    p = sub.add_parser("block"); p.add_argument("id"); p.add_argument("--note", required=True)
    for name in ("reopen", "cancel"):
        p = sub.add_parser(name); p.add_argument("id"); p.add_argument("--note", default="")
    p = sub.add_parser("note"); p.add_argument("id"); p.add_argument("text")
    p = sub.add_parser("edit"); p.add_argument("id"); p.add_argument("--priority"); p.add_argument("--for", dest="for_")
    p.add_argument("--title"); p.add_argument("--depends"); p.add_argument("--spec"); p.add_argument("--spec-file")
    p = sub.add_parser("send"); p.add_argument("to"); p.add_argument("subject"); p.add_argument("--body"); p.add_argument("--file")
    p.add_argument("--task"); p.add_argument("--reply-to")
    p = sub.add_parser("inbox"); p.add_argument("--all", action="store_true"); p.add_argument("--agent", dest="who", help="read another agent's inbox")
    p = sub.add_parser("read"); p.add_argument("id")
    p = sub.add_parser("lease"); p.add_argument("resource"); p.add_argument("--hours", type=float, required=True)
    p.add_argument("--purpose", required=True); p.add_argument("--task"); p.add_argument("--takeover", action="store_true")
    p = sub.add_parser("unlease"); p.add_argument("resource")
    sub.add_parser("leases")
    p = sub.add_parser("dispatch"); p.add_argument("id"); p.add_argument("box"); p.add_argument("--cmd"); p.add_argument("--file")
    p.add_argument("--slug"); p.add_argument("--timeout", type=int); p.add_argument("--no-lease-check", action="store_true")
    sub.add_parser("fleet")
    sub.add_parser("export")
    a = ap.parse_args(argv)
    lg = Ledger(a.repo, a.branch, a.agent)

    try:
        return run(lg, a)
    except Conflict as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3


def run(lg: Ledger, a: argparse.Namespace) -> int:
    c = a.cmd
    if c == "init":
        lg.init(); print(f"opened {lg.store.branch}"); return 0
    if c == "hello":
        r = lg.hello(a.role, a.session, a.model, a.notes); print(json.dumps(r, indent=1)); return 0
    if c == "add":
        deps = [d for d in re.split(r"[ ,]+", a.depends) if d]
        tid = lg.add(a.title, a.kind, a.for_, a.priority, deps, text_arg(a.spec, a.spec_file), a.effort, a.boxes, a.box_hours, a.parent)
        print(tid); return 0
    if c == "claim":
        t = lg.claim(a.id, a.hours, a.force, a.takeover); print(f"{t['id']} checked out by {t['claim']['by']} until {t['claim']['expires']}"); return 0
    if c == "renew":
        t = lg.renew(a.id, a.hours); print(f"{t['id']} renewed until {t['claim']['expires']}"); return 0
    if c == "release":
        lg.release(a.id, a.note); print(f"{a.id} checked back in, open"); return 0
    if c == "review":
        lg.review(a.id, a.note, parse_outputs(a.output)); print(f"{a.id} in review"); return 0
    if c in ("done", "fail"):
        res = text_arg(a.result, a.result_file)
        if not res:
            raise SystemExit("--result or --result-file is required")
        lg.close(a.id, "done" if c == "done" else "failed", res, parse_outputs(a.output)); print(f"{a.id} {c}"); return 0
    if c == "block":
        lg.block(a.id, a.note); print(f"{a.id} blocked"); return 0
    if c == "reopen":
        lg.reopen(a.id, a.note); print(f"{a.id} open"); return 0
    if c == "cancel":
        lg.cancel(a.id, a.note); print(f"{a.id} cancelled"); return 0
    if c == "note":
        lg.note(a.id, a.text); print("noted"); return 0
    if c == "edit":
        spec = text_arg(a.spec, a.spec_file) if (a.spec or a.spec_file) else None
        deps = [d for d in re.split(r"[ ,]+", a.depends) if d] if a.depends is not None else None
        lg.edit(a.id, priority=a.priority, title=a.title, spec=spec, depends_on=deps, **{"for": a.for_}); print("edited"); return 0
    if c == "send":
        body = text_arg(a.body, a.file)
        if not body:
            raise SystemExit("--body or --file is required")
        print(lg.send(a.to, a.subject, body, a.task, a.reply_to)); return 0
    if c == "read":
        m = lg.mark_read(a.id)
        print(f"From {m.get('from')} to {m.get('to')}, {m.get('sent')}" + (f", task {m['task']}" if m.get("task") else "")
              + (f", reply to {m['reply_to']}" if m.get("reply_to") else ""))
        print(f"Subject: {m.get('subject')}\n\n{m['body']}"); return 0
    if c == "lease":
        l = lg.lease(a.resource, a.hours, a.purpose, a.task, a.takeover); print(f"{l['resource']} held by {l['holder']} until {l['expires']}"); return 0
    if c == "unlease":
        lg.unlease(a.resource); print(f"released {a.resource}"); return 0
    if c == "fleet":
        snap = lg.fleet()
        print("\n".join(render_fleet(snap, lg.snapshot().leases(), now())))
        return 0
    if c == "dispatch":
        script = Path(a.file).read_bytes() if a.file else (a.cmd or "").encode()
        if not script:
            raise SystemExit("--cmd or --file is required")
        print(lg.dispatch(a.id, a.box, script, a.slug, a.timeout, not a.no_lease_check)); return 0

    st = lg.snapshot()
    if not st.files:
        raise SystemExit(f"branch {lg.store.branch} does not exist yet; run `ledger.py init` once")
    if c == "status":
        sys.stdout.write(render_status(st).decode()); return 0
    if c == "export":
        print(json.dumps(dict(agents=st.agents(), tasks=st.tasks(), leases=st.leases(),
                              messages=[m for _, m in st.messages()]), indent=1)); return 0
    if c == "leases":
        for r, l in sorted(st.leases().items()):
            print(f"{r:24} {l['holder']:10} until {l['expires']}{'' if lease_live(l, st.at) else ' (lapsed)'}  {l.get('purpose', '')}")
        return 0
    if c == "show":
        t = st.task(a.id)
        print(json.dumps(t, indent=1)) if a.json else print_task(t, st.at, st); return 0
    if c in ("tasks", "next"):
        me = lg.agent
        ts = list(st.tasks().values())
        if c == "next":
            who = a.for_ or me
            ts = [t for t in ts if t["state"] == "open" and not deps_pending(st, t) and t.get("for") in (None, who)]
        else:
            if a.state:
                ts = [t for t in ts if t["state"] == a.state]
            elif not a.mine:
                ts = [t for t in ts if t["state"] not in FINAL]
            if a.for_:
                ts = [t for t in ts if t.get("for") == a.for_]
            if a.mine:
                ts = [t for t in ts if (t.get("claim") or {}).get("by") == me or t.get("for") == me]
        ts.sort(key=lambda t: (t.get("priority", "p2"), t["id"]))
        for t in ts[: (a.n if c == "next" else None)]:
            holder = (t.get("claim") or {}).get("by", "")
            print(f"{t['id']:6} {t.get('priority', ''):3} {display_state(t, st.at):18} {t.get('for') or 'any':6} {holder:8} {t['title']}")
        if not ts:
            print("nothing")
        return 0
    if c == "inbox":
        who = a.who or lg.need_agent()
        rows = [(p, m) for p, m in st.messages() if p.startswith(f"inbox/{who}/") or p.startswith(f"inbox/{BROADCAST}/")]
        if not a.all:
            rows = [(p, m) for p, m in rows if who not in m["read_by"] and m.get("from") != who]
        for p, m in sorted(rows, key=lambda x: x[1].get("sent", "")):
            print(f"{m['id']}\n    from {m.get('from')}, {short(m.get('sent'))}: {m.get('subject')}" + (f" [{m['task']}]" if m.get("task") else ""))
        if not rows:
            print("no unread messages" if not a.all else "no messages")
        return 0
    if c == "watch":
        me = lg.need_agent()
        sp = seen_path(lg.store, me)
        since = sp.read_text().strip() if sp.exists() else ""
        events = []
        for p in st.paths("log/"):
            for line in st.get(p).decode().splitlines():
                if line.strip():
                    events.append(json.loads(line))
        new = [e for e in events if e["at"] > since and (a.all or e["by"] != me)]
        mytasks = {t["id"] for t in st.tasks().values() if t.get("for") == me or (t.get("claim") or {}).get("by") == me or t.get("created_by") == me}
        print(f"ledger {lg.store.branch} at {iso(st.at)}; since {since or 'the beginning'}: {len(new)} change(s) by others")
        for e in new[-60:]:
            mark = "*" if (e.get("target", "").startswith(f"{me}/") or e.get("target") in mytasks or e.get("task") in mytasks) else " "
            print(f" {mark} {short(e['at'])} {e['by']:8} {e['op']:8} {e.get('target', '')}" + (f": {e['note'][:100]}" if e.get("note") else ""))
        unread = [m for p, m in st.messages() if (p.startswith(f"inbox/{me}/") or p.startswith(f"inbox/{BROADCAST}/"))
                  and me not in m["read_by"] and m.get("from") != me]
        print(f"unread for {me}: {len(unread)}")
        for m in sorted(unread, key=lambda m: m.get("sent", "")):
            print(f"   {m['id']}: {m.get('subject')}")
        lapsing = [t for t in st.tasks().values() if (t.get("claim") or {}).get("by") == me
                   and parse_time(t["claim"]["expires"]) - st.at < timedelta(minutes=45)]
        for t in lapsing:
            print(f"   your claim on {t['id']} ends {t['claim']['expires']}: renew, review, release or close it")
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(iso(st.at))
        if not a.no_heartbeat and (st.agents().get(me)):
            lg.mutate(f"heartbeat {me}", lambda s: lg.touch(s))
        return 0
    raise SystemExit(f"unknown command {c}")


if __name__ == "__main__":
    sys.exit(main())
