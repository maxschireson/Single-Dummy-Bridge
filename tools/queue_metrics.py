#!/usr/bin/env python3
"""Queue metrics for team/gen9 (task G9-W4): are there too few thinkers or too few executors?

Reads a checkout of the channel: every task's and experiment's `## Log` (the whole history, from before workq
existed), the message files, the agents' read state, the box job files, and `git log` of the checkout for when each
message was read. Writes a markdown page.

    python3 tools/queue_metrics.py                          # the page for the checkout this file is in, to stdout
    python3 tools/queue_metrics.py --out reports/queue-metrics.md --json reports/queue-metrics.json
    python3 tools/queue_metrics.py --now 2026-11-12T10:00Z  # as of a time (default: now)
    python3 tools/queue_metrics.py --notes reports/queue-metrics-notes.md --out reports/queue-metrics.md

What it measures, for every task and experiment (docs/gen9/workplan.md, "How many thinkers and how many executors"):
time open before a lease, lease length against its time box, leases that ran past their end, work given back,
time submitted before review, who reviewed; by owner, kind and reviewer; the first 90 minutes of the channel apart
from the rest. And the lead's inbox: messages waiting, and how long messages waited to be read.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

LINE = re.compile(r"^- (\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?Z) (\S+?): (.*)$")
UNTIL = re.compile(r"until (\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?Z)")
VERDICT = re.compile(r"^(reviewed|accepted|rejected|adopted|dropped)\b")   # verdicts written by hand before workq
BOX = timedelta(hours=4)          # the longest lease; a lease written without an end (before workq) gets this
FIRST = timedelta(minutes=90)     # g9: the first 90 minutes are a separate data point


def ts(s: str) -> datetime:
    s = s.rstrip("Z")
    fmt = "%Y-%m-%dT%H:%M:%S" if s.count(":") == 2 else "%Y-%m-%dT%H:%M"
    return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)


def fmt(t: datetime | None) -> str:
    return "" if t is None else t.strftime("%H:%M")


def mins(d: timedelta | None) -> float | None:
    return None if d is None else round(d.total_seconds() / 60, 1)


def header(text: str) -> dict:
    out = {}
    if text.startswith("---"):
        for line in text.split("---", 2)[1].splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    return out


def log_lines(text: str) -> list[tuple[datetime, str, str]]:
    out, on = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            on = line.strip() == "## Log"
            continue
        m = LINE.match(line.strip()) if on else None
        if m:
            out.append((ts(m.group(1)), m.group(2), m.group(3)))
    return out


def history(did: str, head: dict, lines: list, now: datetime) -> dict:
    """One document's history as open periods, leases and reviews."""
    d = dict(id=did, kind=head.get("kind") or ("experiment" if did.startswith("E") else "?"), owner=head.get("owner", ""),
             area=head.get("area", ""), state=head.get("state", ""), created=None, proposed=False,
             waits=[], leases=[], reviews=[], given_back=0, sent_back=0, blocked=0)
    open_since = None        # the time the document became leasable and nobody held it
    lease = None             # the lease in force
    review = None            # the submission waiting for review

    def end_lease(t, how):
        nonlocal lease
        if lease:
            lease.update(end=t, how=how, over=max(timedelta(0), t - lease["until"]))
            d["leases"].append(lease)
            lease = None

    for t, who, text in lines:
        low = text.lower()
        if d["created"] is None and (low.startswith("created") or low.startswith("registered")):
            d["created"] = t
            d["proposed"] = "proposed" in low
            if not d["proposed"]:
                open_since = t
        elif low.startswith("set ") and "state=open" in low and open_since is None and lease is None:
            open_since = t
        elif low.startswith("leased") or (low.startswith("lease ") and "until" in low and "renew" not in low):
            if lease:                                    # taken over, or leased again by its holder
                end_lease(t, "taken over" if who != lease["holder"] else "leased again")
            if open_since is not None:
                d["waits"].append(dict(start=open_since, end=t, by=who))
                open_since = None
            m = UNTIL.search(text)
            lease = dict(holder=who, start=t, until=ts(m.group(1)) if m else t + BOX, box=(ts(m.group(1)) - t) if m else BOX)
        elif "renewed until" in low and lease:
            lease["until"] = ts(UNTIL.search(text).group(1))
            lease["renewals"] = lease.get("renewals", 0) + 1
        elif low.startswith("given back"):
            end_lease(t, "given back")
            d["given_back"] += 1
            open_since = t
        elif low.startswith("submitted"):
            end_lease(t, "submitted")
            review = dict(start=t, by=who)
        elif low.startswith("resolved") or (review and who != review["by"] and VERDICT.match(low)):
            end_lease(t, "resolved while leased")
            if review:
                review.update(end=t, reviewer=who, outcome=text.split(":", 1)[1].strip().split(".")[0] if low.startswith("resolved") and ":" in text
                              else (re.search(r"accepted|rejected|adopted|dropped", low) or VERDICT.match(low)).group(0))
                d["reviews"].append(review)
                review = None
            open_since = None
        elif low.startswith("reopened") or low.startswith("sent back"):
            if review:
                review.update(end=t, reviewer=who, outcome="sent back")
                d["reviews"].append(review)
                review = None
            d["sent_back"] += 1
            if low.startswith("reopened"):
                open_since = t
        elif low.startswith("blocked"):
            end_lease(t, "blocked")
            d["blocked"] += 1
            open_since = None
    if lease:
        lease.update(end=None, how="held now", over=max(timedelta(0), now - lease["until"]))
        d["leases"].append(lease)
    if open_since is not None and d["state"] in ("open", ""):
        d["waits"].append(dict(start=open_since, end=None, by=None))
    if review:
        d["reviews"].append(dict(review, end=None, reviewer=None, outcome="waiting"))
    return d


