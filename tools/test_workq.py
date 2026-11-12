"""Tests for tools/workq.py against a local bare repository (no network). Run: python3 tools/test_workq.py"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("work_ledger", HERE / "workq.py")
ledger = importlib.util.module_from_spec(spec)
sys.modules["work_ledger"] = ledger
spec.loader.exec_module(ledger)

T0 = datetime(2026, 11, 12, 7, 0, tzinfo=timezone.utc)

# Shaped like the real files on team/gen9: "holder: " with a trailing space in tasks, "holder:" without in experiments.
TASK = """---
id: G9-B1
title: Design note: card IR for bidding, card to rules, the rule filter
area: bidding
kind: design
owner: bill
state: open
holder:
lease_until:
priority: high
depends:
due: 2026-11-12T12:00Z
branch:
resolution:
---
## Goal

Design the bidding half.

## Done when

`docs/gen9/bidding.md` submitted.

## Context

Rule bidder.

## Log

- 2026-11-12T06:47Z g9: created.
"""
TASK = re.sub(r"^(holder|lease_until|depends|branch|resolution):$", r"\1: ", TASK, flags=re.M)  # the real files keep this space
EXPERIMENT = """---
id: E9-3
title: How often spot cards nine and below are not equivalent
area: signals
kind: experiment
owner: sam
state: open
holder:
lease_until:
priority: high
depends: G9-B1
due: 2026-11-12T20:00Z
branch:
resolution:
---
## Hypothesis

Low spots are equivalent.

## Mechanism

A signal is a choice among cards that take the same tricks.

## Primary metric and population

Share of decisions where the spots differ, 5,000 defender decisions from Gen 7 records.

## Regression slices

Trumps against side suits.

## Compute cap

2 CPU-hours in a sandbox.

## Stopping rule

The fixed sample.

## Result

_not yet_

## Log

