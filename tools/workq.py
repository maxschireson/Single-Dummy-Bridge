#!/usr/bin/env python3
"""workq: lease, renew, submit and resolve the Gen 9 team's tasks and experiments; send and read messages.

The team's files live on branch team/gen9 (README.md there): `tasks/<ID>.md` and
`experiments/<ID>.md` with a `key: value` header between `---` lines and markdown sections, and
messages `inbox/<name>/<stamp>-<from>-<slug>.md` that are never edited. Every change is one commit
made on the branch's current tip and pushed without force; if someone else pushed first, the
change is re-read and re-applied with its checks, so two sessions can never both lease one task.
STATUS.md is regenerated inside the same commit. Name yourself with --as NAME or $WORKQ_AGENT.
The tool keeps its own clone in ~/.cache/workq and never touches a checkout.

  workq.py hello --role TEXT [--session URL]       register, or refresh your last-seen time
  workq.py watch                                   changes since you last looked, unread mail, your leases, reviews
  workq.py status                                  the STATUS.md view; `refresh` commits it if it is stale

  workq.py tasks [--owner N] [--state S] [--mine]  workq.py next       workq.py show ID
  workq.py new TITLE --area A --kind K --owner N --priority P [--due T] [--depends IDS]
               [--goal TEXT --done-when TEXT --context TEXT | --body-file PATH] [--proposed] [--id ID]
               [--value "0.05 IMPs/board"] [--effort HOURS] [--probability P] [--budget BOX_HOURS] [--parent ID]
               [--explore yes] [--sweep yes]      (next orders by value x probability / effort within a priority;
                                                   at most two open sweeps per area)
  workq.py lease ID [--hours H<=4] [--force]       check out (leasing your own task again renews it)
  workq.py renew ID [--hours H]                    workq.py release ID --note TEXT   (give it back)
  workq.py submit ID --note TEXT [--branch B] [--commit SHA]     check in; the reviewer is told: the `reviewer`
                                                   header if set, else for a module task the owner's peer lead
                                                   (bill-sam, dave-will), else g9
  workq.py resolve ID --resolution R [--note TEXT] reviewer: accepted|dropped|superseded,
                                                   experiments adopted|rejected|inconclusive|retired
  workq.py reopen ID --note TEXT [--same-holder]   workq.py block ID --note TEXT
  workq.py log ID TEXT                             workq.py set ID KEY=VALUE ...    workq.py edit ID --file PATH

  workq.py send TO SUBJECT (--body TEXT | --file PATH) [--task ID] [--reply-to MSG]   TO may be "all"
  workq.py inbox [--all] [--agent N]               workq.py read MSG        workq.py ack   (all read)

  workq.py job submit FILE [--box B] [--replace]   queue a box job (tools/boxq.py says the format); job cancel ID --box B
  workq.py jobs                                    the box queues: each job's state, boards, boards an hour, expected finish
  workq.py fleet                                   box heartbeats and the board's allocation table, into STATUS.md
  workq.py issue [--create] [--print]              rewrite the "Gen 9 queue" GitHub issue (Max's phone view): decisions
                                                   for Max, reviews waiting, blocked, in progress, next checkpoint. Also
                                                   done after any change, at most every 10 minutes, where gh exists
  workq.py decision TITLE --body TEXT | --close N --note TEXT   g9 only: a decision for Max as its own issue, assigned
                                                   to him; his replies there are copied into inbox/g9
  workq.py check [--ready ID]                      validate every header (exit 1 if one is malformed); with --ready,
                                                   name the executor sections ID lacks (Base, Interface, Done when,
                                                   Time box, Tests, Results)
  workq.py brief ID                                everything a fresh session needs to do ID: the file, the rules, the commands
  workq.py export                                  everything as JSON

Environment: WORKQ_REPO, WORKQ_BRANCH (default team/gen9), WORKQ_LEAD (default g9), WORKQ_TRAILERS
(appended to commit messages), WORKQ_CACHE. Exit status 3 means the change was refused; nothing was written.
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
DEFAULT_BRANCH = "team/gen9"
NAME_RE = re.compile(r"^[a-z][a-z0-9]{0,31}$")
ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-[A-Z]?[0-9]{1,4}$")
RESOURCE_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}(:[A-Za-z0-9._-]{1,64})?$")
MSG_RE = re.compile(r"^(\d{8}T\d{4,6}Z)-([a-z][a-z0-9]*)-(.+)\.md$")
BROADCAST = "all"
POOL = "pool"

STATES = ("leased", "submitted", "blocked", "open", "proposed", "resolved")  # display order, as tools/status.py
REQUIRED = ("id", "title", "area", "kind", "owner", "state", "priority")
HEADER_ORDER = ("id", "title", "area", "kind", "owner", "state", "holder", "lease_until", "priority",
                "depends", "due", "created", "branch", "resolution")
AREAS = {"architecture": "A", "bidding": "B", "signals": "S", "arena": "D", "workflow": "W", "cross": "X"}
KINDS = ("design", "module", "experiment", "review", "ops")
PRIORITIES = ("high", "medium", "low")
RESOLUTIONS = {"tasks": ("accepted", "dropped", "superseded"), "experiments": ("adopted", "rejected", "inconclusive", "retired")}
LIFECYCLE = ("state", "holder", "lease_until", "resolution")  # changed only by the lifecycle commands
MAX_LEASE_HOURS = 4
PREREGISTERED = ("Hypothesis", "Primary metric and population", "Compute cap", "Stopping rule")  # filled before a lease
GRACE = timedelta(minutes=30)
RESULT_LINES = ("Evidence", "Sample", "Revisit if")  # an experiment's ## Result needs these before submit
SWEEP_CAP = 2  # open parameter-sweep experiments per area
PEERS = {"bill": "sam", "sam": "bill", "dave": "will", "will": "dave"}  # module reviews (g9, 12 Nov 07:28 UTC)
READY_SECTIONS = (("Base",), ("Interface",), ("Done when",), ("Time box",), ("Tests",), ("Results", "Where results go"))
RULES = """- Hidden hands are labels for training, experience and scoring, never inputs to a player's decision.
- Nothing made with the EPBot/BBA bidding engine or its card files.
- Frozen runs, manifests, feeds, completed episodes and receipts are never edited; changed behaviour gets a new identity.
- Never force-push. Feed, transfer, box and team branches are never merged into source.
- Work on a branch cut from the task's base (`feature/gen9-<area>-<slug>` unless the task says otherwise); open a PR into
  `feature/gen9` when the done-when is met, and name it in the submit note.
