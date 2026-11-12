"""Tests for ops/work/ledger.py against a local bare repository (no network)."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("work_ledger", ROOT / "ops" / "work" / "ledger.py")
ledger = importlib.util.module_from_spec(spec)
sys.modules["work_ledger"] = ledger
spec.loader.exec_module(ledger)

T0 = datetime(2026, 11, 12, 7, 0, tzinfo=timezone.utc)


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bare = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.bare)], check=True)
        self.clock = [T0]
        self.agents = {}

    def tearDown(self):
        os.environ.pop("WORK_CACHE", None)
        self.tmp.cleanup()

    def lg(self, name: str) -> "ledger.Ledger":
        if name not in self.agents:
            os.environ["WORK_CACHE"] = str(self.root / f"cache-{name}")  # each agent has its own clone, like a separate session
            l = ledger.Ledger(str(self.bare), "work/ledger", name)
            l.clock = lambda: self.clock[0]
            self.agents[name] = l
        return self.agents[name]

    def boot(self, *names):
        self.lg("lead").init()
        for n in ("lead",) + names:
            self.lg(n).hello(role=f"{n} role", session=f"https://example.invalid/{n}", model=None, notes=None)

    def state(self, name="lead"):
        return self.lg(name).snapshot()

    def test_add_for_agent_sends_mail_and_renders_status(self):
        self.boot("bill")
        tid = self.lg("lead").add("Convention card parser", "code", "bill", "p1", [], "Parse ACBL cards.", 3, None, None)
        self.assertEqual(tid, "T001")
        st = self.state("bill")
        msgs = [m for p, m in st.messages("bill")]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["task"], "T001")
        status = st.get("STATUS.md").decode()
        self.assertIn("| T001 | p1 | open | bill |", status)
        self.assertIn("| bill | bill role |", status)
        self.assertEqual(self.lg("lead").add("Second", "design", None, "p2", ["T001"], "", None, 1, 2), "T002")
        log = b"".join(st.get(p) or b"" for p in self.state().paths("log/")).decode().splitlines()
        self.assertTrue(any(json.loads(x)["op"] == "add" for x in log))

    def test_claim_race_has_one_winner(self):
        self.boot("sam", "dave")
        self.lg("lead").add("Shared job", "experiment", None, "p1", [], "", None, None, None)
        sam, dave = self.lg("sam"), self.lg("dave")
        fired = []

        def dave_first(_sha):
            if not fired:
                fired.append(1)
                os.environ["WORK_CACHE"] = str(self.root / "cache-dave")
                dave.claim("T001", 2)
                os.environ["WORK_CACHE"] = str(self.root / "cache-sam")

        sam.store.before_push = dave_first
        with self.assertRaises(ledger.Conflict) as cm:
            sam.claim("T001", 2)
        self.assertIn("checked out by dave", str(cm.exception))
        t = self.state().task("T001")
        self.assertEqual(t["claim"]["by"], "dave")
        self.assertEqual([e["op"] for e in t["events"]], ["add", "claim"])

    def test_concurrent_unrelated_changes_both_land(self):
        self.boot("sam")
        lead, sam = self.lg("lead"), self.lg("sam")
        fired = []

        def lead_adds(_sha):
            if not fired:
                fired.append(1)
                lead.add("Lead's task", "design", None, "p2", [], "", None, None, None)

        sam.store.before_push = lead_adds
        sam.send("lead", "Question", "Which branch?", None, None)
        st = self.state()
        self.assertIn("T001", st.tasks())
        self.assertEqual(len(st.messages("lead")), 1)

    def test_lapsed_claim_needs_takeover_and_tells_the_holder(self):
        self.boot("bill", "will")
        self.lg("lead").add("Job", "code", None, "p2", [], "", None, None, None)
        self.lg("bill").claim("T001", 1)
        with self.assertRaises(ledger.Conflict):
            self.lg("will").claim("T001", 1)
        self.clock[0] = T0 + timedelta(hours=2)
        self.assertIn("claimed (lapsed)", self.state().get("STATUS.md").decode() + ledger.display_state(self.state().task("T001"), self.clock[0]))
        with self.assertRaises(ledger.Conflict) as cm:
            self.lg("will").claim("T001", 1)
        self.assertIn("--takeover", str(cm.exception))
        self.lg("will").claim("T001", 1, takeover=True)
        st = self.state()
        self.assertEqual(st.task("T001")["claim"]["by"], "will")
        self.assertTrue(any("took over T001" in m["subject"] for _, m in st.messages("bill")))

    def test_dependencies_assignment_review_and_done(self):
        self.boot("bill", "sam")
        lead, bill, sam = self.lg("lead"), self.lg("bill"), self.lg("sam")
        lead.add("Design", "design", "bill", "p1", [], "", None, None, None)
        lead.add("Build", "code", None, "p1", ["T001"], "", None, None, None)
        with self.assertRaises(ledger.Conflict) as cm:
            sam.claim("T001", 2)
        self.assertIn("is for bill", str(cm.exception))
        with self.assertRaises(ledger.Conflict) as cm:
            sam.claim("T002", 2)
        self.assertIn("waits for T001", str(cm.exception))
        bill.claim("T001", 2)
        bill.review("T001", "ready", [dict(kind="branch", ref="feature/x@abc")])
        st = self.state()
        self.assertEqual(st.task("T001")["state"], "review")
        self.assertTrue(any(m["subject"].startswith("Review T001") for _, m in st.messages("lead")))
        with self.assertRaises(ledger.Conflict):
            sam.close("T001", "done", "not mine", [])
        lead.close("T001", "done", "accepted", [])
        st = self.state()
        self.assertEqual(st.task("T001")["state"], "done")
        self.assertIsNone(st.task("T001")["claim"])
        self.assertTrue(any(m["subject"].startswith("T001 done") for _, m in st.messages("bill")))
        self.assertIn("| T001 | done | lead |", st.get("STATUS.md").decode())
        sam.claim("T002", 2)
        sam.release("T002", "out of time")
        self.assertEqual(self.state().task("T002")["state"], "open")

    def test_block_reopen_cancel(self):
        self.boot("dave")
        self.lg("lead").add("Arena job", "experiment", "dave", "p2", [], "", None, 1, 3)
        self.lg("dave").claim("T001", 2)
        self.lg("dave").block("T001", "no free box")
        st = self.state()
        self.assertEqual(st.task("T001")["state"], "blocked")
        self.assertTrue(any("blocked" in m["subject"] for _, m in st.messages("lead")))
        with self.assertRaises(ledger.Conflict):
            self.lg("dave").claim("T001", 2)
        self.lg("lead").reopen("T001", "box free now")
        self.lg("dave").claim("T001", 2)
        self.lg("lead").cancel("T001", "superseded")
        self.assertEqual(self.state().task("T001")["state"], "cancelled")

    def test_leases(self):
        self.boot("sam", "dave")
        self.lg("sam").lease("box:azure2", 2, "signalling bench", None, False)
        with self.assertRaises(ledger.Conflict) as cm:
            self.lg("dave").lease("box:azure2", 1, "arena", None, False)
        self.assertIn("held by sam", str(cm.exception))
        self.lg("sam").lease("box:azure2", 3, "signalling bench, longer", None, False)  # the holder extends
        self.clock[0] = T0 + timedelta(hours=4)
        with self.assertRaises(ledger.Conflict):
            self.lg("dave").lease("box:azure2", 1, "arena", None, False)
        self.lg("dave").lease("box:azure2", 1, "arena", None, True)
        st = self.state()
        self.assertEqual(st.leases()["box:azure2"]["holder"], "dave")
        self.assertTrue(any("took over box:azure2" in m["subject"] for _, m in st.messages("sam")))
        with self.assertRaises(ledger.Conflict):
            self.lg("sam").unlease("box:azure2")
        self.lg("dave").unlease("box:azure2")
        self.assertEqual(self.state().leases(), {})

    def test_read_marks_read_and_broadcast(self):
        self.boot("will", "sam")
        mid = self.lg("lead").send("will", "Set up CI", "Please.", None, None)
        self.lg("lead").send("all", "Kickoff", "Plan is on T001.", None, None)
        st = self.state("will")
        self.assertIn("| will | will role |", st.get("STATUS.md").decode())
        m = self.lg("will").mark_read(mid)
        self.assertEqual(m["body"], "Please.")
        st = self.state()
        direct = [m for _, m in st.messages("will")][0]
        self.assertEqual(direct["read_by"], ["will"])
        self.assertEqual(len(st.messages("all")), 1)
        rows = [l for l in st.get("STATUS.md").decode().splitlines() if l.startswith("| will |")]
        self.assertTrue(rows[0].rstrip().split("|")[4].strip() == "1", rows)  # the broadcast is still unread for will

    def test_cli(self):
        os.environ["WORK_CACHE"] = str(self.root / "cache-cli")
        base = ["--repo", str(self.bare), "--branch", "work/ledger"]
        def run(*args):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = ledger.main(base + list(args))
            return code, out.getvalue(), err.getvalue()
        self.assertEqual(run("--as", "lead", "init")[0], 0)
        self.assertEqual(run("--as", "lead", "hello", "--role", "Gen 9 lead")[0], 0)
        self.assertEqual(run("--as", "lead", "add", "Plan", "--kind", "design", "--for", "will", "--priority", "p0")[1].strip(), "T001")
        code, out, _ = run("--as", "will", "next")
        self.assertIn("T001", out)
        code, out, _ = run("--as", "will", "claim", "T001", "--hours", "1")
        self.assertEqual(code, 0)
        code, out, err = run("--as", "sam", "claim", "T001")
        self.assertEqual(code, 3)
        self.assertIn("refused", err)
        code, out, _ = run("--as", "will", "done", "T001", "--result", "made", "--output", "branch=feature/x@abc")
        self.assertEqual(code, 0)
        code, out, _ = run("--as", "will", "watch", "--no-heartbeat")
        self.assertIn("unread for will: 1", out)
        code, out, _ = run("--as", "lead", "watch", "--no-heartbeat")
        self.assertIn("unread for lead: 1", out)  # will closed the task lead wrote, so lead is told
        code, out, _ = run("--as", "will", "inbox", "--all")
        self.assertIn("New task T001", out)
        code, out, _ = run("inbox", "--agent", "lead")
        self.assertIn("T001 done", out)
        code, out, _ = run("show", "T001")
        self.assertIn("output branch: feature/x@abc", out)
        code, out, _ = run("export")
        self.assertEqual(json.loads(out)["tasks"]["T001"]["state"], "done")
        with self.assertRaises(SystemExit):
            run("--as", "all", "hello")


if __name__ == "__main__":
    unittest.main()