- 2026-11-12T06:47Z g9: registered with predictions.
"""


def task(id_, owner="pool", state="open", area="workflow"):
    return (f"---\nid: {id_}\ntitle: Task {id_}\narea: {area}\nkind: module\nowner: {owner}\nstate: {state}\nholder: \n"
            f"lease_until: \npriority: medium\ndepends: \ndue: \nbranch: \nresolution: \n---\n## Goal\n\nX.\n\n## Log\n\n"
            f"- 2026-11-12T06:47Z g9: created.\n")


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

    def lg(self, name):
        if name not in self.agents:
            os.environ["WORK_CACHE"] = str(self.root / f"cache-{name}")  # one cache per agent, as separate sessions
            l = ledger.Ledger(str(self.bare), "team/gen9", name, lead="g9")
            l.clock = lambda: self.clock[0]
            self.agents[name] = l
        return self.agents[name]

    def team_dir(self, files, name="team"):
        d = self.root / name
        for rel, text in files.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text(text)
        return d

    def boot(self, files=None, *names):
        def seed(st):
            st.put("README.md", b"# channel\n")
            for rel, text in (files or {}).items():
                st.put(rel, text.encode())
        self.lg("g9").mutate("seed", seed, allow_create=True)  # stands for files written by hand before workq
        for n in ("g9",) + names:
            self.lg(n).hello(role=f"{n} role", session=f"https://example.invalid/{n}", model=None, notes=None)

    def st(self, name="g9"):
        return self.lg(name).snapshot()

    def text(self, path):
        return self.st().get(path).decode()

    def test_existing_files_work_unchanged(self):
        msg = "Welcome, bill.\n\nFrom g9.\n"
        self.boot({"tasks/G9-B1.md": TASK, "experiments/E9-3.md": EXPERIMENT, "inbox/bill/20261112T0639Z-g9-welcome.md": msg,
                   "ROSTER.md": "# Roster\n"}, "bill", "sam")
        self.assertEqual(self.text("tasks/G9-B1.md"), TASK)
        self.assertEqual(self.text("experiments/E9-3.md"), EXPERIMENT)
        self.assertEqual(self.text("inbox/bill/20261112T0639Z-g9-welcome.md"), msg)
        self.lg("bill").lease("G9-B1", 3)
        after = self.text("tasks/G9-B1.md")
        self.assertIn("\nstate: leased\nholder: bill\nlease_until: 2026-11-12T10:00Z\npriority: high\ndepends: \ndue: ", after)
        self.assertIn("\nbranch: \nresolution: \n---\n## Goal\n\nDesign the bidding half.\n", after)  # trailing spaces kept
        self.assertTrue(after.endswith("- 2026-11-12T06:47Z g9: created.\n- 2026-11-12T07:00Z bill: leased until 2026-11-12T10:00Z\n"))
        self.lg("sam").lease("E9-3", 2)  # depends on G9-B1, which is not resolved: allowed, with a log note
        e = self.text("experiments/E9-3.md")
        self.assertIn("G9-B1 not resolved yet", e)
        self.assertIn("\nholder: sam\n", e)
        self.assertIn("\nbranch:\nresolution:\n", e)
        self.assertEqual([m["subject"] for m in self.st("bill").unread("bill")], ["Welcome, bill."])
        status = self.text("STATUS.md")
        self.assertIn("| [G9-B1](tasks/G9-B1.md) | Design note: card IR for bidding, card to rules, the rule filter | bill | "
                      "bill until 11-12 10:00 | leased | high |", status)
        self.assertIn("| bill | 1 | 0 | 0 | 0 | 0 | 0 |", status)

    def test_lease_race_has_one_winner(self):
        self.boot({"tasks/G9-W9.md": task("G9-W9")}, "sam", "dave")
        sam, dave = self.lg("sam"), self.lg("dave")
        fired = []

        def dave_first(_sha):
            if not fired:
                fired.append(1)
                dave.lease("G9-W9", 2)

        sam.store.before_push = dave_first
        with self.assertRaises(ledger.Conflict) as cm:
            sam.lease("G9-W9", 2)
        self.assertIn("leased by dave", str(cm.exception))
        d = self.st().doc("G9-W9")
        self.assertEqual(d.get("holder"), "dave")
        self.assertEqual(d.section("Log").count("leased until"), 1)

    def test_concurrent_unrelated_changes_both_land(self):
        self.boot({"tasks/G9-W9.md": task("G9-W9")}, "sam")
        fired = []

        def g9_sends(_sha):
            if not fired:
                fired.append(1)
                self.lg("g9").send("sam", "Plan", "Read the plan.", None, None)

        self.lg("sam").store.before_push = g9_sends
        self.lg("sam").lease("G9-W9", 1)
        st = self.st()
        self.assertEqual(st.doc("G9-W9").get("holder"), "sam")
        self.assertEqual(len(st.unread("sam")), 1)

    def test_expired_lease_takeover_rules(self):
        self.boot({"tasks/G9-D9.md": task("G9-D9", owner="dave", area="arena")}, "dave", "x1", "sam")
        self.lg("x1").lease("G9-D9", 1, force=True)  # an executor the owner briefed
        self.clock[0] = T0 + timedelta(minutes=70)  # lapsed 10 minutes ago: inside the 30 minute grace
        with self.assertRaises(ledger.Conflict) as cm:
            self.lg("dave").lease("G9-D9", 1)
        self.assertIn("may be taken over from 2026-11-12T08:30Z", str(cm.exception))
        self.assertEqual(ledger.note_for(self.st(), self.st().doc("G9-D9"), self.clock[0]), "lease expired")
        self.clock[0] = T0 + timedelta(minutes=95)
        with self.assertRaises(ledger.Conflict) as cm:
            self.lg("sam").lease("G9-D9", 1)
        self.assertIn("only its owner (dave) or g9", str(cm.exception))
        self.lg("dave").lease("G9-D9", 1)
        st = self.st()
        self.assertEqual(st.doc("G9-D9").get("holder"), "dave")
        self.assertIn("taking over from x1", st.doc("G9-D9").section("Log"))
        self.assertTrue(any("took over G9-D9: your lease lapsed at 2026-11-12T08:00Z" in m["subject"] for m in st.unread("x1")))

    def test_malformed_headers_are_refused(self):
        self.boot(None, "bill")
        cases = (("tasks/G9-B2.md", TASK.replace("id: G9-B1", "id: G9-B2").replace("state: open", "state: started"), "unknown state 'started'"),
                 ("tasks/G9-B9.md", TASK, "differs from the file name"),
                 ("tasks/G9-B1.md", re.sub(r"^title: .*$", "title: ", TASK, flags=re.M), "has no title"),
                 ("tasks/G9-B1.md", TASK.replace("priority: high", "priority: urgent"), "priority 'urgent'"),
                 ("tasks/G9-B1.md", TASK.replace("due: 2026-11-12T12:00Z", "due: noon"), "due: not a UTC time"),
                 ("tasks/G9-B1.md", TASK.replace("state: open\nholder: ", "state: leased\nholder: "), "needs holder and lease_until"),
                 ("tasks/G9-B1.md", TASK.replace("resolution: ", "resolution: adopted"), "resolution 'adopted'"),
                 ("tasks/G9-B1.md", TASK.replace("---\n## Goal", "## Goal"), "bad header line"))
        for path, text, why in cases:
            with self.assertRaises(ledger.Malformed) as cm:
                ledger.Doc(path, text).validate()
            self.assertIn(why, str(cm.exception))
        # a hand edit that breaks a header: listed in STATUS.md, `check` fails, and commands on it are refused
        self.lg("g9").mutate("hand edit", lambda st: st.put("tasks/G9-B1.md", TASK.replace("kind: design", "kind: essay").encode()))
        self.assertIn("## Files with a malformed header", self.text("STATUS.md"))
        with self.assertRaises(ledger.Malformed):
            self.lg("bill").lease("G9-B1", 1)
        out, err = io.StringIO(), io.StringIO()
        os.environ["WORK_CACHE"] = str(self.root / "cache-cli")
        with redirect_stdout(out), redirect_stderr(err):
            code = ledger.main(["--repo", str(self.bare), "--channel", "team/gen9", "check"])
        self.assertEqual(code, 1)
        self.assertIn("kind 'essay'", out.getvalue())
        # an edit that would write a malformed header is refused too
        self.lg("g9").mutate("fix", lambda st: st.put("tasks/G9-B1.md", TASK.encode()))
        with self.assertRaises(ledger.Malformed):
            self.lg("bill").edit("G9-B1", TASK.replace("priority: high", "priority: urgent"))
        self.assertEqual(self.text("tasks/G9-B1.md"), TASK)

    def test_edit_keeps_lifecycle_and_log(self):
        self.boot({"experiments/E9-3.md": EXPERIMENT}, "sam")
        self.lg("sam").lease("E9-3", 2)
        sharper = EXPERIMENT.replace("Low spots are equivalent.", "Equivalent in at least 95% of decisions.") \
                            .replace("state: open", "state: resolved").replace("- 2026-11-12T06:47Z g9: registered", "- forged")
        self.lg("sam").edit("E9-3", sharper)
        d = self.st().doc("E9-3")
        self.assertEqual(d.get("state"), "leased")
        self.assertIn("at least 95%", d.section("Hypothesis"))
        log = d.section("Log")
        self.assertIn("g9: registered with predictions", log)
        self.assertNotIn("forged", log)
        self.assertIn("sam: sections edited", log)

    def test_experiment_needs_its_preregistration(self):
        head = EXPERIMENT.split("## Hypothesis")[0].replace("id: E9-3", "id: E9-8")
        thin = head + "## Hypothesis\n\n_not yet_\n\n## Stopping rule\n\nTBD\n\n## Result\n\n_not yet_\n\n## Log\n\n- 2026-11-12T06:47Z g9: registered.\n"
        self.boot({"experiments/E9-8.md": thin, "experiments/E9-3.md": EXPERIMENT}, "sam")
        with self.assertRaises(ledger.Conflict) as cm:
            self.lg("sam").lease("E9-8", 2)
        self.assertIn("not pre-registered: fill Hypothesis, Primary metric and population, Compute cap, Stopping rule", str(cm.exception))
        full = EXPERIMENT.replace("id: E9-3", "id: E9-8")
        self.lg("sam").edit("E9-8", full)
        self.lg("sam").lease("E9-8", 2)
        self.assertEqual(self.st().doc("E9-8").get("holder"), "sam")

    def test_created_field_review_list_and_refresh(self):
        self.boot({"tasks/G9-B1.md": TASK}, "bill")
        tid = self.lg("bill").new("Rule filter", "bidding", "module", "bill", "high", [], None, "")
        d = self.st().doc(tid)
        self.assertEqual(d.get("created"), "2026-11-12T07:00Z")
        self.assertLess([r[0] for r in d.head].index("due"), [r[0] for r in d.head].index("created"))
        self.lg("bill").lease("G9-B1", 1)
        self.lg("bill").submit("G9-B1", "note up", "feature/gen9-bidding-design", None)
        status = self.text("STATUS.md")
        self.assertIn("## Waiting for review", status)
        self.assertIn("| g9 | [G9-B1](tasks/G9-B1.md) | Design note: card IR for bidding, card to rules, the rule filter | bill | feature/gen9-bidding-design |", status)
        self.assertLess(status.index("## Waiting for review"), status.index("## Tasks\n"))
        # a session that edits by hand and leaves STATUS.md stale: refresh brings it back in line
        self.lg("g9").mutate("hand", lambda st: st.put("tasks/G9-B1.md", st.get("tasks/G9-B1.md").replace(b"state: submitted", b"state: resolved").replace(b"resolution: ", b"resolution: accepted")))
        self.lg("g9").refresh()
        self.assertNotIn("## Waiting for review", self.text("STATUS.md"))

    def test_brief_and_ready_check(self):
        ready = task("G9-W9").replace("## Goal\n\nX.\n", "## Goal\n\nX.\n\n## Base\n\nfeature/gen9 at abc1234\n\n## Interface\n\n"
                                       "tools/x.py only\n\n## Done when\n\nTests pass.\n\n## Time box\n\n2 hours\n\n## Tests\n\n"
                                       "python3 tools/test_x.py\n\n## Results\n\nBranch feature/gen9-workflow-x\n")
        self.boot({"tasks/G9-W9.md": ready, "tasks/G9-W8.md": task("G9-W8")}, "will")
        st = self.st()
        self.assertEqual(ledger.missing_ready(st.doc("G9-W9")), [])
        self.assertEqual(ledger.missing_ready(st.doc("G9-W8")), ["Base", "Interface", "Done when", "Time box", "Tests", "Results"])
        b = ledger.brief_text(st, st.doc("G9-W9"), "team/gen9")
        self.assertIn("# Brief: G9-W9, Task G9-W9", b)
        self.assertIn("feature/gen9 at abc1234", b)
        self.assertIn("Hidden hands are labels", b)
        self.assertIn("$Q lease G9-W9 --hours", b)
        self.assertNotIn("Not executor-ready", b)
        self.assertIn("**Not executor-ready:** the task has no Base, Interface", ledger.brief_text(st, st.doc("G9-W8"), "team/gen9"))
        os.environ["WORK_CACHE"] = os.environ["WORKQ_CACHE"] = str(self.root / "cache-cli2")
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = ledger.main(["--repo", str(self.bare), "--channel", "team/gen9", "check", "--ready", "G9-W8"])
        self.assertEqual(code, 1)
        self.assertIn("G9-W8 lacks: Base", out.getvalue())

    def test_module_reviews_go_to_the_peer_lead(self):
        mod = TASK.replace("kind: design", "kind: module").replace("id: G9-B1", "id: G9-B2")
        dav = task("G9-D7", owner="dave", area="arena")
        self.boot({"tasks/G9-B1.md": TASK, "tasks/G9-B2.md": mod, "tasks/G9-D7.md": dav}, "bill", "sam", "dave", "will")
        self.lg("bill").lease("G9-B2", 1)
        self.lg("bill").submit("G9-B2", "filter", "feature/gen9-bidding-filter", None)
        self.assertTrue(any(m["subject"].startswith("G9-B2 submitted") for m in self.st().unread("sam")))
        self.assertFalse(any(m["subject"].startswith("G9-B2 submitted") for m in self.st().unread("g9")))
        self.assertIn("| sam | [G9-B2]", self.text("STATUS.md"))
        with self.assertRaises(ledger.Conflict):
            self.lg("will").resolve("G9-B2", "accepted", "")
        self.lg("sam").resolve("G9-B2", "accepted", "reviewed")
        self.lg("bill").lease("G9-B1", 1)  # a design note still goes to g9
        self.lg("bill").submit("G9-B1", "note", None, None)
        self.assertTrue(any(m["subject"].startswith("G9-B1 submitted") for m in self.st().unread("g9")))
        self.lg("dave").lease("G9-D7", 1)  # G9-D7 is a module owned by dave, so will reviews it
        self.lg("dave").submit("G9-D7", "x", None, None)
        self.assertTrue(any(m["subject"].startswith("G9-D7 submitted") for m in self.st().unread("will")))
        self.assertEqual(ledger.reviewer_of(self.st().doc("G9-D7"), "g9"), "will")

    def test_queue_issue_and_decisions(self):
        roster = ("# Roster\n\n## Review checkpoints (UTC)\n\n| When | What |\n| --- | --- |\n"
                  "| Thu 12 Nov, about 06:00 | Checkpoint 0 |\n| Thu 12 Nov, about 12:00 | Checkpoint 1: notes due |\n")
        self.boot({"tasks/G9-B1.md": TASK, "ROSTER.md": roster}, "bill")
        calls, issues, comments = [], {}, {}

        def fake_gh(method, path, fields=None):
            calls.append((method, path, fields))
            if method == "GET" and path.startswith("issues?labels=decision"):
                return [i for i in issues.values() if "decision" in i.get("labels", []) and i["state"] == "open"]
            if method == "GET" and path.startswith("labels"):
                return [{"name": "bug"}]
            if method == "POST" and path == "labels":
                return fields
            if method == "POST" and path == "issues":
                n = 21 + len(issues)
                issues[n] = dict(number=n, title=fields["title"], body=fields["body"], labels=fields.get("labels", []), state="open",
                                 html_url=f"https://github.com/x/y/issues/{n}", created_at="2026-11-12T06:50:00Z")
                return issues[n]
            if method == "PATCH":
                n = int(path.split("/")[1])
                issues[n].update(fields)
                return issues[n]
            if method == "GET" and path.endswith("/comments?per_page=100"):
                return comments.get(int(path.split("/")[1]), [])
            if method == "POST" and path.endswith("/comments"):
                return {}
            raise AssertionError((method, path))
        real = ledger.gh
        ledger.gh = fake_gh
        try:
            self.lg("bill").lease("G9-B1", 1)
            self.lg("bill").submit("G9-B1", "note", "feature/gen9-bidding-design", None)
            text = ledger.queue_summary(self.st(), [])
            self.assertIn("**Decisions for Max (0)**: none open.", text)
            self.assertIn("- g9: G9-B1 (bill, 0 min)", text)
            self.assertIn("**Next checkpoint**: Thu 12 Nov 12:00 UTC: Checkpoint 1: notes due", text)
            self.assertLess(len(text.splitlines()), 30)  # one phone screen
            with self.assertRaises(SystemExit):
                self.lg("g9").issue_refresh()  # no issue yet, and --create not given
            r = self.lg("g9").issue_refresh(create=True)
            self.assertEqual(r["number"], 21)
            self.assertEqual(self.st().load("issues.json")["queue"], 21)
            with self.assertRaises(ledger.Conflict):
                self.lg("bill").decision("Sub-agents for executors?", "Allow them?")
            i = self.lg("g9").decision("Sub-agents for executors?", "Allow them?")
            self.assertEqual(i["title"], "DECISION: Sub-agents for executors?")
            self.assertEqual(issues[22]["labels"], ["decision"])
            self.assertTrue(any(c[:2] == ("POST", "labels") for c in calls))
            self.assertIn("**Decisions for Max (1)**", issues[21]["body"])
            comments[22] = [dict(id=5, body=ledger.MARK + " our own note", html_url="u5", created_at="2026-11-12T07:01:00Z"),
                            dict(id=7, body="Yes, up to two per lead.", html_url="u7", created_at="2026-11-12T07:02:00Z")]
            self.lg("g9").issue_refresh()
            replies = [m for m in self.st().unread("g9") if m["subject"].startswith("Max on #22")]
            self.assertEqual(len(replies), 1)
            self.assertIn("Yes, up to two per lead.", replies[0]["body"])
            self.lg("g9").issue_refresh()
            self.assertEqual(len([m for m in self.st().unread("g9") if m["subject"].startswith("Max on #22")]), 1)  # not copied twice
            self.lg("g9").decision_close(22, "allowed, two per lead")
            self.assertEqual(issues[22]["state"], "closed")
            self.assertIn("**Decisions for Max (0)**", issues[21]["body"])
        finally:
            ledger.gh = real

    def test_result_check_scores_and_sweep_cap(self):
        self.boot({"experiments/E9-3.md": EXPERIMENT}, "sam")
        self.lg("sam").lease("E9-3", 2)
        with self.assertRaises(ledger.Conflict) as cm:
            self.lg("sam").submit("E9-3", "done", None, None)
        self.assertIn("'Evidence:', 'Sample:', 'Revisit if:'", str(cm.exception))
        half = EXPERIMENT.replace("## Result\n\n_not yet_", "## Result\n\n96.4% equivalent.\n\n- **Evidence:** double-dummy proxy")
        self.lg("sam").edit("E9-3", half)
        with self.assertRaises(ledger.Conflict) as cm:
            self.lg("sam").submit("E9-3", "done", None, None)
        self.assertIn("'Sample:', 'Revisit if:'", str(cm.exception))
        full = half.replace("double-dummy proxy", "double-dummy proxy\n- Sample: 5,120 decisions, 95% interval 95.8 to 96.9\n"
                                                  "- Revisit if: the class rule changes")
        self.lg("sam").edit("E9-3", full)
        self.lg("sam").submit("E9-3", "done", None, None)
        lg = self.lg("g9")
        a = lg.new("Cheap", "bidding", "module", "pool", "high", [], None, "", extra=dict(value="0.01 IMPs/board", effort="1"))
        b = lg.new("Rich", "bidding", "module", "pool", "high", [], None, "", extra=dict(value="0.2 IMPs/board", effort="4", probability="0.5"))
        c = lg.new("Unscored", "bidding", "module", "pool", "high", [], None, "")
        st = self.st()
        self.assertAlmostEqual(ledger.score(st.doc(b)), 0.025)
        self.assertIsNone(ledger.score(st.doc(c)))
        out = io.StringIO()
        os.environ["WORKQ_CACHE"] = str(self.root / "cache-cli3")
        with redirect_stdout(out):
            ledger.main(["--repo", str(self.bare), "--channel", "team/gen9", "--as", "bill", "next"])
        ids = [l.split()[0] for l in out.getvalue().splitlines()]
        self.assertEqual(ids[:3], [b, a, c])
        with self.assertRaises(ledger.Malformed):
            lg.new("Bad", "bidding", "module", "pool", "high", [], None, "", extra=dict(probability="1.5"))
        for n in (1, 2):
            lg.new(f"Sweep {n}", "bidding", "experiment", "bill", "low", [], None, "", extra=dict(sweep="yes"))
        with self.assertRaises(ledger.Conflict) as cm:
            lg.new("Sweep 3", "bidding", "experiment", "bill", "low", [], None, "", extra=dict(sweep="yes"))
        self.assertIn("the cap is 2", str(cm.exception))
        lg.new("Sweep elsewhere", "signals", "experiment", "sam", "low", [], None, "", extra=dict(sweep="yes"))

    def test_watch_stars_the_box_events_of_your_own_jobs(self):
        self.boot(None, "bill")
        job = dict(id="e9-1", box="azure4", owner="bill", priority=2, cores=4, source=dict(branch="b", commit="abcdef1"),
                   argv=["x"], progress=dict(results="results.jsonl", target=10))
        self.lg("g9").mutate("jobs", lambda st: st.save("boxq/azure4/e9-1.json", job))
        self.lg("azure4").mutate("box", lambda st: st.event("job", "azure4/e9-1", "running"))
        os.environ["WORKQ_CACHE"] = str(self.root / "cache-cli-bill")
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            ledger.main(["--repo", str(self.bare), "--channel", "team/gen9", "--as", "bill", "watch", "--no-heartbeat"])
        self.assertRegex(out.getvalue(), r"\* \S+ \S+ azure4 +job +azure4/e9-1: running")

    def test_owner_proposed_and_blocked_rules(self):
        self.boot({"tasks/G9-W8.md": task("G9-W8", owner="will"), "tasks/G9-W7.md": task("G9-W7", state="proposed"),
                   "tasks/G9-W6.md": task("G9-W6")}, "bill", "will")
        with self.assertRaises(ledger.Conflict) as cm:
            self.lg("bill").lease("G9-W8", 1)
        self.assertIn("owned by will", str(cm.exception))
        with self.assertRaises(ledger.Conflict) as cm:
            self.lg("will").lease("G9-W7", 1)
        self.assertIn("needs g9's agreement", str(cm.exception))
        self.lg("g9").lease("G9-W7", 1)  # the lead may lease anything
        self.lg("bill").lease("G9-W6", 1)  # pool
        with self.assertRaises(SystemExit):
            self.lg("will").lease("G9-W8", 5)  # over the four-hour cap
        self.lg("bill").block("G9-W6", "needs a box")
        self.assertTrue(any("blocked" in m["subject"] for m in self.st().unread("g9")))
        with self.assertRaises(ledger.Conflict):
            self.lg("bill").lease("G9-W6", 1)
        self.lg("g9").reopen("G9-W6", "box free")
        self.lg("bill").lease("G9-W6", 1)
        with self.assertRaises(ledger.Conflict):
            self.lg("bill").set_fields("G9-W6", [("state", "resolved")])
        self.lg("bill").set_fields("G9-W6", [("priority", "high"), ("reviewer", "will")])
        self.assertEqual(self.st().doc("G9-W6").get("reviewer"), "will")

    def test_submit_review_resolve(self):
        self.boot({"tasks/G9-B1.md": TASK, "experiments/E9-3.md": EXPERIMENT}, "bill", "sam")
        self.lg("bill").lease("G9-B1", 2)
        with self.assertRaises(ledger.Conflict):
            self.lg("sam").submit("G9-B1", "not mine", None, None)
        self.lg("bill").submit("G9-B1", "note is up", "feature/gen9-bidding-design", "abc1234")
        d = self.st().doc("G9-B1")
        self.assertEqual((d.get("state"), d.get("branch"), d.get("lease_until")), ("submitted", "feature/gen9-bidding-design", ""))
        review = [m for m in self.st().unread("g9") if m["subject"].startswith("G9-B1 submitted")]
        self.assertEqual(len(review), 1)
        self.assertIn("commit abc1234", review[0]["body"])
        self.assertEqual(review[0]["task"], "G9-B1")
        with self.assertRaises(ledger.Conflict):
            self.lg("bill").resolve("G9-B1", "accepted", "self-review")
        self.lg("g9").reopen("G9-B1", "add the WBF fields", same_holder=True)
        self.assertEqual(self.st().doc("G9-B1").get("state"), "leased")
        self.lg("bill").submit("G9-B1", "WBF fields added", None, "def5678")
        with self.assertRaises(ledger.Conflict):
            self.lg("g9").resolve("G9-B1", "adopted", "")  # an experiment's word
        self.lg("g9").resolve("G9-B1", "accepted", "good")
        self.assertTrue(any(m["subject"].startswith("G9-B1 resolved (accepted)") for m in self.st().unread("bill")))
        self.lg("sam").lease("E9-3", 2)
        self.lg("sam").edit("E9-3", EXPERIMENT.replace("## Result\n\n_not yet_", "## Result\n\n97% equivalent.\n\nEvidence: double-dummy proxy\n"
                                                       "Sample: 5,000 decisions\nRevisit if: never"))
        self.lg("sam").submit("E9-3", "97% equivalent", "research/gen9-spots", None)
        self.lg("g9").resolve("E9-3", "adopted", "")
        self.assertIn("| [E9-3](experiments/E9-3.md) |", self.text("STATUS.md"))

    def test_new_ids_and_notice(self):
        self.boot({"tasks/G9-B1.md": TASK, "experiments/E9-3.md": EXPERIMENT}, "bill")
        tid = self.lg("g9").new("Parser", "bidding", "module", "bill", "high", ["G9-B1"], "2026-11-12T18:00Z", "")
        self.assertEqual(tid, "G9-B2")
        eid = self.lg("bill").new("Boards to identify a system", "bidding", "experiment", "bill", "medium", [], None, "", proposed=True)
        self.assertEqual(eid, "E9-4")
        st = self.st()
        e = st.doc("E9-4")
        self.assertEqual((e.folder, e.get("state")), ("experiments", "proposed"))
        self.assertIn("## Stopping rule", e.body)
        self.assertTrue(any(m.get("task") == "G9-B2" for m in st.unread("bill")))
        with self.assertRaises(ledger.Conflict):
            self.lg("g9").new("Again", "bidding", "module", "bill", "high", [], None, "", did="G9-B2")

    def test_messages_are_never_edited_and_read_is_per_agent(self):
        self.boot(None, "will", "sam")
        mid = self.lg("g9").send("will", "Set up the test runner", "Please, today.", None, None)
        self.assertEqual(mid, "20261112T0700Z-g9-set-up-the-test-runner")
        self.lg("g9").send("all", "Checkpoint at 12:00", "Notes due.", None, None)
        path = f"inbox/will/{mid}.md"
        raw = self.text(path)
        self.assertTrue(raw.startswith("Set up the test runner\n\ng9, 12 Nov 07:00 UTC.\n\nPlease, today.\n"))
        self.assertEqual(len(self.st().unread("will")), 2)
        self.lg("will").mark_read(mid)
        self.assertEqual(self.text(path), raw)
        self.assertEqual([m["subject"] for m in self.st().unread("will")], ["Checkpoint at 12:00"])
        self.assertEqual(len(self.st().unread("sam")), 1)
        self.lg("will").mark_read(all_=True)
        self.assertEqual(self.st().unread("will"), [])
        self.clock[0] = T0 + timedelta(minutes=1)
        mid2 = self.lg("g9").send("will", "Set up the test runner", "Again.", None, None)
        self.assertNotEqual(mid2, mid)
        self.assertEqual(len(self.st().unread("will")), 1)

    def test_fleet_table(self):
        board = ("# Board\n\n## Allocation (edit in place)\n\n| Box | Now | Next |\n| --- | --- | --- |\n"
                 "| azure1 (Bridgebots) | g8: Gen 8 experiments | g8 |\n| azure2 (Bridgebots2) | g7: `71s-32~7s-32` | g7 |\n\n## Log\n\n| azure9 | no | |\n")
        alloc = ledger.board_allocation(board)
        self.assertEqual(alloc, {"azure1": "g8: Gen 8 experiments", "azure2": "g7: `71s-32~7s-32`"})
        snap = dict(at="2026-11-12T07:00:00Z", boxes=[
            dict(box="azure1", board_now=alloc["azure1"], heartbeat="2026-11-12T06:58:00Z", cpus=8, load=7.9, mem_free_gb=20.1,
                 mem_total_gb=31.3, disk_free_gb=100, running="20261112T065500Z-000001-g8-job", pending=1),
            dict(box="azure2", board_now=alloc["azure2"], heartbeat="2026-11-12T06:30:00Z", cpus=8, load=8.0, mem_free_gb=25,
                 mem_total_gb=31.3, disk_free_gb=114, running=None, pending=0),
            dict(box="azure7", board_now=None)])
        text = "\n".join(ledger.render_fleet(snap, {}))
        self.assertIn("| azure1 | 11-12 06:58 | 7.9 / 8 | 20.1 of 31.3 GB | 100 GB | running g8-job, 1 waiting | g8: Gen 8", text)
        self.assertIn("(**30 min old**)", text)
        self.assertIn("| azure7 | none |", text)

    def test_cli(self):
        self.boot({"tasks/G9-W1.md": task("G9-W1", owner="will")}, "will", "dave")
        os.environ["WORK_CACHE"] = str(self.root / "cache-cli")
        base = ["--repo", str(self.bare), "--channel", "team/gen9"]

        def run(*args):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = ledger.main(base + list(args))
            return code, out.getvalue(), err.getvalue()
        code, out, _ = run("--as", "will", "next")
        self.assertIn("G9-W1", out)
        self.assertEqual(run("--as", "will", "lease", "G9-W1", "--hours", "2")[0], 0)
        code, _, err = run("--as", "bill", "lease", "G9-W1")
        self.assertEqual(code, 3)
        self.assertIn("refused:", err)
        self.assertEqual(run("--as", "will", "submit", "G9-W1", "--note", "done", "--branch", "feature/x")[0], 0)
        code, out, _ = run("--as", "dave", "watch", "--no-heartbeat")  # a module of will's: dave reviews it
        self.assertIn("G9-W1 waits for your review", out)
        self.assertIn("unread for dave: 1", out)
        code, out, _ = run("--as", "dave", "inbox")
        self.assertIn("G9-W1 submitted for your review", out)
        self.assertEqual(run("--as", "dave", "resolve", "G9-W1", "--resolution", "accepted")[0], 0)
        code, out, _ = run("show", "G9-W1")
        self.assertIn("resolution: accepted", out)
        code, out, _ = run("export")
        self.assertEqual(json.loads(out)["docs"]["G9-W1"]["state"], "resolved")
        self.assertEqual(run("--as", "g9", "refresh")[0], 0)
        with self.assertRaises(SystemExit):
            run("--as", "all", "hello")


if __name__ == "__main__":
    unittest.main()
