#!/usr/bin/env python3
"""mailbridge: one mailbox relayed to a Claude session through an encrypted GitHub branch.

Runs on a box. Every INTERVAL seconds it
  1. fetches branch mail/coord,
  2. sends each new outbox/<id>.cms (signed by the session, encrypted to the box) by SMTP,
     to allow-listed addresses only, and writes sent/<id>.json,
  3. reads new INBOX messages by IMAP and writes each, signed by the box and encrypted to the
     session, as inbox/<time>-<uid>.cms,
  4. pushes.

The repository is public: nothing readable leaves the box except receipts and status, which
carry no addresses or message text. Signing and encryption are CMS through the openssl CLI.

Files on the box, under ~/.mailbridge (mode 700):
  secret      "ADDRESS APP_PASSWORD" (mode 600; spaces inside the password are ignored), or
              delivered encrypted as secret/secret.cms on the branch
  name        optional display name for From
  allow       one address per line: the only recipients the bridge will send to
  box.key, box.pem      the box's key and self-signed certificate (box.pem is published)
  state.json  IMAP position and ids already sent
  repo/       a clone of branch mail/coord
"""
from __future__ import annotations

import argparse
import imaplib
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import time
import traceback
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
import base64

VERSION = "1.0"
BRANCH = "mail/coord"
ID_RE = re.compile(r"^[0-9A-Za-z_.-]{6,80}$")


def utc(t: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def log(*a) -> None:
    print(utc(), *a, flush=True)


def run(cmd, input: bytes | None = None, cwd=None, env=None, check=True):
    r = subprocess.run(cmd, input=input, capture_output=True, cwd=cwd, env=env)
    if check and r.returncode:
        err = r.stderr.decode(errors="replace")[-800:]
        raise RuntimeError(f"{' '.join(map(str, cmd[:3]))} failed ({r.returncode}): {err}")
    return r


# ---------------------------------------------------------------- crypto (shared with client.py)

def make_keys(key: Path, cert: Path, cn: str) -> None:
    run(["openssl", "req", "-x509", "-newkey", "rsa:3072", "-nodes", "-sha256", "-days", "3650",
         "-keyout", str(key), "-out", str(cert), "-subj", f"/CN={cn}"])
    os.chmod(key, 0o600)


def seal(data: bytes, my_cert: Path, my_key: Path, peer_cert: Path) -> bytes:
    """Sign with my key, then encrypt to the peer."""
    signed = run(["openssl", "cms", "-sign", "-binary", "-nodetach", "-md", "sha256", "-outform", "DER",
                  "-signer", str(my_cert), "-inkey", str(my_key)], input=data).stdout
    return run(["openssl", "cms", "-encrypt", "-binary", "-aes256", "-outform", "DER", str(peer_cert)],
               input=signed).stdout


def unseal(blob: bytes, my_cert: Path, my_key: Path, peer_cert: Path) -> bytes:
    """Decrypt with my key, then verify that the peer signed it."""
    inner = run(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER",
                 "-recip", str(my_cert), "-inkey", str(my_key)], input=blob).stdout
    return run(["openssl", "cms", "-verify", "-binary", "-inform", "DER", "-purpose", "any",
                "-CAfile", str(peer_cert)], input=inner).stdout


# ---------------------------------------------------------------- mail transports (replaceable in tests)

class Gmail:
    imap_host, imap_port = "imap.gmail.com", 993
    smtp_host, smtp_port = "smtp.gmail.com", 587

    def __init__(self, address: str, password: str):
        self.address, self.password = address, password
        self.imap: imaplib.IMAP4_SSL | None = None

    def _imap(self) -> imaplib.IMAP4_SSL:
        if self.imap is not None:
            try:
                self.imap.noop()
                return self.imap
            except Exception:
                self.close()
        m = imaplib.IMAP4_SSL(self.imap_host, self.imap_port, timeout=60)
        m.login(self.address, self.password)
        self.imap = m
        return m

    def close(self) -> None:
        if self.imap is not None:
            try:
                self.imap.logout()
            except Exception:
                pass
        self.imap = None

    def new_messages(self, uidvalidity: str | None, last_uid: int):
        """Returns (uidvalidity, [(uid, raw_bytes), ...]) for messages with uid > last_uid."""
        m = self._imap()
        typ, _ = m.select("INBOX", readonly=True)
        if typ != "OK":
            raise RuntimeError("IMAP select INBOX failed")
        uv = m.untagged_responses.get("UIDVALIDITY", [b"0"])[-1]
        uv = uv.decode() if isinstance(uv, bytes) else str(uv)
        if uv != uidvalidity:
            last_uid = 0
        typ, data = m.uid("SEARCH", None, f"UID {last_uid + 1}:*")
        if typ != "OK":
            raise RuntimeError("IMAP search failed")
        uids = sorted(int(u) for u in (data[0] or b"").split() if int(u) > last_uid)
        out = []
        for uid in uids:
            typ, parts = m.uid("FETCH", str(uid), "(BODY.PEEK[])")
            raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
            if typ != "OK" or raw is None:
                raise RuntimeError(f"IMAP fetch of uid {uid} failed")
            out.append((uid, raw))
        return uv, out

    def send(self, msg: EmailMessage) -> None:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=60) as s:
            s.starttls(context=ctx)
            s.login(self.address, self.password)
            s.send_message(msg)