- State what was tested and what was not; keep negative and inconclusive results.
- End your commits with your own session trailer.
- Queue nothing on an Azure box unless the task gives you one; the allocation table on `box/coordination` says who holds each.
- Work only on this task. If it cannot be done as written, `log` why and `release` or `block` it rather than widen it."""
EXPERIMENT_SECTIONS = ("Hypothesis", "Mechanism", "Primary metric and population", "Regression slices",
                       "Compute cap", "Stopping rule", "Result")


class Conflict(Exception):
    """A check failed on the current tip: reported, never retried."""


class Malformed(Conflict):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


def hm(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%MZ")


def parse_time(s: str) -> datetime:
    for f in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s, f).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise ValueError(f"not a UTC time: {s!r} (want 2026-11-12T10:30Z)")


def short(s: str | None) -> str:
    return "" if not s else s[5:16].replace("T", " ")


def slugify(text: str, n: int = 30) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n].strip("-") or "msg"


def split_ids(s: str | None) -> list[str]:
    return [x for x in re.split(r"[ ,]+", s or "") if x]


# ---------------------------------------------------------------- git storage

class Store:
    """One branch of one remote, in a private bare cache, so no checkout is touched."""

    def __init__(self, url: str, branch: str):
        self.url, self.branch = url, branch
        self.ref, self.local = f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"
        self.cache = Path(os.environ.get("WORKQ_CACHE", "~/.cache/workq")).expanduser()
        self.git_dir = self.cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".git")
        if not (self.git_dir / "HEAD").exists():
            self.cache.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init", "--bare", "-q", str(self.git_dir)], check=True)
        self.git("config", "remote.origin.url", url)
        self.before_push = None  # test hook, called with the new commit before it is pushed

    def git(self, *args: str, input: bytes | None = None, check: bool = True, env: dict | None = None,
            timeout: float = 300) -> subprocess.CompletedProcess:
        e = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        e.update(env or {})
        r = subprocess.run(["git", "--git-dir", str(self.git_dir), *args], input=input, capture_output=True, timeout=timeout, env=e)
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
        entries = []
        for line in self.git("ls-tree", "-r", "-z", tip).stdout.decode().split("\0"):
            if line:
                meta, path = line.split("\t", 1)
                entries.append((path, meta.split()[2]))
        if not entries:
            return {}
        batch = self.git("cat-file", "--batch", input=("\n".join(s for _, s in entries) + "\n").encode()).stdout
        files, pos = {}, 0
        for path, _ in entries:
            nl = batch.index(b"\n", pos)
            size = int(batch[pos:nl].split()[2])
            files[path] = batch[nl + 1:nl + 1 + size]
            pos = nl + 2 + size
        return files

    def commit(self, tip: str | None, changes: dict[str, bytes | None], message: str, author: str) -> str:
        index = self.git_dir / f"index-{os.getpid()}"
        env = {"GIT_INDEX_FILE": str(index), "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": "workq@invalid",
               "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": "workq@invalid"}
        try:
            self.git("read-tree", *([tip] if tip else ["--empty"]), env=env)
            lines = []
            for path, data in changes.items():
                if data is None:
                    lines.append(f"0 {'0' * 40}\t{path}")  # mode 0 removes the entry
                else:
                    lines.append(f"100644 {self.out('hash-object', '-w', '--stdin', input=data)}\t{path}")
            if lines:
                self.git("update-index", "--add", "--index-info", input=("\n".join(lines) + "\n").encode(), env=env)
            tree = self.out("write-tree", env=env)
        finally:
            index.unlink(missing_ok=True)
        return self.out("commit-tree", tree, *(["-p", tip] if tip else []), "-F", "-", input=message.encode(), env=env)

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


# ---------------------------------------------------------------- task and experiment files

class Doc:
    """A task or experiment file. Header lines that are not changed are written back byte for byte."""

    def __init__(self, path: str, text: str):
        self.path, self.folder = path, path.split("/", 1)[0]
        lines = text.split("\n")
        if not lines or lines[0].strip() != "---":
            raise Malformed(f"{path}: no header")
        self.head: list[list] = []  # [key, value, original line or None]
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                self.body = "\n".join(lines[i + 1:])
                break
            if ":" not in line:
                raise Malformed(f"{path}: bad header line {line!r}")
            k, _, v = line.partition(":")
            self.head.append([k.strip(), v.split(" #")[0].strip(), line])
        else:
            raise Malformed(f"{path}: header is not closed")

    def get(self, k: str) -> str:
        for row in self.head:
            if row[0] == k:
                return row[1]
        return ""

    def set(self, k: str, v: str) -> None:
        for row in self.head:
            if row[0] == k:
                if row[1] != v:
                    row[1], row[2] = v, None
                return
        pos = len(self.head)
        if k in HEADER_ORDER:
            later = HEADER_ORDER[HEADER_ORDER.index(k) + 1:]
            pos = next((i for i, row in enumerate(self.head) if row[0] in later), pos)
        self.head.insert(pos, [k, v, None])

    def validate(self) -> "Doc":
        for k in REQUIRED:
            if not self.get(k):
                raise Malformed(f"{self.path}: header has no {k}")
        stem = self.path.rsplit("/", 1)[-1][:-3]
        if self.get("id") != stem:
            raise Malformed(f"{self.path}: id {self.get('id')!r} differs from the file name")
        if not ID_RE.match(self.get("id")):
            raise Malformed(f"{self.path}: id {self.get('id')!r} is not like G9-B1 or E9-3")
        if self.get("state") not in STATES:
            raise Malformed(f"{self.path}: unknown state {self.get('state')!r}")
        for k, allowed in (("kind", KINDS), ("priority", PRIORITIES)):
            if self.get(k) not in allowed:
                raise Malformed(f"{self.path}: {k} {self.get(k)!r} is not one of {', '.join(allowed)}")
        if self.get("area") not in AREAS:
            raise Malformed(f"{self.path}: area {self.get('area')!r} is not one of {', '.join(AREAS)}")
        for k in ("owner", "holder"):
            v = self.get(k)
            if v and not NAME_RE.match(v):
                raise Malformed(f"{self.path}: {k} {v!r} is not a roster name")
        for k in ("lease_until", "due", "created"):
            if self.get(k):
                try:
                    parse_time(self.get(k))
                except ValueError as e:
                    raise Malformed(f"{self.path}: {k}: {e}")
        for k in ("effort", "budget", "probability"):
            v = self.get(k)
            if v:
                try:
                    x = float(v.split()[0])
                except ValueError:
                    raise Malformed(f"{self.path}: {k} {v!r} is not a number")
                if k == "probability" and not 0 <= x <= 1:
                    raise Malformed(f"{self.path}: probability {v!r} is not between 0 and 1")
        if self.get("value") and not re.match(r"^[+-]?\d+(\.\d+)?", self.get("value")):
            raise Malformed(f"{self.path}: value {self.get('value')!r} does not start with a number (e.g. '0.05 IMPs/board')")
        for k in ("explore", "sweep"):
            if self.get(k) and self.get(k) not in ("yes", "no"):
                raise Malformed(f"{self.path}: {k} is yes or no, not {self.get(k)!r}")
        res = self.get("resolution")
        if res and res not in RESOLUTIONS.get(self.folder, ()):
            raise Malformed(f"{self.path}: resolution {res!r} is not one of {', '.join(RESOLUTIONS.get(self.folder, ()))}")
        if self.get("state") == "leased" and not (self.get("holder") and self.get("lease_until")):
            raise Malformed(f"{self.path}: a leased task needs holder and lease_until")
        for d in split_ids(self.get("depends")):
            if not ID_RE.match(d):
                raise Malformed(f"{self.path}: depends names {d!r}")
        return self

    def add_log(self, at: datetime, who: str, text: str) -> None:
        line = f"- {hm(at)} {who}: {text}"
        lines = self.body.split("\n")
        start = next((i for i, l in enumerate(lines) if l.strip().lower() == "## log"), None)
        if start is None:
            self.body = self.body.rstrip("\n") + f"\n\n## Log\n\n{line}\n"
            return
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        last = max([i for i in range(start + 1, end) if lines[i].strip()] or [start])
        lines.insert(last + 1, line if last > start else "\n" + line)
        self.body = "\n".join(lines)
        if not self.body.endswith("\n"):
            self.body += "\n"

    def section(self, name: str) -> str:
        m = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", self.body, re.S | re.M | re.I)
        return m.group(1).strip() if m else ""

    def render(self) -> bytes:
        head = "".join((row[2] if row[2] is not None else f"{row[0]}: {row[1]}") + "\n" for row in self.head)
        return f"---\n{head}---\n{self.body}".encode()

    def lease_lapsed(self, at: datetime) -> bool:
        return self.get("state") == "leased" and bool(self.get("lease_until")) and parse_time(self.get("lease_until")) <= at


# ---------------------------------------------------------------- messages

def parse_message(path: str, data: bytes) -> dict:
    name = path.rsplit("/", 1)[-1]
    to = path.split("/")[1]
    m = MSG_RE.match(name)
    text = data.decode(errors="replace")
    msg = dict(id=name[:-3], path=path, to=to, stamp=m.group(1) if m else "", **{"from": m.group(2) if m else ""})
    if text.startswith("---\n") and "\n---\n" in text[4:]:  # messages with a front-matter header, read but not written
        end = text.index("\n---\n", 4)
        for line in text[4:end].splitlines():
            k, _, v = line.partition(":")
            if k.strip() in ("from", "subject", "task", "reply_to"):
                msg[k.strip()] = v.strip()
        text = text[end + 5:]
    lines = [l for l in text.strip("\n").split("\n")]
    msg.setdefault("subject", next((l.strip() for l in lines if l.strip()), ""))
    msg["body"] = text.strip("\n")
    if "task" not in msg:
        t = re.search(r"\bTask ([A-Z][A-Z0-9]*-[A-Z]?\d+)\.", text[:600])
        if t:
            msg["task"] = t.group(1)
    return msg


def format_message(sender: str, at: datetime, subject: str, body: str, task: str | None, reply_to: str | None) -> bytes:
    sig = f"{sender}, {at.day} {at:%b %H:%M} UTC."
    if task:
        sig += f" Task {task}."
    if reply_to:
        sig += f" Reply to {reply_to}."
    return f"{subject.strip()}\n\n{sig}\n\n{body.strip()}\n".encode()


# ---------------------------------------------------------------- channel state

class State:
    def __init__(self, files: dict[str, bytes], agent: str, at: datetime, lead: str):
        self.files, self.agent, self.at, self.lead = files, agent, at, lead
        self.changes: dict[str, bytes | None] = {}
        self.events: list[dict] = []
        self.notes: list[str] = []  # printed to the caller after a successful change

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
        self.changes[path] = (json.dumps(obj, indent=1) + "\n").encode()

    def put(self, path: str, data: bytes | None) -> None:
        self.changes[path] = data

    def docs(self, folder: str | None = None) -> tuple[dict[str, Doc], list[str]]:
        out, errors = {}, []
        for f in ([folder] if folder else ["tasks", "experiments"]):
            for p in self.paths(f + "/"):
                if p.endswith(".md"):
                    try:
                        d = Doc(p, self.get(p).decode()).validate()
                        out[d.get("id")] = d
                    except Malformed as e:
                        errors.append(str(e))
        return out, errors

    def doc(self, did: str) -> Doc:
        for f in ("tasks", "experiments"):
            data = self.get(f"{f}/{did}.md")
            if data is not None:
                return Doc(f"{f}/{did}.md", data.decode()).validate()
        raise Conflict(f"no task or experiment {did}")

    def save_doc(self, d: Doc) -> None:
        d.validate()
        self.put(d.path, d.render())

    def agents(self) -> dict[str, dict]:
        return {p[7:-5]: self.load(p) for p in self.paths("agents/") if p.endswith(".json")}

    def messages(self) -> list[dict]:
        return [parse_message(p, self.get(p)) for p in self.paths("inbox/") if p.endswith(".md")]

    def unread(self, who: str) -> list[dict]:
        a = self.load(f"agents/{who}.json") or {}
        until, seen = a.get("read_until", ""), set(a.get("read_ids", []))
        return sorted([m for m in self.messages() if m["to"] in (who, BROADCAST) and m["from"] != who
                       and m["stamp"] > until and m["id"] not in seen], key=lambda m: m["id"])

    def event(self, op: str, target: str, note: str = "", **extra) -> None:
        e = dict(at=self.at.strftime("%Y-%m-%dT%H:%M:%SZ"), by=self.agent, op=op, target=target)
        if note:
            e["note"] = note[:300]
        e.update({k: v for k, v in extra.items() if v not in (None, "", [])})
        self.events.append(e)

    def send(self, to: str, subject: str, body: str, task: str | None = None, reply_to: str | None = None,
             sender: str | None = None) -> str:
        sender = sender or self.agent  # `max` for his replies copied from GitHub
        base = f"{self.at:%Y%m%dT%H%MZ}-{sender}-{slugify(subject)}"
        mid, n = base, 1
        while self.get(f"inbox/{to}/{mid}.md") is not None:
            n += 1
            mid = f"{base}-{n}"
        self.put(f"inbox/{to}/{mid}.md", format_message(sender, self.at, subject, body, task, reply_to))
        self.event("send", f"{to}/{mid}", subject, task=task)
        return mid

    def flush_log(self) -> None:
        if self.events:
            path = f"log/{self.at:%Y-%m-%d}.jsonl"
            self.put(path, (self.get(path) or b"") + b"".join((json.dumps(e) + "\n").encode() for e in self.events))


def score(d: Doc) -> float | None:
    """Expected value for effort: value x probability / effort, when value and effort are given."""
    try:
        v = float(re.match(r"^[+-]?\d+(\.\d+)?", d.get("value")).group(0))
        e = float(d.get("effort").split()[0])
        pr = float(d.get("probability").split()[0]) if d.get("probability") else 1.0
    except (AttributeError, ValueError, IndexError):
        return None
    return v * pr / e if e > 0 else None


def missing_result(d: Doc) -> list[str]:
    res = d.section("Result")
    if not res or res.strip() == "_not yet_":
        return list(RESULT_LINES)
    return [n for n in RESULT_LINES if not re.search(rf"^\W*{re.escape(n)}\W*:", res, re.M | re.I)]


def reviewer_of(d: Doc, lead: str) -> str:
    """Who reviews a submission: the `reviewer` header if set; a module task's peer lead; otherwise the lead."""
    if d.get("reviewer"):
        return d.get("reviewer")
    if d.folder == "tasks" and d.get("kind") == "module":
        peer = PEERS.get(d.get("owner"))
        if peer and peer != d.get("holder"):
            return peer
    return lead