def read_times(root: Path) -> dict[tuple[str, str], datetime]:
    """{(agent, message id): when it was read}, from the checkout's commit messages ('<agent>: read <id>' or
    '<agent>: read all', which reads everything in that agent's inbox up to then)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "log", "--reverse", "--format=%aI|%s"], capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    got = {}
    inbox = {p.name: sorted(m.stem for m in p.glob("*.md")) for p in (root / "inbox").iterdir() if p.is_dir()} if (root / "inbox").exists() else {}
    for line in out.splitlines():
        at, _, subject = line.partition("|")
        m = re.match(r"^(\S+): read (.+)$", subject)
        if not m:
            continue
        t = datetime.fromisoformat(at).astimezone(timezone.utc)
        agent, what = m.group(1), m.group(2).strip()
        if what == "all":
            for mid in inbox.get(agent, []):
                if (agent, mid) not in got and msg_time(mid) <= t:
                    got[(agent, mid)] = t
        else:
            for mid in inbox.get(agent, []):
                if mid.startswith(what) and (agent, mid) not in got:
                    got[(agent, mid)] = t
    return got


def msg_time(mid: str) -> datetime:
    return datetime.strptime(mid[:14], "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc)


def collect(root: Path, now: datetime | None = None) -> dict:
    docs, latest = [], None
    raw = []
    for folder in ("tasks", "experiments"):
        for p in sorted((root / folder).glob("*.md")):
            text = p.read_text()
            lines = log_lines(text)
            raw.append((p.stem, header(text), lines))
            if lines:
                latest = max(latest or lines[-1][0], max(t for t, _, _ in lines))
    if now is None:
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    for did, head, lines in raw:
        lines = [x for x in lines if x[0] <= now]       # as of `now`: later lines are not seen yet
        docs.append(history(did, head, lines, now))
    start = min((d["created"] for d in docs if d["created"]), default=now)
    # messages
    reads = read_times(root)
    msgs = []
    for p in sorted((root / "inbox").glob("*/*.md")) if (root / "inbox").exists() else []:
        mid, to = p.stem, p.parent.name
        sender = mid[15:].split("-", 1)[0]
        msgs.append(dict(id=mid, to=to, sender=sender, at=msg_time(mid), read=reads.get((to, mid))))
    agents = {}
    for p in sorted((root / "agents").glob("*.json")) if (root / "agents").exists() else []:
        a = json.loads(p.read_text())
        agents[a.get("name", p.stem)] = a
    for m in msgs:                                       # a message read by state but with no read commit found
        a = agents.get(m["to"]) or {}
        if m["read"] is None and (m["id"][:14] <= a.get("read_until", "") or m["id"] in a.get("read_ids", [])):
            m["read"] = "yes, time unknown"
    jobs = []
    for p in sorted((root / "boxq").glob("*/*.json")) if (root / "boxq").exists() else []:
        if p.name != "status.json":
            j = json.loads(p.read_text())
            jobs.append(dict(id=j.get("id"), box=p.parent.name, owner=j.get("owner"), cores=j.get("cores"), submitted=j.get("submitted"),
                             target=(j.get("progress") or {}).get("target"), state=j.get("state", "queued")))
    status = {p.parent.name: json.loads(p.read_text()) for p in (root / "boxq").glob("*/status.json")} if (root / "boxq").exists() else {}
    return dict(now=now, start=start, docs=docs, msgs=msgs, agents=agents, jobs=jobs, box_status=status)


def stats(values: list[float]) -> str:
    v = sorted(x for x in values if x is not None)
    if not v:
        return "—"
    med = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
    return f"{len(v)}: median {med:.0f}, max {v[-1]:.0f}"


def period(t: datetime, start: datetime) -> str:
    return "first 90 min" if t < start + FIRST else "after"


def render(c: dict, notes: str | None = None) -> str:
    now, start, docs = c["now"], c["start"], c["docs"]
    L = [f"# Queue metrics, team/gen9, {now:%d %b %Y %H:%M} UTC", "",
         f"From the channel's history: {len(docs)} tasks and experiments, the first created at {fmt(start)} UTC. "
         f"The first 90 minutes ({fmt(start)} to {fmt(start + FIRST)}) are counted apart from the rest. "
         "Times in minutes. Made by `tools/queue_metrics.py` (G9-W4).", ""]
    if notes:
        L += [notes.strip(), ""]

    # 1. waiting for a lease
    waits = [(d, w) for d in docs for w in d["waits"]]
    L += ["## 1. Open and unleased", "",
          "Time from a task being open (created, opened from proposed, given back, reopened) to its next lease.", "",
          "| Owner | Waits, first 90 min | Waits, after | Open now, unleased |", "| --- | --- | --- | --- |"]
    owners = sorted({d["owner"] for d in docs})
    for o in owners:
        f = [mins(w["end"] - w["start"]) for d, w in waits if d["owner"] == o and w["end"] and period(w["start"], start) == "first 90 min"]
        a = [mins(w["end"] - w["start"]) for d, w in waits if d["owner"] == o and w["end"] and period(w["start"], start) == "after"]
        n = [f"{d['id']} {mins(now - w['start']):.0f}" for d, w in waits if d["owner"] == o and w["end"] is None]
        L.append(f"| {o} | {stats(f)} | {stats(a)} | {', '.join(n) or '—'} |")
    long = [(d, w) for d, w in waits if (w["end"] or now) - w["start"] > timedelta(hours=1)]
    L += ["", "Open more than an hour before a lease (the workplan's signal to add executors): " +
          (", ".join(f"{d['id']} ({d['owner']}, {mins((w['end'] or now) - w['start']):.0f}{'' if w['end'] else ', still open'})" for d, w in long) or "none") + ".", ""]

    # 2. leases
    leases = [(d, l) for d in docs for l in d["leases"]]
    L += ["## 2. Leases", "", "Length of each lease that has ended (start to submit, give-back or block), against its time box.", "",
          "| Holder | Leases | Ended | Median length | Longest | Ran past its end | Given back | Renewals |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for h in sorted({l["holder"] for _, l in leases}):
        mine = [l for _, l in leases if l["holder"] == h]
        ended = [mins(l["end"] - l["start"]) for l in mine if l["end"]]
        past = [l for l in mine if l["over"] > timedelta(0)]
        gb = sum(1 for l in mine if l["how"] == "given back")
        s = sorted(ended)
        med = (s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2) if s else None
        L.append(f"| {h} | {len(mine)} | {len(ended)} | {'—' if med is None else f'{med:.0f}'} | {'—' if not s else f'{s[-1]:.0f}'} | "
                 f"{len(past)} | {gb} | {sum(l.get('renewals', 0) for l in mine)} |")
    ended_all = [l for _, l in leases if l["end"]]
    share = [((l["end"] - l["start"]) / l["box"]) for l in ended_all if l["box"].total_seconds() > 0]
    L += ["", f"Of {len(ended_all)} ended leases, {sum(1 for x in share if x <= 0.25)} used a quarter of their time box or less and "
          f"{sum(1 for x in share if x > 1)} ran past it. Leases held now: " +
          (", ".join(f"{d['id']} {l['holder']} ({mins(now - l['start']):.0f} of {mins(l['box']):.0f}{', past its end' if l['over'] > timedelta(0) else ''})"
                     for d, l in leases if l["end"] is None) or "none") + ".", ""]
    past = [(d, l) for d, l in leases if l["over"] > timedelta(0)]
    if past:
        L += ["Leases that ran past their end (the workplan's signal that tasks are too big): " +
              ", ".join(f"{d['id']} {l['holder']} by {mins(l['over']):.0f}" for d, l in past) + ".", ""]

    # 3. review
    revs = [(d, r) for d in docs for r in d["reviews"]]
    L += ["## 3. Waiting for review", "", "Time from submission to a verdict (resolved or sent back), by reviewer and by period.", "",
          "| Reviewer | Kind | Reviews, first 90 min | Reviews, after | Sent back |", "| --- | --- | --- | --- | ---: |"]
    keys = sorted({(r["reviewer"], d["kind"]) for d, r in revs if r["reviewer"]})
    for rv, kind in keys:
        f = [mins(r["end"] - r["start"]) for d, r in revs if r["reviewer"] == rv and d["kind"] == kind and period(r["start"], start) == "first 90 min"]
        a = [mins(r["end"] - r["start"]) for d, r in revs if r["reviewer"] == rv and d["kind"] == kind and period(r["start"], start) == "after"]
        sb = sum(1 for d, r in revs if r["reviewer"] == rv and d["kind"] == kind and r["outcome"] == "sent back")
        L.append(f"| {rv} | {kind} | {stats(f)} | {stats(a)} | {sb} |")
    waiting = [(d, r) for d, r in revs if r["end"] is None]
    L += ["", "Waiting now: " + (", ".join(f"{d['id']} ({d['kind']}, from {r['by']}, {mins(now - r['start']):.0f})" for d, r in waiting) or "nothing") + ".", ""]
    over2 = [(d, r) for d, r in revs if (r["end"] or now) - r["start"] > timedelta(hours=2)]
    L += ["Unreviewed for more than two hours (the workplan's signal that a lead or the architect is the bottleneck): " +
          (", ".join(f"{d['id']} {mins((r['end'] or now) - r['start']):.0f}" for d, r in over2) or "none") + ".", ""]
    by_hour = defaultdict(Counter)
    for d, r in revs:
        if r["end"]:
            by_hour[r["reviewer"]][r["end"].strftime("%H:00")] += 1
    hours = sorted({h for c in by_hour.values() for h in c})
    if hours:
        L += ["Verdicts by hour (UTC):", "", "| Reviewer | " + " | ".join(hours) + " |", "| --- |" + " ---: |" * len(hours)]
        for rv in sorted(by_hour):
            L.append(f"| {rv} | " + " | ".join(str(by_hour[rv].get(h, 0)) for h in hours) + " |")
        L.append("")

    # 4. inboxes
    msgs = c["msgs"]
    L += ["## 4. Messages", "", "Messages received, how long they waited to be read (a read commit's time), and how many are unread now.", "",
          "| Agent | Received | Read, wait (median, max) | Unread now | Oldest unread |", "| --- | ---: | --- | ---: | --- |"]
    for a in sorted({m["to"] for m in msgs} - {"all"}):
        mine = [m for m in msgs if m["to"] == a]
        w = [mins(m["read"] - m["at"]) for m in mine if isinstance(m["read"], datetime)]
        ag = c["agents"].get(a) or {}
        if not w and not ag.get("read_until") and not ag.get("read_ids"):
            L.append(f"| {a} | {len(mine)} | keeps no read state | — | — |")
            continue
        unread = [m for m in mine if m["read"] is None]
        old = min((m["at"] for m in unread), default=None)
        L.append(f"| {a} | {len(mine)} | {stats(w)} | {len(unread)} | {fmt(old)}{'' if old is None else f' ({mins(now - old):.0f} min)'} |")
    bc = [m for m in msgs if m["to"] == "all"]
    if bc:
        L.append(f"| all (to everyone) | {len(bc)} | — | — | — |")
    seen = {a: v.get("last_seen") for a, v in c["agents"].items()}
    L += ["", "Last seen (agents/*.json): " + ", ".join(f"{a} {(s or '?')[11:16]}" for a, s in sorted(seen.items())) + ".", ""]

    # 5. boxes
    jobs = c["jobs"]
    L += ["## 5. Boxes", ""]
    if not c["box_status"]:
        L += [f"No box serves the queue yet. Jobs waiting for one: {len(jobs)} ({sum(j['cores'] or 0 for j in jobs)} cores asked, "
              f"{sum(j['target'] or 0 for j in jobs):,} boards), submitted from {min((j['submitted'] or '' for j in jobs), default='')[11:16] or '—'} UTC. "
              "The workplan's box signals (idle boxes while experiments wait; full boxes) start when the queue runs.", ""]
    else:
        for box, s in sorted(c["box_status"].items()):
            J = s.get("jobs", {})
            L.append(f"- {box}: {sum(1 for v in J.values() if v.get('state') == 'running')} running, "
                     f"{sum(1 for v in J.values() if v.get('state') == 'waiting')} waiting, cores {s.get('cores')}, updated {str(s.get('at', ''))[11:16]}.")
        L.append("")
    return "\n".join(L) + "\n"


def to_json(c: dict) -> dict:
    def conv(x):
        if isinstance(x, datetime):
            return x.strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(x, timedelta):
            return mins(x)
        if isinstance(x, dict):
            return {k: conv(v) for k, v in x.items()}
        if isinstance(x, list):
            return [conv(v) for v in x]
        return x
    return conv(dict(now=c["now"], start=c["start"], docs=c["docs"], messages=c["msgs"], jobs=c["jobs"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent, help="a checkout of team/gen9")
    ap.add_argument("--now", help="as of this time (UTC, e.g. 2026-11-12T10:00Z)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--notes", type=Path, help="a hand-written reading of the numbers, placed after the first paragraph")
    a = ap.parse_args(argv)
    c = collect(a.root, ts(a.now) if a.now else None)
    text = render(c, a.notes.read_text() if a.notes else None)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text)
    else:
        sys.stdout.write(text)
    if a.json:
        a.json.write_text(json.dumps(to_json(c), indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