# ---------------------------------------------------------------- the bridge

class Bridge:
    def __init__(self, home: Path, repo_url: str, ssh_key: str | None, transport_factory=Gmail,
                 box_name: str = "box"):
        self.d = home / ".mailbridge"
        self.repo = self.d / "repo"
        self.repo_url = repo_url
        self.box_name = box_name
        self.transport_factory = transport_factory
        self.transport = None
        self.env = dict(os.environ)
        if ssh_key:
            self.env["GIT_SSH_COMMAND"] = (f"ssh -i {ssh_key} -o IdentitiesOnly=yes -o BatchMode=yes "
                                           "-o StrictHostKeyChecking=accept-new")
        self.key, self.cert = self.d / "box.key", self.d / "box.pem"
        self.state_path = self.d / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.state.setdefault("sent_ids", [])
        self.state.setdefault("uidvalidity", None)
        self.state.setdefault("last_uid", 0)
        self.status = {"version": VERSION, "box": box_name}
        self.last_status_push = 0.0

    # git
    def git(self, *args, check=True):
        return run(["git", *args], cwd=self.repo, env=self.env, check=check)

    def setup(self) -> None:
        self.d.mkdir(mode=0o700, exist_ok=True)
        if not self.key.exists():
            make_keys(self.key, self.cert, f"mailbridge-{self.box_name}")
            log("made box key and certificate")
        if not (self.repo / ".git").exists():
            run(["git", "clone", "-q", "--single-branch", "--branch", BRANCH, self.repo_url, str(self.repo)],
                env=self.env)
            self.git("config", "user.name", f"mailbridge ({self.box_name})")
            self.git("config", "user.email", "mailbridge@invalid")
            self.git("config", "commit.gpgsign", "false")
        self.sync()
        pub = self.repo / "certs" / "box.pem"
        if not pub.exists() or pub.read_bytes() != self.cert.read_bytes():
            pub.parent.mkdir(exist_ok=True)
            pub.write_bytes(self.cert.read_bytes())
            self.publish(f"mailbridge {self.box_name}: box certificate")

    def sync(self) -> None:
        self.git("fetch", "-q", "origin", BRANCH)
        ahead = self.git("rev-list", "--count", f"origin/{BRANCH}..HEAD").stdout.strip()
        if ahead == "0":
            self.git("reset", "-q", "--hard", f"origin/{BRANCH}")
        else:
            self.git("rebase", "-q", f"origin/{BRANCH}")

    def publish(self, message: str) -> bool:
        self.git("add", "-A")
        if self.git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return False
        self.git("commit", "-q", "-m", message)
        for attempt in range(6):
            if self.git("push", "-q", "origin", f"HEAD:{BRANCH}", check=False).returncode == 0:
                return True
            time.sleep(2 + 3 * attempt)
            self.sync()
        raise RuntimeError("push failed six times")

    def save_state(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1))
        tmp.replace(self.state_path)

    # credentials
    def secret(self):
        p = self.d / "secret"
        if not p.exists():
            enc = self.repo / "secret" / "secret.cms"
            session = self.repo / "certs" / "session.pem"
            if enc.exists() and session.exists():
                data = unseal(enc.read_bytes(), self.cert, self.key, session)
                fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(data.strip() + b"\n")
                log("installed the secret delivered on the branch")
            else:
                return None
        parts = p.read_text().split()
        if len(parts) < 2:
            raise RuntimeError("secret file needs ADDRESS PASSWORD")
        # Google shows app passwords in groups of four; spaces are not part of them.
        address, password = parts[0], "".join(parts[1:])
        name_file = self.d / "name"
        name = name_file.read_text().strip() if name_file.exists() else "Claude (for Max Schireson)"
        return address, password, name

    def allowed(self) -> set[str]:
        p = self.d / "allow"
        if not p.exists():
            return set()
        return {ln.strip().lower() for ln in p.read_text().splitlines() if ln.strip() and not ln.startswith("#")}

    # outbound
    def build(self, req: dict, address: str, name: str) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = formataddr((name, address))
        msg["To"] = ", ".join(req["to"])
        if req.get("cc"):
            msg["Cc"] = ", ".join(req["cc"])
        if req.get("reply_to"):
            msg["Reply-To"] = req["reply_to"]
        msg["Subject"] = req["subject"]
        msg["Date"] = formatdate(usegmt=True)
        msg["Message-ID"] = req.get("message_id") or make_msgid(domain=address.split("@")[-1])
        if req.get("in_reply_to"):
            msg["In-Reply-To"] = req["in_reply_to"]
            msg["References"] = req.get("references") or req["in_reply_to"]
        msg.set_content(req["text"])
        if req.get("html"):
            msg.add_alternative(req["html"], subtype="html")
        for a in req.get("attachments", []):
            maintype, _, subtype = a.get("mime", "application/octet-stream").partition("/")
            msg.add_attachment(base64.b64decode(a["b64"]), maintype=maintype, subtype=subtype or "octet-stream",
                               filename=a["filename"])
        return msg

    def process_outbox(self, creds) -> int:
        out_dir, sent_dir = self.repo / "outbox", self.repo / "sent"
        if not out_dir.exists():
            return 0
        session = self.repo / "certs" / "session.pem"
        n = 0
        for f in sorted(out_dir.glob("*.cms")):
            oid = f.stem
            if oid in self.state["sent_ids"] or (sent_dir / f"{oid}.json").exists():
                continue
            receipt = {"id": oid, "time": utc()}
            try:
                if not ID_RE.match(oid):
                    raise ValueError("bad id")
                req = json.loads(unseal(f.read_bytes(), self.cert, self.key, session))
                if req.get("id") != oid:
                    raise ValueError("id inside does not match the file name")
                allow = self.allowed()
                rcpts = [x.lower() for x in req["to"] + req.get("cc", [])]
                bad = [x for x in rcpts if x not in allow]
                if bad:
                    raise ValueError(f"{len(bad)} recipient(s) not on the allow list")
                if creds is None:
                    continue  # no credentials yet: leave it queued
                msg = self.build(req, creds[0], creds[2])
                self.transport.send(msg)
                receipt.update(ok=True, message_id=msg["Message-ID"])
                log("sent", oid)
            except Exception as e:  # noqa: BLE001
                receipt.update(ok=False, error=f"{type(e).__name__}: {str(e)[:300]}")
                log("send failed", oid, receipt["error"])
            sent_dir.mkdir(exist_ok=True)
            (sent_dir / f"{oid}.json").write_text(json.dumps(receipt, indent=1))
            self.state["sent_ids"].append(oid)
            self.save_state()
            n += 1
        return n

    # inbound
    def poll_inbox(self) -> int:
        session = self.repo / "certs" / "session.pem"
        uv, msgs = self.transport.new_messages(self.state["uidvalidity"], int(self.state["last_uid"]))
        if uv != self.state["uidvalidity"]:
            self.state["uidvalidity"], self.state["last_uid"] = uv, 0
        inbox = self.repo / "inbox"
        n = 0
        for uid, raw in msgs:
            inbox.mkdir(exist_ok=True)
            name = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uv}-{uid}.cms"
            (inbox / name).write_bytes(seal(raw, self.cert, self.key, session))
            self.state["last_uid"] = max(int(self.state["last_uid"]), uid)
            n += 1
        if n:
            self.save_state()
        return n

    def cycle(self) -> None:
        self.sync()
        creds = self.secret()
        if creds is None:
            self.status.update(state="waiting for the mailbox secret")
            self.transport = None
        else:
            if self.transport is None or self.transport.address != creds[0]:
                self.transport = self.transport_factory(creds[0], creds[1])
            self.status.update(state="running")
        sent = self.process_outbox(creds) if creds else 0
        got = self.poll_inbox() if creds else 0
        self.status.update(last_cycle=utc(), last_error=None)
        if sent or got:
            self.status.update(last_change=utc())
        changed = bool(sent or got)
        if changed or time.time() - self.last_status_push > 3600:
            self.write_status()
            if self.publish(f"mailbridge {self.box_name}: {got} in, {sent} out"):
                self.last_status_push = time.time()

    def write_status(self) -> None:
        self.status["time"] = utc()
        self.status["sent_total"] = len(self.state["sent_ids"])
        self.status["last_uid"] = self.state["last_uid"]
        (self.repo / "status.json").write_text(json.dumps(self.status, indent=1))

    def loop(self, interval: float) -> None:
        self.setup()
        errors = 0
        while True:
            t0 = time.time()
            try:
                self.cycle()
                errors = 0
            except Exception as e:  # noqa: BLE001
                errors += 1
                log("cycle failed:", "".join(traceback.format_exception_only(type(e), e)).strip())
                self.status.update(last_error=f"{utc()} {type(e).__name__}: {str(e)[:200]}")
                if self.transport is not None:
                    self.transport.close()
                if errors in (1, 5) or errors % 60 == 0:
                    try:
                        self.write_status()
                        self.publish(f"mailbridge {self.box_name}: error")
                    except Exception:  # noqa: BLE001
                        pass
            time.sleep(max(5.0, interval - (time.time() - t0)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-url", default="git@github.com:maxschireson/Single-Dummy-Bridge.git")
    ap.add_argument("--ssh-key", default=str(Path.home() / ".ssh" / "boxctl_github"))
    ap.add_argument("--box", default=os.uname().nodename)
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--once", action="store_true", help="set up and run one cycle")
    a = ap.parse_args()
    b = Bridge(Path.home(), a.repo_url, a.ssh_key or None, box_name=a.box)
    if a.once:
        b.setup()
        b.cycle()
        b.write_status()
        b.publish(f"mailbridge {a.box}: one cycle")
        return
    b.loop(a.interval)


if __name__ == "__main__":
    sys.exit(main())