def missing_ready(d: Doc) -> list[str]:
    """Sections an executor needs that are absent or empty (docs/gen9/workflow.md, section 3)."""
    out = []
    for names in READY_SECTIONS:
        if not any(d.section(n).strip() not in ("", "_not yet_", "TBD") for n in names):
            out.append(names[0])
    return out


def brief_text(st: State, d: Doc, branch: str) -> str:
    did = d.get("id")
    pend = deps_unresolved(st, d)
    miss = missing_ready(d)
    lines = [f"# Brief: {did}, {d.get('title')}", "",
             f"This brief is all the context you are given. The task lives in `{d.path}` on branch `{branch}` of "
             f"maxschireson/Single-Dummy-Bridge; the repository's own rules are in AGENTS.md and CONTRIBUTING.md on main.", ""]
    if miss:
        lines += [f"**Not executor-ready:** the task has no {', '.join(miss)} section. Ask its owner ({d.get('owner')}) "
                  f"before you start: `workq.py send {d.get('owner')} \"{did}: ...\" --task {did} --body ...`.", ""]
    if pend:
        lines += [f"**Depends on {', '.join(pend)}**, not resolved yet.", ""]
    lines += ["## The task", "", "```markdown", d.render().decode().rstrip(), "```", "",
              "## Rules that always hold", "", RULES, "",
              "## How to work it", "",
              "    git fetch origin team/gen9 && git show FETCH_HEAD:tools/workq.py > /tmp/workq.py",
              "    Q=\"python3 /tmp/workq.py --as <your name>\"",
              f"    $Q hello --role \"executor for {did}\" --session <your session link>",
              f"    $Q lease {did} --hours <the time box, at most 4>",
              f"    $Q log {did} \"<a result, a blocker or a change of plan>\"      # whenever another session would want to know",
              f"    $Q renew {did}                                               # before the lease ends",
              "    python3 scripts/run_tests.py --prepare --set gen9            # in your source checkout, before you submit",
              f"    $Q submit {did} --branch <branch> --commit <sha> --note \"what was done, what was tested, what is unresolved\"",
              f"    $Q release {did} --note \"<where the partial work is>\"        # if you must stop", "",
              f"Reviewer: {reviewer_of(d, st.lead)}. Run `$Q watch` at natural breaks for messages about this task."]
    return "\n".join(lines) + "\n"


def deps_unresolved(st: State, d: Doc) -> list[str]:
    out = []
    for dep in split_ids(d.get("depends")):
        try:
            dd = st.doc(dep)
            if dd.get("state") != "resolved" or dd.get("resolution") in ("dropped",):
                out.append(dep)
        except Conflict:
            out.append(dep)
    return out


def note_for(st: State, d: Doc, at: datetime) -> str:
    s = d.get("state")
    if s == "resolved":
        res = d.get("resolution")
        if d.folder == "experiments":
            line = next((l.strip() for l in d.section("Result").splitlines() if l.strip()), "")
            if line and line != "_not yet_":
                res = f"{res}. {line}".strip(". ")
        return res
    if s == "leased" and d.get("lease_until"):
        lu = parse_time(d.get("lease_until"))
        if lu <= at:
            return "lease expired" + (", may be taken over" if at - lu >= GRACE else "")
    if s not in ("submitted",) and d.get("due") and parse_time(d.get("due")) < at:
        return "past due"
    if s in ("open", "proposed", "blocked"):
        pend = deps_unresolved(st, d)
        if pend:
            return "after " + ", ".join(pend)
    return ""


# ---------------------------------------------------------------- rendering

