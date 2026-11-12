"""Tests for tools/queue_metrics.py on a synthetic channel (no git needed)."""
import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import queue_metrics as qm  # noqa: E402

TASK = """---
id: {id}
title: t
area: a
kind: {kind}
owner: {owner}
state: {state}
holder:
lease_until:
---
## Goal

g

## Log

{log}
"""


def write(root, did, log, kind="module", owner="bill", state="resolved"):
    folder = root / ("experiments" if did.startswith("E") else "tasks")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{did}.md").write_text(TASK.format(id=did, kind=kind, owner=owner, state=state, log="\n".join(log)))


class QueueMetrics(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        write(self.root, "G9-B1", [  # the hand-written form from before workq
            "- 2026-11-12T06:47Z g9: created.",
            "- 2026-11-12T06:50Z bill: leased; note goes to docs.",
            "- 2026-11-12T06:55Z bill: submitted. On a branch.",
            "- 2026-11-12T07:03Z g9: reviewed and accepted; merged."])
        write(self.root, "G9-D2", [  # workq's form: lease with an end, renewal, give back, lease again, sent back, resolved
            "- 2026-11-12T06:47Z g9: created.",
            "- 2026-11-12T08:00Z dave: leased until 2026-11-12T09:00Z",
            "- 2026-11-12T08:50Z dave: lease renewed until 2026-11-12T09:30Z",
            "- 2026-11-12T09:10Z dave: given back: blocked on data",
            "- 2026-11-12T09:40Z sam: leased until 2026-11-12T10:00Z",
            "- 2026-11-12T10:20Z sam: submitted (feature/x at abc1234)",
            "- 2026-11-12T10:30Z will: sent back to sam: a test fails",
            "- 2026-11-12T10:50Z sam: submitted (feature/x at abc1235)",
            "- 2026-11-12T11:00Z will: resolved: accepted. ok"], owner="dave")
        write(self.root, "G9-S9", ["- 2026-11-12T06:47Z g9: created as proposed.",
                                   "- 2026-11-12T07:30Z g9: set state=open"], owner="sam", state="open")
        write(self.root, "E9-1", ["- 2026-11-12T06:47Z g9: registered with predictions.",
                                  "- 2026-11-12T07:00Z bill: leased until 2026-11-12T11:00Z",
                                  "- 2026-11-12T08:00Z bill: submitted (b at 1234567): result",
                                  ], kind="experiment", state="submitted")
        (self.root / "inbox" / "g9").mkdir(parents=True)
        (self.root / "inbox" / "g9" / "20261112T0800Z-bill-e9-1-submitted.md").write_text("x")
        (self.root / "agents").mkdir()
        (self.root / "agents" / "g9.json").write_text(json.dumps(dict(name="g9", read_until="20261112T0751Z", read_ids=[])))
        self.c = qm.collect(self.root, qm.ts("2026-11-12T12:00Z"))
        self.docs = {d["id"]: d for d in self.c["docs"]}

    def test_hand_written_history(self):
        d = self.docs["G9-B1"]
        self.assertEqual(qm.mins(d["waits"][0]["end"] - d["waits"][0]["start"]), 3)
        (lease,) = d["leases"]
        self.assertEqual((lease["how"], lease["box"]), ("submitted", timedelta(hours=4)))  # no end written: the 4-hour box
        (r,) = d["reviews"]
        self.assertEqual((r["reviewer"], r["outcome"], qm.mins(r["end"] - r["start"])), ("g9", "accepted", 8))

    def test_renewal_give_back_and_sent_back(self):
        d = self.docs["G9-D2"]
        self.assertEqual([l["how"] for l in d["leases"]], ["given back", "submitted"])
        self.assertEqual(d["leases"][0]["until"], qm.ts("2026-11-12T09:30Z"))       # the renewal moved the end
        self.assertEqual(d["leases"][1]["over"], timedelta(minutes=20))             # submitted 20 minutes past its end
        self.assertEqual([qm.mins(w["end"] - w["start"]) for w in d["waits"]], [73, 30])
        self.assertEqual([r["outcome"] for r in d["reviews"]], ["sent back", "accepted"])
        self.assertEqual((d["given_back"], d["sent_back"]), (1, 1))

    def test_proposed_waits_from_when_it_was_opened(self):
        d = self.docs["G9-S9"]
        (w,) = d["waits"]
        self.assertEqual((w["start"], w["end"]), (qm.ts("2026-11-12T07:30Z"), None))

    def test_page(self):
        page = qm.render(self.c)
        self.assertIn("Waiting now: E9-1 (experiment, from bill, 240)", page)
        self.assertIn("Unreviewed for more than two hours (the workplan's signal that a lead or the architect is the bottleneck): E9-1 240", page)
        self.assertIn("G9-D2 sam by 20", page)                                    # ran past its end
        self.assertIn("| g9 | 1 |", page)                                         # one message, unread
        self.assertIn("G9-S9 270", page)                                          # open and unleased now


if __name__ == "__main__":
    unittest.main()
