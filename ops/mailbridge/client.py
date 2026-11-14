#!/usr/bin/env python3
"""Session side of mailbridge: read and send mail through the encrypted branch mail/coord.

  client.py keys                       make this session's key and certificate (once)
  client.py init                       create branch mail/coord with the session certificate
  client.py fetch                      decrypt new inbox items; print a JSON summary of each
  client.py show <name>                print one received message (headers and text)
  client.py send --to A [--cc B] --subject S --text-file F [--html-file H] [--in-reply-to ID]
                 [--attach PATH ...] [--wait 180]
  client.py secret < "ADDRESS APP_PASSWORD"    deliver the mailbox secret to the box, encrypted
  client.py status                     the box's status and receipts not yet seen

State lives in ~/.mailcoord (override with MAILCOORD_HOME).
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
from email import policy
from email.parser import BytesParser
from email.utils import make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mailbridge import BRANCH, make_keys, run, seal, unseal, utc  # noqa: E402

HOME = Path(os.environ.get("MAILCOORD_HOME", Path.home() / ".mailcoord"))
REPO_URL = os.environ.get("MAILCOORD_REPO", "https://github.com/maxschireson/single-dummy-bridge")
KEY, CERT = HOME / "session.key", HOME / "session.pem"
REPO = HOME / "repo"
INBOX = HOME / "inbox"
SENT = HOME / "sent"
SEEN = HOME / "seen.json"


def git(*args, check=True, cwd=REPO):
    return run(["git", *args], cwd=cwd, check=check)


def sync() -> None:
    if not (REPO / ".git").exists():
        run(["git", "clone", "-q", "--single-branch", "--branch", BRANCH, REPO_URL, str(REPO)])
    git("fetch", "-q", "origin", BRANCH)
    ahead = git("rev-list", "--count", f"origin/{BRANCH}..HEAD").stdout.strip()
    if ahead == "0":
        git("reset", "-q", "--hard", f"origin/{BRANCH}")
    else:
        git("rebase", "-q", f"origin/{BRANCH}")


def publish(message: str) -> None:
    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        return
    git("commit", "-q", "-m", message)
    for attempt in range(6):
        if git("push", "-q", "origin", f"HEAD:{BRANCH}", check=False).returncode == 0:
            return
        time.sleep(2 + 3 * attempt)
        sync()
    raise SystemExit("push failed six times")


def seen() -> dict:
    return json.loads(SEEN.read_text()) if SEEN.exists() else {"inbox": [], "receipts": []}


def cmd_keys(_a) -> None:
    HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    if KEY.exists():
        print(f"exists: {CERT}")
        return
    make_keys(KEY, CERT, "mailbridge-session")
    print(f"made {CERT}")


def cmd_init(_a) -> None:
    """Create the orphan branch with a README and the session certificate."""
    if not CERT.exists():
        raise SystemExit("run keys first")
    tmp = HOME / "init"
    run(["rm", "-rf", str(tmp)])
    tmp.mkdir(parents=True)
    git("init", "-q", "-b", BRANCH, cwd=tmp)
    (tmp / "certs").mkdir()
    (tmp / "certs" / "session.pem").write_bytes(CERT.read_bytes())
    (tmp / "README.md").write_text(
        "# mail/coord: an encrypted mail channel\n\n"
        "A channel branch, like `box/*`: never merge it into source. Written by `ops/mailbridge` on branch\n"
        "`perf/stu-20261114`. The box relays one mailbox; the session reads and sends through this branch.\n\n"
        "- `certs/`: public certificates of the box and the session.\n"
        "- `inbox/*.cms`: received messages, signed by the box and encrypted to the session.\n"
        "- `outbox/*.cms`: messages to send, signed by the session and encrypted to the box.\n"
        "- `sent/*.json`, `status.json`: receipts and the box's status, with no addresses or text.\n"
        "- `secret/secret.cms`: the mailbox credentials, encrypted to the box.\n")
    git("add", "-A", cwd=tmp)
    git("commit", "-q", "-m", "mail/coord: channel branch with the session certificate", cwd=tmp)
    git("remote", "add", "origin", REPO_URL, cwd=tmp)
    r = git("push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=tmp, check=False)
    if r.returncode:
        raise SystemExit(r.stderr.decode())
    run(["rm", "-rf", str(tmp)])
    sync()
    print("branch created")


def box_cert() -> Path:
    p = REPO / "certs" / "box.pem"
    if not p.exists():
        raise SystemExit("the box has not published its certificate yet")
    return p


def summary(raw: bytes) -> dict:
    m = BytesParser(policy=policy.default).parsebytes(raw)
    body = m.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body is not None else ""
    return {"from": str(m["From"]), "to": str(m["To"]), "cc": str(m["Cc"] or ""), "date": str(m["Date"]),
            "subject": str(m["Subject"]), "message_id": str(m["Message-ID"]),
            "references": str(m["References"] or ""), "preview": text.strip()[:600]}


def cmd_fetch(_a) -> None:
    sync()
    s = seen()
    INBOX.mkdir(parents=True, exist_ok=True)
    new = []
    for f in sorted((REPO / "inbox").glob("*.cms")) if (REPO / "inbox").exists() else []:
        if f.name in s["inbox"]:
            continue
        raw = unseal(f.read_bytes(), CERT, KEY, box_cert())
        out = INBOX / (f.stem + ".eml")
        out.write_bytes(raw)
        new.append({"name": f.stem, **summary(raw)})
        s["inbox"].append(f.name)
    receipts = []
    for f in sorted((REPO / "sent").glob("*.json")) if (REPO / "sent").exists() else []:
        if f.name in s["receipts"]:
            continue
        receipts.append(json.loads(f.read_text()))
        s["receipts"].append(f.name)
    SEEN.write_text(json.dumps(s, indent=1))
    status = json.loads((REPO / "status.json").read_text()) if (REPO / "status.json").exists() else None
    print(json.dumps({"new_messages": new, "new_receipts": receipts, "box_status": status}, indent=1))


def cmd_show(a) -> None:
    raw = (INBOX / (a.name.removesuffix(".eml") + ".eml")).read_bytes()
    m = BytesParser(policy=policy.default).parsebytes(raw)
    for h in ("From", "To", "Cc", "Date", "Subject", "Message-ID", "In-Reply-To", "References"):
        if m[h]:
            print(f"{h}: {m[h]}")
    body = m.get_body(preferencelist=("plain", "html"))
    print()
    print(body.get_content() if body is not None else "(no text body)")
    atts = [p.get_filename() for p in m.iter_attachments()]
    if atts:
        print("\nAttachments:", ", ".join(map(str, atts)))
    if a.save_attachments:
        d = INBOX / (a.name + ".files")
        d.mkdir(exist_ok=True)
        for p in m.iter_attachments():
            (d / Path(p.get_filename() or "part").name).write_bytes(p.get_content() if isinstance(
                p.get_content(), bytes) else str(p.get_content()).encode())
        print("saved to", d)


def cmd_send(a) -> None:
    sync()
    oid = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + os.urandom(3).hex()
    req = {"id": oid, "to": a.to, "cc": a.cc or [], "subject": a.subject,
           "text": Path(a.text_file).read_text(),
           "message_id": make_msgid(domain=a.domain)}
    if a.html_file:
        req["html"] = Path(a.html_file).read_text()
    if a.in_reply_to:
        req["in_reply_to"] = a.in_reply_to
        req["references"] = a.references or a.in_reply_to
    atts = []
    for path in a.attach or []:
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        atts.append({"filename": Path(path).name, "mime": mime,
                     "b64": base64.b64encode(Path(path).read_bytes()).decode()})
    if atts:
        req["attachments"] = atts
    data = json.dumps(req).encode()
    out = REPO / "outbox"
    out.mkdir(exist_ok=True)
    (out / f"{oid}.cms").write_bytes(seal(data, CERT, KEY, box_cert()))
    SENT.mkdir(parents=True, exist_ok=True)
    (SENT / f"{oid}.json").write_text(json.dumps({k: v for k, v in req.items() if k != "attachments"}, indent=1))
    publish(f"session: outbox {oid}")
    print(json.dumps({"queued": oid, "message_id": req["message_id"]}))
    if a.wait:
        deadline = time.time() + a.wait
        while time.time() < deadline:
            time.sleep(15)
            sync()
            r = REPO / "sent" / f"{oid}.json"
            if r.exists():
                print(r.read_text())
                return
        print(json.dumps({"receipt": None, "note": f"no receipt after {a.wait} s; check status later"}))


def cmd_secret(_a) -> None:
    sync()
    data = sys.stdin.read().strip().encode()
    if len(data.split()) < 2:
        raise SystemExit("expected: ADDRESS APP_PASSWORD")
    d = REPO / "secret"
    d.mkdir(exist_ok=True)
    (d / "secret.cms").write_bytes(seal(data, CERT, KEY, box_cert()))
    publish("session: mailbox secret for the box (encrypted)")
    print("delivered")


def cmd_status(_a) -> None:
    sync()
    st = REPO / "status.json"
    print(st.read_text() if st.exists() else "no status yet")
    out = {f.stem for f in (REPO / "outbox").glob("*.cms")} if (REPO / "outbox").exists() else set()
    done = {f.stem for f in (REPO / "sent").glob("*.json")} if (REPO / "sent").exists() else set()
    print("pending:", sorted(out - done))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keys")
    sub.add_parser("init")
    sub.add_parser("fetch")
    p = sub.add_parser("show")
    p.add_argument("name")
    p.add_argument("--save-attachments", action="store_true")
    p = sub.add_parser("send")
    p.add_argument("--to", action="append", required=True)
    p.add_argument("--cc", action="append")
    p.add_argument("--subject", required=True)
    p.add_argument("--text-file", required=True)
    p.add_argument("--html-file")
    p.add_argument("--in-reply-to")
    p.add_argument("--references")
    p.add_argument("--attach", action="append")
    p.add_argument("--domain", default="gmail.com")
    p.add_argument("--wait", type=int, default=0)
    sub.add_parser("secret")
    sub.add_parser("status")
    a = ap.parse_args()
    {"keys": cmd_keys, "init": cmd_init, "fetch": cmd_fetch, "show": cmd_show, "send": cmd_send,
     "secret": cmd_secret, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()