def render_status(st: State) -> bytes:
    at = st.at
    docs, errors = st.docs()
    order = {s: i for i, s in enumerate(STATES)}
    rank = {p: i for i, p in enumerate(PRIORITIES)}
    key = lambda d: (order[d.get("state")], rank.get(d.get("priority"), 9), d.get("id"))
    tasks = sorted([d for d in docs.values() if d.folder == "tasks"], key=key)
    exps = sorted([d for d in docs.values() if d.folder == "experiments"], key=key)
    L = ["# Gen 9 status", "",
         f"Generated {at:%Y-%m-%d %H:%M} UTC by `tools/workq.py` after a change by `{st.agent}`. "
         f"Do not edit by hand. How to work here: [README.md](README.md).", ""]

    counts: dict[str, dict[str, int]] = {}
    for d in tasks:
        counts.setdefault(d.get("owner"), {}).setdefault(d.get("state"), 0)
        counts[d.get("owner")][d.get("state")] += 1
    L += ["## Tasks by owner", "", "| Owner | " + " | ".join(STATES) + " |", "| --- |" + " ---: |" * len(STATES)]
    for o in sorted(counts):
        L.append(f"| {o} | " + " | ".join(str(counts[o].get(s, 0)) for s in STATES) + " |")
    L.append("")

    def table(rows):
        if not rows:
            return ["_none_", ""]
        out = ["| Id | Title | Owner | Holder | State | Priority | Due | Note |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for d in rows:
            lu = f" until {short(d.get('lease_until'))}" if d.get("state") == "leased" else ""
            out.append(f"| [{d.get('id')}]({d.path}) | {d.get('title')} | {d.get('owner')} | {d.get('holder')}{lu} | "
                       f"{d.get('state')} | {d.get('priority')} | {d.get('due')} | {note_for(st, d, at).replace('|', '/')} |")
        return out + [""]
    waiting = [d for d in tasks + exps if d.get("state") == "submitted"]
    if waiting:
        L += ["## Waiting for review", "", "| Reviewer | Id | Title | Submitted by | Branch |", "| --- | --- | --- | --- | --- |"]
        for d in sorted(waiting, key=lambda d: (reviewer_of(d, st.lead), d.get("id"))):
            L.append(f"| {reviewer_of(d, st.lead)} | [{d.get('id')}]({d.path}) | {d.get('title')} | {d.get('holder')} | {d.get('branch')} |")
        L.append("")
    L += ["## Tasks", ""] + table(tasks) + ["## Experiments", ""] + table(exps)

    agents = st.agents()
    L += ["## Agents", "", "| Agent | Role | Last seen | Unread | Session |", "| --- | --- | --- | ---: | --- |"]
    for name, a in sorted(agents.items()):
        sess = a.get("session") or ""
        L.append(f"| {name} | {a.get('role', '')} | {short(a.get('last_seen'))} | {len(st.unread(name))} | "
                 f"{'[link](' + sess + ')' if sess.startswith('http') else sess} |")
    L.append("")

    recent = sorted(st.messages(), key=lambda m: m["id"])[-15:]
    L += ["## Latest messages", ""]
    if recent:
        L += ["| To | From | Sent | First line |", "| --- | --- | --- | --- |"]
        for m in reversed(recent):
            L.append(f"| {m['to']} | {m['from']} | {short(m['stamp'][:4] + '-' + m['stamp'][4:6] + '-' + m['stamp'][6:11] + ':' + m['stamp'][11:13])} | "
                     f"[{m['subject'][:110].replace('|', '/')}]({m['path']}) |")
    else:
        L.append("_none_")
    L.append("")

    L += render_queues(st)
    L += render_fleet(st.load("fleet.json"), {})
    if errors:
        L += ["## Files with a malformed header", ""] + [f"- {e}" for e in errors] + [""]
    return "\n".join(L).encode()


# ---------------------------------------------------------------- box queue (tools/boxq.py)

def box_queues(st: State) -> dict[str, dict]:
    """Per box: its status file, plus job files it has not reported yet."""
    out = {}
    for p in st.paths("boxq/"):
        parts = p.split("/")
        if len(parts) != 3 or not p.endswith(".json"):
            continue
        box = parts[1]
        q = out.setdefault(box, dict(status=None, jobs={}))
        if parts[2] == "status.json":
            q["status"] = st.load(p)
        else:
            try:
                j = st.load(p)
                q["jobs"][j["id"]] = j
            except (ValueError, KeyError, TypeError):
                pass
    return out


def queue_rows(q: dict) -> list[dict]:
    reported = (q.get("status") or {}).get("jobs", {})
    rows = []
    for jid, j in q["jobs"].items():
        r = dict(id=jid, owner=j.get("owner"), experiment=j.get("experiment") or "", priority=j.get("priority"), cores=j.get("cores"),
                 target=(j.get("progress") or {}).get("target"))
        r.update({k: v for k, v in reported.get(jid, {}).items() if k in ("state", "boards", "rate_per_hour", "eta", "published", "short")})
        r.setdefault("state", "cancelled" if j.get("state") == "cancelled" else "not seen yet")
        rows.append(r)
    order = {"running": 0, "paused": 1, "waiting": 2, "not seen yet": 3, "done": 4, "failed": 5, "cancelled": 6}
    return sorted(rows, key=lambda r: (order.get(r["state"], 9), r.get("priority") or 99, r["id"]))


def render_queues(st: State) -> list[str]:
    qs = box_queues(st)
    if not qs:
        return []
    L = ["## Box queue", ""]
    for box, q in sorted(qs.items()):
        stt = q.get("status") or {}
        L += [f"**{box}**: {stt.get('cores_busy', '?')} of {stt.get('cores', '?')} cores busy, reported {short(stt.get('updated'))} UTC"
              + (f"; malformed job files: {'; '.join(stt['bad_jobs'])}" if stt.get("bad_jobs") else "") + ".", "",
              "| Job | Experiment | Owner | Pri | Cores | State | Boards | Boards/h | Expected finish | Results |",
              "| --- | --- | --- | ---: | ---: | --- | --- | ---: | --- | --- |"]
        for r in queue_rows(q):
            boards = f"{r.get('boards', 0):,} of {r['target']:,}" if r.get("target") else str(r.get("boards", ""))
            L.append(f"| {r['id']} | {r['experiment']} | {r['owner']} | {r.get('priority')} | {r.get('cores')} | {r['state']}"
                     f"{' (short)' if r.get('short') else ''} | {boards} | {r.get('rate_per_hour') or ''} | {short(r.get('eta'))} | "
                     f"{('`' + r['published'] + '`') if r.get('published') else ''} |")
        L.append("")
    return L


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


def collect_fleet(store: Store, at: datetime) -> dict:
    """Read every box's heartbeat (box/<box>/status) and the board's allocation table. Read-only."""
    heads = store.out("ls-remote", "--heads", "origin")
    boxes = sorted({m.group(1) for m in re.finditer(r"refs/heads/box/([a-z0-9-]+)/status$", heads, re.M)})

    def blob(branch: str, path: str) -> bytes | None:
        local = f"refs/remotes/origin/{branch}"
        r = store.git("fetch", "--quiet", "--no-tags", "--depth=1", "origin", f"+refs/heads/{branch}:{local}", check=False)
        if r.returncode != 0:
            return None
        r = store.git("cat-file", "blob", f"{local}:{path}", check=False)
        return r.stdout if r.returncode == 0 else None

    alloc = board_allocation((blob("box/coordination", "BOARD.md") or b"").decode(errors="replace"))
    rows = []
    for box in boxes:
        row = dict(box=box, board_now=alloc.get(box))
        hb = json.loads(blob(f"box/{box}/status", "heartbeat.json") or b"{}")
        if hb:
            mem, disk = hb.get("memory_mb") or {}, (hb.get("disk") or {}).get("home") or {}
            row.update(heartbeat=hb.get("time"), cpus=hb.get("cpus"), load=(hb.get("load") or [None])[0],
                       mem_free_gb=round(mem.get("MemAvailable", 0) / 1024, 1), mem_total_gb=round(mem.get("MemTotal", 0) / 1024, 1),
                       disk_free_gb=disk.get("free_gb"), running=hb.get("running"), pending=len(hb.get("pending") or []))
        rows.append(row)
    return dict(at=at.strftime("%Y-%m-%dT%H:%M:%SZ"), boxes=rows)


def render_fleet(f: dict | None, res: dict) -> list[str]:
    if not f:
        return []
    snap = parse_time(f["at"])
    L = ["## Boxes", "", f"Heartbeats from `box/<box>/status` and the allocation table on `box/coordination` (which "
         f"decides who holds a box), read at {short(f['at'])} UTC by `workq.py fleet`.", "",
         "| Box | Heartbeat | Load / CPUs | Free memory | Free disk | boxctl queue | Board says |",
         "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in f["boxes"]:
        board = (r.get("board_now") or "").replace("|", "/")
        board = board[:90] + ("..." if len(board) > 90 else "")
        if not r.get("heartbeat"):
            L.append(f"| {r['box']} | none | | | | | {board} |")
            continue
        age = int((snap - parse_time(r["heartbeat"])).total_seconds() // 60)
        hb = short(r["heartbeat"]) + (f" (**{age} min old**)" if age > 12 else "")
        q = ("running " + r["running"].split("-", 2)[-1] if r.get("running") else "idle") + (f", {r['pending']} waiting" if r.get("pending") else "")
        L.append(f"| {r['box']} | {hb} | {r.get('load')} / {r.get('cpus')} | {r.get('mem_free_gb')} of {r.get('mem_total_gb')} GB | "
                 f"{r.get('disk_free_gb')} GB | {q} | {board} |")
    return L + [""]


# ---------------------------------------------------------------- phone view (GitHub issues)

GH_REPO = os.environ.get("WORKQ_GH_REPO", "maxschireson/Single-Dummy-Bridge")
MARK = "<!-- workq -->"  # in every body and comment workq writes, so its own text is never taken for Max's
ISSUE_EVERY = timedelta(minutes=10)


def gh(method: str, path: str, fields: dict | None = None) -> object:
    """One GitHub REST call through the gh CLI; returns the parsed JSON (None for an empty body)."""
    import shutil
    if not shutil.which("gh"):
        raise SystemExit("this needs the gh CLI (GitHub REST), which this session does not have")
    args = ["gh", "api", "-X", method, f"repos/{GH_REPO}/{path}"]
    data = None
    if fields is not None:
        args += ["--input", "-"]
        data = json.dumps(fields)
    r = subprocess.run(args, input=data, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise SystemExit(f"gh api {method} {path} failed: {(r.stderr or r.stdout).strip()[:400]}")
    return json.loads(r.stdout) if r.stdout.strip() else None


def next_checkpoint(st: State) -> str:
    """The next row of ROSTER.md's checkpoint table, e.g. 'Thu 12 Nov, about 12:00: Checkpoint 1: ...'."""
    text = (st.get("ROSTER.md") or b"").decode(errors="replace")
    for line in text.splitlines():
        m = re.match(r"\|\s*\w{3} (\d{1,2}) (\w{3}), about (\d{1,2}):(\d{2})\s*\|\s*(.+?)\s*\|\s*$", line)
        if not m:
            continue
        try:
            when = datetime.strptime(f"{st.at.year} {m.group(2)} {m.group(1)} {m.group(3)}:{m.group(4)}", "%Y %b %d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if when > st.at:
            return f"{when:%a %d %b %H:%M} UTC: {m.group(5)}"
    return "none listed"


def ago(st: State, stamp: str) -> str:
    try:
        minutes = int((st.at - parse_time(stamp)).total_seconds() // 60)
    except ValueError:
        return ""
    return f"{minutes} min" if minutes < 120 else f"{minutes // 60} h"


def queue_summary(st: State, decisions: list[dict]) -> str:
    """One phone screen: decisions waiting for Max first, then reviews, blocked, in progress, the next checkpoint."""
    docs, errors = st.docs()
    url = f"https://github.com/{GH_REPO}/blob/{os.environ.get('WORKQ_BRANCH', DEFAULT_BRANCH)}/STATUS.md"

    def when_submitted(d: Doc) -> str:
        stamps = re.findall(r"^- (\S+) \S+: submitted", d.section("Log"), re.M)
        return ago(st, stamps[-1]) if stamps else ""
    L = [MARK, f"**Gen 9 queue**, {st.at:%a %d %b %H:%M} UTC. Rewritten by `workq` (at most every 10 minutes); "
         f"everything else: [STATUS.md]({url}).", ""]
    L.append(f"**Decisions for Max ({len(decisions)})**" + ("" if decisions else ": none open."))
    for i in decisions:
        L.append(f"- [#{i['number']} {i['title']}]({i['html_url']}), raised {ago(st, i['created_at'][:16] + 'Z')} ago")
    waiting = sorted([d for d in docs.values() if d.get("state") == "submitted"], key=lambda d: (reviewer_of(d, st.lead), d.get("id")))
    L += ["", f"**Reviews waiting ({len(waiting)})**" + ("" if waiting else ": none.")]
    by = {}
    for d in waiting:
        by.setdefault(reviewer_of(d, st.lead), []).append(f"{d.get('id')} ({d.get('holder')}, {when_submitted(d)})")
    L += [f"- {r}: " + "; ".join(v) for r, v in sorted(by.items())]
    blocked = [d for d in docs.values() if d.get("state") == "blocked"]
    L += ["", f"**Blocked ({len(blocked)})**" + ("" if blocked else ": none.")]
    for d in sorted(blocked, key=lambda d: d.get("id")):
        why = re.findall(r"blocked: (.+)$", d.section("Log"), re.M)
        L.append(f"- {d.get('id')} {d.get('title')[:60]}" + (f": {why[-1][:90]}" if why else ""))
    leased = [d for d in docs.values() if d.get("state") == "leased"]
    holders = {}
    for d in sorted(leased, key=lambda d: d.get("id")):
        holders.setdefault(d.get("holder"), []).append(d.get("id"))
    L += ["", f"**In progress ({len(leased)})**: " + (" · ".join(f"{h}: {', '.join(v)}" for h, v in sorted(holders.items())) or "none")]
    today = [d for d in docs.values() if d.get("state") == "resolved"
             and re.search(rf"^- {st.at:%Y-%m-%d}\S* \S+: resolved", d.section("Log"), re.M)]
    open_ = sum(1 for d in docs.values() if d.get("state") in ("open", "proposed"))
    for box, q in sorted(box_queues(st).items()):
        bits = [f"{r['id']} {r['state']} {r.get('boards', 0):,}/{r['target']:,}" + (f", {r['rate_per_hour']:.0f}/h, ETA {short(r['eta'])[6:]}" if r.get("rate_per_hour") and r.get("eta") else "")
                for r in queue_rows(q) if r["state"] in ("running", "paused", "waiting", "not seen yet") and r.get("target")]
        L.append(f"**Box {box}**: " + (" · ".join(bits) if bits else "idle"))
    L += [f"**Resolved today**: {len(today)}. **Open, not started**: {open_}.",
          f"**Next checkpoint**: {next_checkpoint(st)}"]
    if errors:
        L.append(f"**Malformed files**: {len(errors)} (see STATUS.md)")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- the queue

class Ledger:
    def __init__(self, url: str | None = None, branch: str | None = None, agent: str | None = None, lead: str | None = None):
        self.store = Store(url or os.environ.get("WORKQ_REPO", DEFAULT_REPO), branch or os.environ.get("WORKQ_BRANCH", DEFAULT_BRANCH))
        self.agent = agent or os.environ.get("WORKQ_AGENT")
        self.lead = lead or os.environ.get("WORKQ_LEAD", "g9")
        self.clock = now  # tests replace this

    def need_agent(self) -> str:
        if not self.agent or not NAME_RE.match(self.agent) or self.agent in (BROADCAST, POOL):
            raise SystemExit("say who you are: --as NAME or WORK_AGENT=NAME (a roster name: lower case letters and digits)")
        return self.agent

    def snapshot(self) -> State:
        return State(self.store.read(self.store.fetch()), self.agent or "-", self.clock(), self.lead)

    def mutate(self, summary: str, fn, allow_create: bool = False):
        agent = self.need_agent()
        for attempt in range(10):
            tip = self.store.fetch()
            if tip is None and not allow_create:
                raise SystemExit(f"branch {self.store.branch} does not exist")
            st = State(self.store.read(tip), agent, self.clock(), self.lead)
            result = fn(st)
            if not st.changes and not st.events:
                return result
            st.flush_log()
            st.put("STATUS.md", render_status(st))
            msg = f"{agent}: {summary}\n"
            if os.environ.get("WORKQ_TRAILERS"):
                msg += "\n" + os.environ["WORKQ_TRAILERS"].strip() + "\n"
            if self.store.push(self.store.commit(tip, st.changes, msg, f"{agent} (workq)")):
                for n in st.notes:
                    print(n, file=sys.stderr)
                self.maybe_refresh_issue(st, summary)
                return result
            time.sleep(min(0.5 * (attempt + 1), 4))
        raise SystemExit("the branch kept moving under this change; try again")

    def maybe_refresh_issue(self, st: State, summary: str) -> None:
        import shutil
        if os.environ.get("WORKQ_ISSUE", "1") == "0" or summary.startswith("queue issue") or not shutil.which("gh"):
            return
        if not (st.load("issues.json") or {}).get("queue"):
            return
        try:
            self.issue_refresh(force=False)
        except (SystemExit, Exception) as e:  # the phone view never blocks a change
            print(f"note: the queue issue was not refreshed ({str(e)[:160]})", file=sys.stderr)

    def touch(self, st: State, gap_minutes: int = 15) -> None:
        a = st.load(f"agents/{st.agent}.json")
        if a and (not a.get("last_seen") or st.at - parse_time(a["last_seen"]) >= timedelta(minutes=gap_minutes)):
            a["last_seen"] = st.at.strftime("%Y-%m-%dT%H:%M:%SZ")
            st.save(f"agents/{st.agent}.json", a)

    def is_reviewer(self, st: State, d: Doc) -> bool:
        return st.agent in (st.lead, reviewer_of(d, st.lead)) or (st.agent == d.get("owner") and d.get("holder") not in ("", st.agent))

    # presence
    def hello(self, role, session, model, notes):
        def fn(st):
            path = f"agents/{st.agent}.json"
            a = st.load(path)
            new = a is None
            a = a or dict(name=st.agent, registered=st.at.strftime("%Y-%m-%dT%H:%M:%SZ"))
            for k, v in (("role", role), ("session", session), ("model", model), ("notes", notes)):
                if v is not None:
                    a[k] = v
            a["last_seen"] = st.at.strftime("%Y-%m-%dT%H:%M:%SZ")
            st.save(path, a)
            if new:
                st.event("hello", st.agent, a.get("role", ""))
            return a
        return self.mutate(f"hello from {self.agent}", fn)

    # tasks and experiments
    def new(self, title, area, kind, owner, priority, depends, due, body, proposed=False, did=None, extra=None):
        if area not in AREAS:
            raise SystemExit(f"--area must be one of {', '.join(AREAS)}")

        def fn(st):
            docs, _ = st.docs()
            exp = kind == "experiment" and (did or "E").startswith("E")
            folder = "experiments" if exp else "tasks"
            ident = did
            if not ident:
                if exp:
                    ident = "E9-" + str(1 + max([int(k.split("-")[1]) for k in docs if k.startswith("E9-")] + [0]))
                else:
                    p = f"G9-{AREAS[area]}"
                    ident = p + str(1 + max([int(k[len(p):]) for k in docs if k.startswith(p) and k[len(p):].isdigit()] + [0]))
            if ident in docs or st.get(f"tasks/{ident}.md") or st.get(f"experiments/{ident}.md"):
                raise Conflict(f"{ident} exists")
            for dep in depends:
                if dep not in docs:
                    raise Conflict(f"no task or experiment {dep}")
            text = body.strip() if body.strip() else (
                "\n\n".join(f"## {s}\n\n_not yet_" if s == "Result" else f"## {s}\n\n" for s in EXPERIMENT_SECTIONS) if exp
                else "## Goal\n\n\n\n## Done when\n\n\n\n## Context\n\n")
            head = dict(id=ident, title=title, area=area, kind=kind, owner=owner, state="proposed" if proposed else "open",
                        holder="", lease_until="", priority=priority, depends=", ".join(depends), due=due or "", created=hm(st.at), branch="", resolution="")
            head.update({k: v for k, v in (extra or {}).items() if v not in (None, "")})
            if exp and head.get("sweep") == "yes":
                sweeps = [k for k, x in docs.items() if x.folder == "experiments" and x.get("sweep") == "yes"
                          and x.get("area") == area and x.get("state") not in ("resolved",)]
                if len(sweeps) >= SWEEP_CAP:
                    raise Conflict(f"{area} already has {len(sweeps)} open sweeps ({', '.join(sorted(sweeps))}); the cap is {SWEEP_CAP}")
            d = Doc(f"{folder}/{ident}.md", "---\n" + "".join(f"{k}: {v}\n" for k, v in head.items()) + "---\n" + text + "\n")
            d.add_log(st.at, st.agent, "created" + (" as proposed" if proposed else ""))
            st.save_doc(d)
            st.event("new", ident, title)
            if owner not in (st.agent, POOL):
                st.send(owner, f"New {'experiment' if exp else 'task'} for you: {ident}, {title}",
                        f"{st.agent} created it ({kind}, {priority}{', due ' + due if due else ''}). Read {folder}/{ident}.md.", task=ident)
            return ident
        return self.mutate(f"new {title}", fn)

    def lease(self, did, hours, force=False):
        if not 0 < hours <= MAX_LEASE_HOURS:
            raise SystemExit(f"--hours must be more than 0 and at most {MAX_LEASE_HOURS}")

        def fn(st):
            d = st.doc(did)
            s, holder, me = d.get("state"), d.get("holder"), st.agent
            until = hm(st.at + timedelta(hours=hours))
            if s == "leased" and holder == me:
                d.set("lease_until", until)
                d.add_log(st.at, me, f"lease renewed until {until}")
                st.save_doc(d); st.event("renew", did, until=until); self.touch(st)
                return d
            if s == "resolved":
                raise Conflict(f"{did} is resolved ({d.get('resolution')})")
            if s == "submitted":
                raise Conflict(f"{did} is submitted and with its reviewer; the reviewer reopens it")
            if s == "proposed" and me != st.lead:
                raise Conflict(f"{did} is proposed and needs {st.lead}'s agreement first ({st.lead} sets it open)")
            if s == "blocked" and not force:
                raise Conflict(f"{did} is blocked; reopen it, or lease with --force")
            if d.folder == "experiments":
                empty = [n for n in PREREGISTERED if d.section(n).strip().lower() in ("", "_not yet_", "tbd", "_tbd_")]
                if empty:
                    raise Conflict(f"{did} is not pre-registered: fill {', '.join(empty)} first (`workq.py edit {did} --file ...`)")
            taken = None
            if s == "leased":
                lu = parse_time(d.get("lease_until"))
                if lu > st.at:
                    raise Conflict(f"{did} is leased by {holder} until {d.get('lease_until')}")
                if st.at - lu < GRACE:
                    raise Conflict(f"{did}'s lease by {holder} lapsed at {d.get('lease_until')}; it may be taken over from "
                                   f"{hm(lu + GRACE)}, by its owner or {st.lead} only")
                if me not in (d.get("owner"), st.lead):
                    raise Conflict(f"{did}'s lease by {holder} lapsed; only its owner ({d.get('owner')}) or {st.lead} may take it over. Ask {holder}")
                taken = holder
            elif d.get("owner") not in (me, POOL) and me != st.lead and not force:
                raise Conflict(f"{did} is owned by {d.get('owner')}; lease with --force only if they agreed")
            d.set("state", "leased"); d.set("holder", me); d.set("lease_until", until)
            pend = deps_unresolved(st, d)
            text = f"leased until {until}" + (f", taking over from {taken} (lease lapsed)" if taken else "")
            if pend:
                text += f"; {', '.join(pend)} not resolved yet"
                st.notes.append(f"note: {did} depends on {', '.join(pend)}, not resolved yet")
            d.add_log(st.at, me, text)
            st.save_doc(d)
            st.event("lease", did, until=until, takeover=taken)
            if taken and taken != me:
                st.send(taken, f"{me} took over {did}: your lease lapsed at {hm(lu)}",
                        f"{did} ({d.get('title')}) is now leased by {me}. If that is wrong, say so in {me}'s inbox.", task=did)
            self.touch(st)
            return d
        return self.mutate(f"task({did}): lease", fn)

    def _op(self, did, label, apply, who=("holder",)):
        def fn(st):
            d = st.doc(did)
            ok = (("holder" in who and d.get("holder") == st.agent and d.get("state") in ("leased", "submitted", "blocked"))
                  or ("owner" in who and d.get("owner") == st.agent) or ("lead" in who and st.agent == st.lead)
                  or ("reviewer" in who and self.is_reviewer(st, d)) or "anyone" in who)
            if not ok:
                h = d.get("holder")
                raise Conflict(f"{did} ({d.get('state')}{', holder ' + h if h else ''}): {label} is for its " + " or ".join(who))
            out = apply(st, d)
            st.save_doc(d)
            self.touch(st)
            return out
        return self.mutate(f"task({did}): {label}", fn)

    def renew(self, did, hours):
        if not 0 < hours <= MAX_LEASE_HOURS:
            raise SystemExit(f"--hours must be more than 0 and at most {MAX_LEASE_HOURS}")

        def apply(st, d):
            if d.get("state") != "leased":
                raise Conflict(f"{did} is {d.get('state')}")
            until = hm(st.at + timedelta(hours=hours))
            d.set("lease_until", until); d.add_log(st.at, st.agent, f"lease renewed until {until}")
            st.event("renew", did, until=until)
            return d
        return self._op(did, "renew", apply)

    def release(self, did, note):
        def apply(st, d):
            d.set("state", "open"); d.set("holder", ""); d.set("lease_until", "")
            d.add_log(st.at, st.agent, "given back" + (f": {note}" if note else ""))
            st.event("release", did, note)
            return d
        return self._op(did, "release", apply)

    def submit(self, did, note, branch, commit):
        def apply(st, d):
            if d.get("state") != "leased":
                raise Conflict(f"{did} is {d.get('state')}, not leased")
            if d.folder == "experiments":
                miss = missing_result(d)
                if miss:
                    raise Conflict(f"{did}'s ## Result needs lines starting {', '.join(repr(m + ':') for m in miss)} before it is submitted "
                                   f"(Evidence: prediction, double-dummy proxy or played boards; Sample: count and interval; "
                                   f"Revisit if: the conditions under which it is worth trying again). `workq.py edit {did} --file ...`")
            if branch:
                d.set("branch", branch)
            d.set("state", "submitted"); d.set("lease_until", "")
            where = (d.get("branch") or "") + (f" at {commit}" if commit else "")
            d.add_log(st.at, st.agent, "submitted" + (f" ({where})" if where else "") + (f": {note}" if note else ""))
            st.event("submit", did, note, branch=d.get("branch"), commit=commit)
            reviewer = reviewer_of(d, st.lead)
            if reviewer != st.agent:
                st.send(reviewer, f"{did} submitted for your review: {d.get('title')}",
                        f"{note}\n\nBranch: {d.get('branch') or '(none named)'}" + (f", commit {commit}" if commit else "") +
                        f".\n\nAccept: `workq.py resolve {did} --resolution accepted`. Send back: `workq.py reopen {did} --note ...` "
                        f"(add `--same-holder` to return it to {st.agent}).", task=did)
            return d
        return self._op(did, "submit", apply)

    def resolve(self, did, resolution, note):
        def apply(st, d):
            if resolution not in RESOLUTIONS[d.folder]:
                raise Conflict(f"resolution for {d.folder} is one of {', '.join(RESOLUTIONS[d.folder])}")
            holder = d.get("holder")
            d.set("state", "resolved"); d.set("resolution", resolution); d.set("lease_until", "")
            d.add_log(st.at, st.agent, f"resolved: {resolution}" + (f". {note}" if note else ""))
            st.event("resolve", did, note, resolution=resolution)
            for who in {holder, d.get("owner")} - {st.agent, "", POOL}:
                st.send(who, f"{did} resolved ({resolution}): {d.get('title')}", note or f"{st.agent} resolved it.", task=did)
            return d
        return self._op(did, "resolve", apply, who=("reviewer",))

    def reopen(self, did, note, same_holder=False):
        def apply(st, d):
            holder = d.get("holder")
            if same_holder and holder:
                d.set("state", "leased"); d.set("lease_until", hm(st.at + timedelta(hours=MAX_LEASE_HOURS)))
            else:
                d.set("state", "open"); d.set("holder", ""); d.set("lease_until", "")
            d.set("resolution", "")
            d.add_log(st.at, st.agent, ("sent back to " + holder if same_holder and holder else "reopened") + (f": {note}" if note else ""))
            st.event("reopen", did, note)
            if holder and holder != st.agent:
                st.send(holder, f"{did} {'sent back to you' if same_holder else 'reopened'}: {d.get('title')}", note or "(no note)", task=did)
            return d
        return self._op(did, "reopen", apply, who=("reviewer", "owner", "holder"))

    def block(self, did, note):
        def apply(st, d):
            if d.get("state") == "resolved":
                raise Conflict(f"{did} is resolved")
            d.set("state", "blocked"); d.set("lease_until", "")
            d.add_log(st.at, st.agent, f"blocked: {note}")
            st.event("block", did, note)
            for who in {st.lead, d.get("owner")} - {st.agent, POOL}:
                st.send(who, f"{did} blocked: {d.get('title')}", note, task=did)
            return d
        return self._op(did, "block", apply, who=("holder", "owner", "lead"))

    def log(self, did, text):
        def apply(st, d):
            d.add_log(st.at, st.agent, text); st.event("log", did, text)
            return d
        return self._op(did, "log", apply, who=("holder", "owner", "lead", "reviewer"))

    def set_fields(self, did, pairs):
        def apply(st, d):
            changed = []
            for k, v in pairs:
                if k in LIFECYCLE or k == "id":
                    raise Conflict(f"{k} changes only through lease, submit, resolve, reopen, release or block")
                if k == "depends":
                    for dep in split_ids(v):
                        st.doc(dep)
                d.set(k, v); changed.append(f"{k}={v}")
            d.add_log(st.at, st.agent, "set " + ", ".join(changed)); st.event("set", did, ", ".join(changed))
            return d
        return self._op(did, "set", apply, who=("owner", "lead", "holder"))

    def edit(self, did, text):
        """Replace a file's sections (not its lifecycle fields or its log), e.g. to sharpen an experiment."""
        def apply(st, d):
            new = Doc(d.path, text)
            for row in new.head:
                if row[0] not in LIFECYCLE and row[0] != "id" and new.get(row[0]) != d.get(row[0]):
                    d.set(row[0], row[1])
            old_log = d.section("Log")
            body = re.sub(r"^## Log\s*\n.*?(?=^## |\Z)", "", new.body, flags=re.S | re.M | re.I).rstrip("\n")
            d.body = body + "\n\n## Log\n\n" + old_log + "\n"
            d.add_log(st.at, st.agent, "sections edited")
            st.event("edit", did)
            return d
        return self._op(did, "edit", apply, who=("holder", "owner", "lead"))

    # messages
    def send(self, to, subject, body, task, reply_to):
        if to != BROADCAST and not NAME_RE.match(to):
            raise SystemExit(f"invalid recipient {to!r}")

        def fn(st):
            if task:
                st.doc(task)
            self.touch(st)
            return st.send(to, subject, body, task, reply_to)
        return self.mutate(f"message to {to}: {subject[:60]}", fn)

    def mark_read(self, mid=None, all_=False):
        def fn(st):
            path = f"agents/{st.agent}.json"
            a = st.load(path) or dict(name=st.agent)
            if all_:
                mine = [m for m in st.messages() if m["to"] in (st.agent, BROADCAST)]
                a["read_until"] = max([m["stamp"] for m in mine] + [a.get("read_until", "")])
                a["read_ids"] = []
                st.save(path, a)
                return None
            hits = [m for m in st.messages() if m["id"] == mid]
            if not hits:
                raise Conflict(f"no message {mid}")
            if hits[0]["id"] not in a.get("read_ids", []) and hits[0]["stamp"] > a.get("read_until", ""):
                a.setdefault("read_ids", []).append(hits[0]["id"])
                st.save(path, a)
            return hits[0]
        return self.mutate("read " + ("all" if all_ else mid), fn)

    def refresh(self):
        def fn(st):
            st.event("refresh", "STATUS.md")
        return self.mutate("regenerate STATUS.md", fn)

    def issue_refresh(self, create: bool = False, force: bool = True):
        """Rewrite the queue issue's body; copy new comments on open decision issues into the lead's inbox."""
        st = self.snapshot()
        meta = st.load("issues.json") or {}
        stamp = self.store.cache / f"{self.store.git_dir.stem}.issue-stamp"
        if not force and stamp.exists() and datetime.now(timezone.utc).timestamp() - stamp.stat().st_mtime < ISSUE_EVERY.total_seconds():
            return None
        decisions = [i for i in gh("GET", "issues?labels=decision&state=open&per_page=50") if "pull_request" not in i]
        body = queue_summary(st, decisions)
        number = meta.get("queue")
        if not number:
            if not create:
                raise SystemExit("there is no queue issue yet; `workq issue --create` makes it")
            number = gh("POST", "issues", dict(title="Gen 9 queue", body=body))["number"]
            meta["queue"] = number
        else:
            gh("PATCH", f"issues/{number}", dict(body=body))
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        replies = []
        for i in decisions:
            last = meta.get("synced", {}).get(str(i["number"]), 0)
            for c in gh("GET", f"issues/{i['number']}/comments?per_page=100"):
                if c["id"] > last and MARK not in (c.get("body") or ""):
                    replies.append((i, c))
        if replies or not st.load("issues.json") or meta.get("queue") != (st.load("issues.json") or {}).get("queue"):
            def fn(s2):
                m2 = s2.load("issues.json") or {}
                m2["queue"] = number
                for i, c in replies:
                    m2.setdefault("synced", {})[str(i["number"])] = max(c["id"], m2.get("synced", {}).get(str(i["number"]), 0))
                    s2.send(s2.lead, f"Max on #{i['number']}: {i['title'][:80]}",
                            f"{(c.get('body') or '').strip()}\n\n(Copied by {s2.agent} from {c['html_url']}, {c['created_at']}.)",
                            sender="max")
                s2.save("issues.json", m2)
            self.mutate("queue issue: record it and copy replies", fn)
        return dict(number=number, url=f"https://github.com/{GH_REPO}/issues/{number}", replies=len(replies))

    def decision(self, title: str, body: str):
        """The lead raises a decision for Max as its own issue, labelled `decision` and assigned to him."""
        if self.need_agent() != self.lead:
            raise Conflict(f"decision issues are raised by {self.lead} only")
        labels = [l["name"] for l in gh("GET", "labels?per_page=100")]
        if "decision" not in labels:
            gh("POST", "labels", dict(name="decision", color="d93f0b", description="Waiting for Max's decision (raised by the Gen 9 lead)"))
        owner = GH_REPO.split("/")[0]
        i = gh("POST", "issues", dict(title=title if title.startswith("DECISION") else f"DECISION: {title}",
                                     body=f"{MARK}\n{body.strip()}\n\nRaised by {self.lead}. Reply here; the reply is copied to the team's channel.",
                                     labels=["decision"], assignees=[owner]))

        def fn(st):
            m = st.load("issues.json") or {}
            m.setdefault("decisions", []).append(dict(number=i["number"], title=i["title"], raised=hm(st.at)))
            st.save("issues.json", m)
            st.event("decision", f"#{i['number']}", i["title"])
        self.mutate(f"decision raised: #{i['number']}", fn)
        self.issue_refresh(force=True) if (self.snapshot().load("issues.json") or {}).get("queue") else None
        return i

    def decision_close(self, number: int, note: str):
        if self.need_agent() != self.lead:
            raise Conflict(f"decision issues are closed by {self.lead} only")
        gh("POST", f"issues/{number}/comments", dict(body=f"{MARK}\nClosed by {self.lead}: {note}"))
        gh("PATCH", f"issues/{number}", dict(state="closed"))
        self.mutate(f"decision closed: #{number}", lambda st: st.event("decision-close", f"#{number}", note))
        if (self.snapshot().load("issues.json") or {}).get("queue"):
            self.issue_refresh(force=True)

    def job_submit(self, job: dict, replace: bool = False):
        spec = importlib_boxq()
        spec.validate(job)

        def fn(st):
            owner = job["owner"]
            if st.agent not in (owner, st.lead):
                raise Conflict(f"a job is submitted by its owner ({owner}) or {st.lead}")
            if job.get("experiment"):
                st.doc(job["experiment"])
            path = f"boxq/{job['box']}/{job['id']}.json"
            old = st.load(path)
            if old and not replace:
                raise Conflict(f"job {job['id']} exists on {job['box']}; use --replace (the box uses the new spec the next time it starts the job)")
            j = dict(job, submitted=(old or {}).get("submitted") or st.at.strftime("%Y-%m-%dT%H:%M:%SZ"), by=st.agent)
            st.save(path, j)
            st.event("job-submit", f"{job['box']}/{job['id']}", f"priority {job['priority']}, {job['cores']} cores", task=job.get("experiment"))
            return j
        return self.mutate(f"job {job['id']} on {job['box']}", fn)

    def job_cancel(self, box: str, jid: str, note: str):
        def fn(st):
            path = f"boxq/{box}/{jid}.json"
            j = st.load(path)
            if not j:
                raise Conflict(f"no job {jid} on {box}")
            if st.agent not in (j["owner"], st.lead):
                raise Conflict(f"job {jid} is cancelled by its owner ({j['owner']}) or {st.lead}")
            j["state"] = "cancelled"
            st.save(path, j)
            st.event("job-cancel", f"{box}/{jid}", note)
        return self.mutate(f"cancel job {jid} on {box}", fn)

    def fleet(self):
        snap = collect_fleet(self.store, self.clock())
        self.mutate("fleet snapshot", lambda st: st.save("fleet.json", snap))
        return snap

# ---------------------------------------------------------------- command line

def commits_since(store: Store, since: str) -> list[tuple[str, str, str]]:
    """Commits on the branch after `since`, oldest first: (time, author, subject). Fetches enough history to cover it."""
    r = store.git("fetch", "--quiet", "--no-tags", f"--shallow-since={since}", "origin", f"+{store.ref}:{store.local}", check=False)
    if r.returncode != 0:
        store.git("fetch", "--quiet", "--no-tags", "--depth=200", "origin", f"+{store.ref}:{store.local}", check=False)
    out = store.out("log", f"--since={since}", "--reverse", "--format=%cI%x09%an%x09%s", store.local)
    return [tuple(l.split("\t", 2)) for l in out.splitlines() if l.count("\t") >= 2]


def importlib_boxq():
    import importlib.util
    spec = importlib.util.spec_from_file_location("boxq", Path(__file__).resolve().parent / "boxq.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("workq", sys.modules[__name__])
    spec.loader.exec_module(m)
    return m


def seen_file(lg: Ledger, who: str) -> Path:
    return lg.store.cache / f"{lg.store.git_dir.stem}.{lg.store.branch.replace('/', '_')}.{who}.seen"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as", dest="agent"); ap.add_argument("--repo"); ap.add_argument("--channel", dest="channel", help="branch to use (default team/gen9)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("hello"); [p.add_argument(f"--{k}") for k in ("role", "session", "model", "notes")]
    p = sub.add_parser("watch"); p.add_argument("--no-heartbeat", action="store_true")
    sub.add_parser("status"); sub.add_parser("refresh")
    p = sub.add_parser("check"); p.add_argument("--ready", metavar="ID", help="say which executor sections ID lacks")
    p = sub.add_parser("brief"); p.add_argument("id")
    sub.add_parser("export"); sub.add_parser("fleet"); sub.add_parser("next")
    p = sub.add_parser("issue"); p.add_argument("--create", action="store_true"); p.add_argument("--print", action="store_true")
    p = sub.add_parser("job"); p.add_argument("action", choices=["submit", "cancel"]); p.add_argument("arg", help="a job file (submit) or a job id (cancel)")
    p.add_argument("--box"); p.add_argument("--replace", action="store_true"); p.add_argument("--note", default="")
    sub.add_parser("jobs")
    p = sub.add_parser("decision"); p.add_argument("title"); p.add_argument("--body"); p.add_argument("--file")
    p.add_argument("--close", type=int, metavar="NUMBER"); p.add_argument("--note", default="")
    p = sub.add_parser("tasks"); p.add_argument("--owner"); p.add_argument("--state"); p.add_argument("--mine", action="store_true")
    p = sub.add_parser("show"); p.add_argument("id")
    p = sub.add_parser("new"); p.add_argument("title")
    for k in ("area", "kind", "owner", "priority"):
        p.add_argument(f"--{k}", required=True)
    for k in ("due", "depends", "goal", "done-when", "context", "body-file", "id",
              "value", "effort", "probability", "budget", "parent", "explore", "sweep"):
        p.add_argument(f"--{k}")
    p.add_argument("--proposed", action="store_true")
    p = sub.add_parser("lease"); p.add_argument("id"); p.add_argument("--hours", type=float, default=MAX_LEASE_HOURS); p.add_argument("--force", action="store_true")
    p = sub.add_parser("renew"); p.add_argument("id"); p.add_argument("--hours", type=float, default=MAX_LEASE_HOURS)
    p = sub.add_parser("release"); p.add_argument("id"); p.add_argument("--note", required=True)
    p = sub.add_parser("submit"); p.add_argument("id"); p.add_argument("--note", required=True); p.add_argument("--branch"); p.add_argument("--commit")
    p = sub.add_parser("resolve"); p.add_argument("id"); p.add_argument("--resolution", required=True); p.add_argument("--note", default="")
    p = sub.add_parser("reopen"); p.add_argument("id"); p.add_argument("--note", required=True); p.add_argument("--same-holder", action="store_true")
    p = sub.add_parser("block"); p.add_argument("id"); p.add_argument("--note", required=True)
    p = sub.add_parser("log"); p.add_argument("id"); p.add_argument("text")
    p = sub.add_parser("set"); p.add_argument("id"); p.add_argument("pairs", nargs="+")
    p = sub.add_parser("edit"); p.add_argument("id"); p.add_argument("--file", required=True)
    p = sub.add_parser("send"); p.add_argument("to"); p.add_argument("subject"); p.add_argument("--body"); p.add_argument("--file")
    p.add_argument("--task"); p.add_argument("--reply-to")
    p = sub.add_parser("inbox"); p.add_argument("--all", action="store_true"); p.add_argument("--agent", dest="who")
    p = sub.add_parser("read"); p.add_argument("id")
    sub.add_parser("ack")
    a = ap.parse_args(argv)
    lg = Ledger(a.repo, a.channel, a.agent)
    try:
        return run(lg, a)
    except Conflict as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3


def text_of(path: str | None, text: str | None = None) -> str:
    if path:
        return sys.stdin.read() if path == "-" else Path(path).read_text()
    return text or ""


def run(lg: Ledger, a) -> int:
    c = a.cmd
    if c == "hello":
        print(json.dumps(lg.hello(a.role, a.session, a.model, a.notes), indent=1)); return 0
    if c == "new":
        body = text_of(a.body_file) if a.body_file else ""
        if not body and (a.goal or a.done_when or a.context):
            body = f"## Goal\n\n{a.goal or ''}\n\n## Done when\n\n{a.done_when or ''}\n\n## Context\n\n{a.context or ''}\n"
        if a.kind not in KINDS or a.priority not in PRIORITIES:
            raise SystemExit(f"--kind is one of {', '.join(KINDS)}; --priority one of {', '.join(PRIORITIES)}")
        extra = {k: getattr(a, k) for k in ("value", "effort", "probability", "budget", "parent", "explore", "sweep")}
        print(lg.new(a.title, a.area, a.kind, a.owner, a.priority, split_ids(a.depends), a.due, body, a.proposed, a.id, extra)); return 0
    if c == "lease":
        d = lg.lease(a.id, a.hours, a.force); print(f"{a.id} leased by {d.get('holder')} until {d.get('lease_until')}"); return 0
    if c == "renew":
        d = lg.renew(a.id, a.hours); print(f"{a.id} renewed until {d.get('lease_until')}"); return 0
    if c == "release":
        lg.release(a.id, a.note); print(f"{a.id} given back, open"); return 0
    if c == "submit":
        lg.submit(a.id, a.note, a.branch, a.commit); print(f"{a.id} submitted"); return 0
    if c == "resolve":
        lg.resolve(a.id, a.resolution, a.note); print(f"{a.id} resolved: {a.resolution}"); return 0
    if c == "reopen":
        d = lg.reopen(a.id, a.note, a.same_holder); print(f"{a.id} {d.get('state')}"); return 0
    if c == "block":
        lg.block(a.id, a.note); print(f"{a.id} blocked"); return 0
    if c == "log":
        lg.log(a.id, a.text); print("logged"); return 0
    if c == "set":
        pairs = []
        for kv in a.pairs:
            k, sep, v = kv.partition("=")
            if not sep:
                raise SystemExit(f"set takes KEY=VALUE, got {kv!r}")
            pairs.append((k.strip(), v.strip()))
        lg.set_fields(a.id, pairs); print("set"); return 0
    if c == "edit":
        lg.edit(a.id, Path(a.file).read_text()); print("edited"); return 0
    if c == "send":
        body = text_of(a.file, a.body)
        if not body.strip():
            raise SystemExit("--body or --file is required")
        print(lg.send(a.to, a.subject, body, a.task, a.reply_to)); return 0
    if c == "read":
        m = lg.mark_read(a.id)
        print(f"To {m['to']}, from {m['from']}, {m['stamp']}\n\n{m['body']}"); return 0
    if c == "ack":
        lg.mark_read(all_=True); print("all read"); return 0
    if c == "job":
        if a.action == "submit":
            job = json.loads(text_of(a.arg))
            if a.box:
                job["box"] = a.box
            j = lg.job_submit(job, a.replace)
            print(f"job {j['id']} queued on {j['box']} (priority {j['priority']}, {j['cores']} cores)"); return 0
        if not a.box:
            raise SystemExit("--box is required to cancel")
        lg.job_cancel(a.box, a.arg, a.note); print(f"job {a.arg} on {a.box} cancelled"); return 0
    if c == "issue":
        if a.print:
            st = lg.snapshot(); sys.stdout.write(queue_summary(st, [])); return 0
        r = lg.issue_refresh(create=a.create)
        print(f"queue issue {r['url']} rewritten; {r['replies']} new repl{'y' if r['replies'] == 1 else 'ies'} copied to {lg.lead}"); return 0
    if c == "decision":
        if a.close:
            lg.decision_close(a.close, a.note or a.title); print(f"closed #{a.close}"); return 0
        body = text_of(a.file, a.body)
        if not body.strip():
            raise SystemExit("--body or --file is required")
        i = lg.decision(a.title, body); print(f"#{i['number']} {i['html_url']}"); return 0
    if c == "fleet":
        snap = lg.fleet(); print("\n".join(render_fleet(snap, {}))); return 0

    st = lg.snapshot()
    if not st.files:
        raise SystemExit(f"branch {lg.store.branch} does not exist")
    if c == "status":
        sys.stdout.write(render_status(st).decode()); return 0
    if c == "jobs":
        print("\n".join(render_queues(st)) or "no box queue yet"); return 0
    if c == "refresh":
        lg.refresh(); print("STATUS.md regenerated"); return 0
    if c == "brief":
        sys.stdout.write(brief_text(st, st.doc(a.id), lg.store.branch)); return 0
    if c == "check" and a.ready:
        miss = missing_ready(st.doc(a.ready))
        print(f"{a.ready} is executor-ready" if not miss else f"{a.ready} lacks: {', '.join(miss)}"); return 1 if miss else 0
    if c == "check":
        _, errors = st.docs()
        print("\n".join(errors) if errors else "every header is well formed"); return 1 if errors else 0
    if c == "export":
        docs, _ = st.docs()
        print(json.dumps(dict(agents=st.agents(), docs={k: dict((r[0], r[1]) for r in d.head) for k, d in docs.items()},
                              messages=st.messages()), indent=1)); return 0
    if c == "show":
        d = st.doc(a.id); sys.stdout.write(d.render().decode())
        pend = deps_unresolved(st, d)
        if pend:
            print(f"\n(depends on {', '.join(pend)}, not resolved)")
        return 0
    if c in ("tasks", "next"):
        docs, _ = st.docs()
        me = lg.agent
        ds = list(docs.values())
        if c == "next":
            ds = [d for d in ds if d.get("state") == "open" and (d.get("owner") in (me, POOL) or me == lg.lead)]
        else:
            if a.state:
                ds = [d for d in ds if d.get("state") == a.state]
            elif not a.mine:
                ds = [d for d in ds if d.get("state") != "resolved"]
            if a.owner:
                ds = [d for d in ds if d.get("owner") == a.owner]
            if a.mine:
                ds = [d for d in ds if me in (d.get("owner"), d.get("holder"))]
        rank = {p: i for i, p in enumerate(PRIORITIES)}
        # within a priority class: value for effort when both are given (best first), then due date
        ds.sort(key=lambda d: (rank.get(d.get("priority"), 9), -(score(d) if score(d) is not None else -1e18), d.get("due") or "9", d.get("id")))
        for d in ds:
            n = note_for(st, d, st.at)
            print(f"{d.get('id'):7} {d.get('priority'):6} {d.get('state'):9} {d.get('owner'):5} {d.get('holder'):5} "
                  f"{short(d.get('due')):11} {d.get('title')[:70]}" + (f"  [{n}]" if n else ""))
        if not ds:
            print("nothing")
        return 0
    if c == "inbox":
        who = a.who or lg.need_agent()
        rows = [m for m in st.messages() if m["to"] in (who, BROADCAST)] if a.all else st.unread(who)
        for m in sorted(rows, key=lambda m: m["id"]):
            print(f"{m['id']}\n    to {m['to']}, from {m['from']}: {m['subject'][:140]}")
        if not rows:
            print("no unread messages" if not a.all else "no messages")
        return 0
    if c == "watch":
        me = lg.need_agent()
        sf = seen_file(lg, me)
        since = sf.read_text().strip() if sf.exists() else ""
        events = [json.loads(l) for p in st.paths("log/") for l in st.get(p).decode().splitlines() if l.strip()]
        new = [e for e in events if e["at"] > since and e["by"] != me]
        docs, errors = st.docs()
        mine = {k for k, d in docs.items() if me in (d.get("owner"), d.get("holder"), reviewer_of(d, lg.lead))}
        mine |= {f"{box}/{jid}" for box, q in box_queues(st).items() for jid, j in q["jobs"].items() if j.get("owner") == me}
        print(f"{lg.store.branch} at {st.at:%Y-%m-%d %H:%M} UTC; {len(new)} change(s) by others since {since or 'the start'}")
        for e in new[-50:]:
            star = "*" if e.get("target", "").startswith(f"{me}/") or e.get("target") in mine or e.get("task") in mine else " "
            print(f" {star} {short(e['at'])} {e['by']:5} {e['op']:8} {e.get('target', '')}" + (f": {e['note'][:90]}" if e.get("note") else ""))
        hand = commits_since(lg.store, since) if since else []
        hand = [c for c in hand if not c[1].endswith("(workq)")]  # changes made with workq are listed above
        if hand:
            print(f"{len(hand)} commit(s) made by hand since then:")
            for when, _, subject in hand[-40:]:
                print(f"   {short(when.replace('+00:00', 'Z'))} {subject[:110]}")
        unread = st.unread(me)
        print(f"unread for {me}: {len(unread)}")
        for m in unread:
            print(f"   {m['id']}  ({m['from']}) {m['subject'][:110]}")
        for d in docs.values():
            if d.get("holder") == me and d.get("state") == "leased":
                left = parse_time(d.get("lease_until")) - st.at
                if left < timedelta(minutes=45):
                    print(f"   your lease on {d.get('id')} ends {d.get('lease_until')}: renew, submit or release it")
            if d.get("state") == "submitted" and me == reviewer_of(d, lg.lead):
                print(f"   {d.get('id')} waits for your review ({d.get('holder')}): {d.get('title')[:70]}")
        if errors:
            print("malformed: " + "; ".join(errors))
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(st.at.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if not a.no_heartbeat and me in st.agents():
            lg.mutate(f"heartbeat {me}", lambda s: lg.touch(s))
        return 0
    raise SystemExit(f"unknown command {c}")


if __name__ == "__main__":
    sys.exit(main())
