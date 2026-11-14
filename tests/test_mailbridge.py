"""mailbridge end to end against a local bare repository with a fake mail transport.

Run: python3 tests/test_mailbridge.py   (or under pytest)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "ops" / "mailbridge"
sys.path.insert(0, str(HERE))
import mailbridge  # noqa: E402


class FakeMail:
    inbox: list = []
    sent: list = []

    def __init__(self, address, password):
        self.address, self.password = address, password

    def new_messages(self, uidvalidity, last_uid):
        uv = "777"
        if uidvalidity != uv:
            last_uid = 0
        return uv, [(u, raw) for u, raw in FakeMail.inbox if u > last_uid]

    def send(self, msg):
        FakeMail.sent.append(msg)

    def close(self):
        pass


def client(env, *args, input=None):
    r = subprocess.run([sys.executable, str(HERE / "client.py"), *args], env=env, input=input,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_round_trip():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        bare = t / "bare.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        env = dict(os.environ, MAILCOORD_HOME=str(t / "session"), MAILCOORD_REPO=str(bare))
        client(env, "keys")
        client(env, "init")

        box_home = t / "box"
        box_home.mkdir()
        b = mailbridge.Bridge(box_home, str(bare), None, transport_factory=FakeMail, box_name="test")
        b.setup()
        b.cycle()  # no secret yet
        assert b.status["state"].startswith("waiting")

        # the secret arrives encrypted through the branch
        client(env, "secret", input="bot@example.com abcd efgh ijkl mnop\n")
        (b.d / "allow").write_text("randal@example.edu\nmax@example.com\n")
        msg = EmailMessage()
        msg["From"] = "Randal <randal@example.edu>"
        msg["To"] = "bot@example.com"
        msg["Subject"] = "Re: Stu"
        msg["Message-ID"] = "<abc@example.edu>"
        msg.set_content("Try a bigger batch.\n")
        FakeMail.inbox = [(5, msg.as_bytes())]
        b.cycle()
        assert (b.d / "secret").read_text().split() == ["bot@example.com", "abcd", "efgh", "ijkl", "mnop"]
        assert b.secret()[1] == "abcdefghijklmnop"

        out = json.loads(client(env, "fetch"))
        assert len(out["new_messages"]) == 1
        m = out["new_messages"][0]
        assert m["subject"] == "Re: Stu" and "bigger batch" in m["preview"]
        assert json.loads(client(env, "fetch"))["new_messages"] == []  # seen once

        # a second cycle does not relay the same message again
        b.cycle()
        assert json.loads(client(env, "fetch"))["new_messages"] == []

        # outbound, allowed
        body = t / "note.txt"
        body.write_text("Status note.\n")
        q = json.loads(client(env, "send", "--to", "randal@example.edu", "--cc", "max@example.com",
                              "--subject", "Stu status", "--text-file", str(body),
                              "--in-reply-to", "<abc@example.edu>"))
        b.cycle()
        assert len(FakeMail.sent) == 1
        s = FakeMail.sent[0]
        assert s["To"] == "randal@example.edu" and s["Cc"] == "max@example.com"
        assert s["In-Reply-To"] == "<abc@example.edu>" and s["Message-ID"] == q["message_id"]
        assert s["From"].addresses[0].addr_spec == "bot@example.com"
        r = json.loads(client(env, "fetch"))["new_receipts"]
        assert r[0]["ok"] is True and r[0]["id"] == q["queued"]

        # outbound, not allowed
        client(env, "send", "--to", "stranger@example.org", "--subject", "x", "--text-file", str(body))
        b.cycle()
        assert len(FakeMail.sent) == 1
        r = json.loads(client(env, "fetch"))["new_receipts"]
        assert r[0]["ok"] is False and "allow list" in r[0]["error"]

        # a forged outbox file (signed by someone else) is refused
        other = t / "other"
        other.mkdir()
        mailbridge.make_keys(other / "k", other / "c", "intruder")
        fake = {"id": "20990101T000000Z-aaaaaa", "to": ["randal@example.edu"], "subject": "x", "text": "x"}
        blob = mailbridge.seal(json.dumps(fake).encode(), other / "c", other / "k", b.cert)
        (b.repo / "outbox").mkdir(exist_ok=True)
        (b.repo / "outbox" / f"{fake['id']}.cms").write_bytes(blob)
        b.publish("forged")
        b.cycle()
        assert len(FakeMail.sent) == 1
        rec = json.loads((b.repo / "sent" / f"{fake['id']}.json").read_text())
        assert rec["ok"] is False

        # nothing readable on the branch
        for f in (b.repo).rglob("*"):
            if f.is_file() and ".git" not in f.parts and f.suffix in (".json", ".md"):
                text = f.read_text()
                assert "example.edu" not in text and "Try a bigger" not in text, f


if __name__ == "__main__":
    test_round_trip()
    print("ok")
