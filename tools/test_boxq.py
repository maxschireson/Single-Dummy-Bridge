"""Tests for tools/boxq.py: the plan, job checks, rates, and the loop against a local repository with plain processes.
Run: python3 tools/test_boxq.py"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("boxq", HERE / "boxq.py")
bq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bq)
wq = bq.wq

WORKER = '''import sys, time
from pathlib import Path
out, target, delay = Path(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
f = out / "results.jsonl"
done = len(f.read_text().splitlines()) if f.exists() else 0   # resumes like gen8_match
for i in range(done, target):
    time.sleep(delay)
    with f.open("a") as h:
        h.write('{"index": %d}\\n' % i)
'''


def job(jid, priority, cores, target=4, delay=0.05, preemptible=True, commit=None, **kw):
    return dict(dict(id=jid, box="testbox", owner="g9", priority=priority, cores=cores, source=dict(branch="feature/x", commit=commit or "0" * 7),
                     argv=["{python}", "worker.py", "{out}", str(target), str(delay)], progress=dict(results="results.jsonl", target=target),
                     preemptible=preemptible, publish=["results.jsonl"], state="queued"), **kw)


class PlanTest(unittest.TestCase):
    def test_priority_and_gap_filling(self):
        jobs = {"a": job("a", 2, 4), "b": job("b", 1, 6), "c": job("c", 3, 2)}
        start, stop = bq.plan(jobs, {}, 8)
        self.assertEqual((start, stop), (["b", "c"], []))  # a (4 cores) does not fit beside b; c (2) fills the gap

    def test_preemption_waits_for_the_cores(self):
        jobs = {"low": job("low", 5, 4), "low2": job("low2", 6, 4), "big": job("big", 1, 8)}
        status = {"low": dict(state="running"), "low2": dict(state="running")}
        start, stop = bq.plan(jobs, status, 8)
        self.assertEqual((start, stop), ([], ["low", "low2"]))  # big starts on a later pass, once both are gone
        start, stop = bq.plan(jobs, {"low": dict(state="paused"), "low2": dict(state="paused")}, 8)
        self.assertEqual((start, stop), (["big"], []))

    def test_non_preemptible_keeps_its_cores_and_cancel_stops(self):
        jobs = {"fixed": job("fixed", 9, 6, preemptible=False), "urgent": job("urgent", 1, 4), "small": job("small", 2, 2)}
        start, stop = bq.plan(jobs, {"fixed": dict(state="running")}, 8)
        self.assertEqual((start, stop), (["small"], []))
        jobs["fixed"]["state"] = "cancelled"
        self.assertEqual(bq.plan(jobs, {"fixed": dict(state="running")}, 8)[1], ["fixed"])

    def test_final_jobs_are_left_alone(self):
        jobs = {"a": job("a", 1, 8)}
        self.assertEqual(bq.plan(jobs, {"a": dict(state="done")}, 8), ([], []))

    def test_validation(self):
        bq.validate(job("ok", 1, 2), "testbox", 8)
        for bad, why in ((dict(job("x", 1, 2), cores=9), "cores"), (dict(job("x", 1, 2), priority=0), "priority"),
                         (dict(job("X y", 1, 2)), "id"), (dict(job("x", 1, 2), source=dict(branch="b", commit="zz")), "source"),
                         (dict(job("x", 1, 2), progress=dict(results="r.jsonl")), "progress"), (dict(job("x", 1, 2), box="other"), "box")):
            with self.assertRaises(ValueError) as cm:
                bq.validate(bad, "testbox", 8)
            self.assertIn(why, str(cm.exception))

    def test_rate_and_eta(self):
        now = datetime(2026, 11, 12, 14, 0, tzinfo=timezone.utc)
        samples = [[bq.stamp(now - timedelta(minutes=40)), 0], [bq.stamp(now - timedelta(minutes=20)), 100], [bq.stamp(now), 400]]
        rate, eta = bq.rate_and_eta(samples, 400, 1300, now)
        self.assertEqual(rate, 900.0)  # 300 boards in the last 20 minutes; the 40-minute sample is outside the window
        self.assertEqual(eta, "2026-11-12T15:00:00Z")


class LoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.bare = root / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.bare)], check=True)
        src = root / "srcrepo"
        subprocess.run(["git", "init", "-q", "-b", "feature/x", str(src)], check=True)
        (src / "worker.py").write_text(WORKER)
        g = ["git", "-C", str(src), "-c", "user.name=t", "-c", "user.email=t@invalid"]
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-q", "-m", "worker"], check=True)
        subprocess.run(g + ["push", "-q", str(self.bare), "feature/x"], check=True)
        self.commit = subprocess.run(g[:3] + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        os.environ["WORKQ_CACHE"] = str(root / "cache-g9")
        self.g9 = wq.Ledger(str(self.bare), "team/gen9", "g9", lead="g9")
        self.g9.mutate("seed", lambda st: st.put("README.md", b"# channel\n"), allow_create=True)
        os.environ["WORKQ_CACHE"] = str(root / "cache-box")
        self.box = bq.Box("testbox", 2, root / "work", executor=bq.Local(), python=sys.executable, repo_url=str(self.bare))
        self.root = root

    def tearDown(self):
        for p in self.box.exec.procs.values():
            if p.poll() is None:
                p.kill()
        os.environ.pop("WORKQ_CACHE", None)
        self.tmp.cleanup()

    def submit(self, j):
        os.environ["WORKQ_CACHE"] = str(self.root / "cache-g9")
        self.g9.job_submit(j)
        os.environ["WORKQ_CACHE"] = str(self.root / "cache-box")

    def run_until(self, cond, limit=60):
        t = time.time()
        while time.time() - t < limit:
            s = self.box.once()
            if cond(s["jobs"]):
                return s
            time.sleep(0.2)
        self.fail(f"not reached: {json.dumps(self.box.status['jobs'])[:600]}")

    def test_priority_order_status_and_results(self):
        self.submit(job("low", 2, 2, commit=self.commit))
        time.sleep(1.1)
        self.submit(job("high", 1, 2, commit=self.commit))
        s = self.box.once()
        self.assertEqual(s["jobs"]["high"]["state"], "running")
        self.assertEqual(s["jobs"]["low"]["state"], "waiting")
        self.run_until(lambda J: J["low"]["state"] == "done")
        self.assertEqual(self.box.status["jobs"]["high"]["state"], "done")
        self.assertEqual(self.box.status["jobs"]["low"]["boards"], 4)
        st = self.g9.snapshot()
        status = st.load("boxq/testbox/status.json")
        self.assertEqual(status["jobs"]["low"]["state"], "done")
        text = st.get("STATUS.md").decode()
        self.assertIn("## Box queue", text)
        self.assertIn("| high |  | g9 | 1 | 2 | done | 4 of 4 |", text)
        pub = wq.Store(str(self.bare), self.box.status["jobs"]["low"]["published"].split("@")[0])
        files = pub.read(pub.fetch())
        self.assertEqual(len(files["results.jsonl"].decode().splitlines()), 4)
        self.assertIn(b'"id": "low"', files["job.json"])

    def test_preemption_pauses_and_resumes_without_losing_boards(self):
        self.submit(job("slow", 5, 2, target=40, delay=0.1, commit=self.commit))
        self.run_until(lambda J: J["slow"]["state"] == "running" and J["slow"]["boards"] >= 3)
        self.submit(job("urgent", 1, 2, target=3, commit=self.commit))
        self.run_until(lambda J: J["slow"]["state"] == "paused")
        self.run_until(lambda J: J.get("urgent", {}).get("state") == "done")
        self.run_until(lambda J: J["slow"]["state"] == "done", limit=90)
        lines = (self.root / "work" / "runs" / "slow" / "results.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(l)["index"] for l in lines], list(range(40)))  # every board once, resumed after the pause

    def test_cancel_and_bad_job_files(self):
        self.submit(job("doomed", 3, 2, target=200, delay=0.1, commit=self.commit))
        self.run_until(lambda J: J["doomed"]["state"] == "running")
        os.environ["WORKQ_CACHE"] = str(self.root / "cache-g9")
        self.g9.job_cancel("testbox", "doomed", "not needed")
        self.g9.mutate("bad", lambda st: st.put("boxq/testbox/broken.json", b'{"id": "broken"}'))
        os.environ["WORKQ_CACHE"] = str(self.root / "cache-box")
        s = self.run_until(lambda J: J["doomed"]["state"] == "cancelled")
        self.assertTrue(any("broken.json" in b for b in s["bad_jobs"]))
        with self.assertRaises(wq.Conflict):
            os.environ["WORKQ_CACHE"] = str(self.root / "cache-other")
            wq.Ledger(str(self.bare), "team/gen9", "sam", lead="g9").job_submit(job("not-mine", 1, 1, commit=self.commit))


if __name__ == "__main__":
    unittest.main()
