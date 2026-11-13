"""End-to-end tests of the boxctl agent and client against a local bare repository.

They exercise the queue, ordering, timeouts, the status snapshot, restart safety and
a live agent. They do not exercise GitHub, the deploy key or the systemd unit.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "ops" / "boxctl" / "agent.py"
CLIENT = ROOT / "ops" / "boxctl" / "client.py"


class BoxctlEndToEnd(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        self.url = remote.as_uri()
        self.state = self.tmp / "state"
        self.config = self.tmp / "config.json"
        self.config.write_text(json.dumps({
            "box": "t1", "repo": self.url, "state_dir": str(self.state),
            "workdir": str(self.tmp), "poll_s": 0.2, "heartbeat_s": 3600}))
        self.env = dict(os.environ, BOXCTL_CACHE=str(self.tmp / "cache"), BOXCTL_REPO=self.url)
        self.order = self.tmp / "order.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def agent_once(self):
        r = subprocess.run([sys.executable, str(AGENT), "--config", str(self.config), "--once"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def client(self, *args):
        r = subprocess.run([sys.executable, str(CLIENT), *args], capture_output=True, text=True,
                           timeout=120, env=self.env)
        self.assertIn(r.returncode, (0, 1), r.stdout + r.stderr)
        return r

    def send(self, slug, cmd, *extra):
        return self.client("send", "t1", "--slug", slug, "--cmd", cmd, *extra).stdout.strip()

    def result(self, cid):
        return json.loads(self.client("show", "t1", cid, "--json").stdout)

    def test_queue_runs_once_in_order_and_publishes(self):
        ids = [self.send("first", f"echo first >> {self.order}; echo out-first; exit 3"),
               self.send("second", f"echo second >> {self.order}"),
               self.send("slow", "sleep 30", "--timeout", "1")]
        self.agent_once()
        self.assertEqual(self.order.read_text(), "first\nsecond\n")
        first, second, slow = (self.result(i) for i in ids)
        self.assertEqual(first["exit_code"], 3)
        self.assertIn("out-first", first["output_tail"])
        self.assertEqual(second["exit_code"], 0)
        self.assertTrue(slow["timed_out"])
        self.assertLess(slow["duration_s"], 15)

        third = self.send("third", f"echo third >> {self.order}")
        self.agent_once()  # earlier commands must not run again
        self.assertEqual(self.order.read_text(), "first\nsecond\nthird\n")
        self.assertEqual(self.result(third)["exit_code"], 0)
        status = self.client("status", "t1").stdout
        self.assertIn("box t1: heartbeat", status)
        self.assertIn(third, status)
        self.assertIn("t1", self.client("boxes").stdout)

    def test_interrupted_command_is_reported_not_rerun(self):
        cid = self.send("x", f"echo ran >> {self.order}")
        self.state.mkdir(parents=True)
        (self.state / "state.json").write_text(json.dumps({"done": [], "started": [cid]}))
        self.agent_once()
        self.assertFalse(self.order.exists())
        self.assertTrue(self.result(cid)["interrupted"])

    def test_heartbeat_without_control_branch(self):
        self.agent_once()
        status = self.client("status", "t1").stdout
        self.assertIn("box t1: heartbeat", status)
        self.assertIn("no control branch yet", status)

    def test_run_against_live_agent(self):
        agent = subprocess.Popen([sys.executable, str(AGENT), "--config", str(self.config)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            r = self.client("run", "t1", "--cmd", "echo live-$BOXCTL_BOX", "--max-wait", "60",
                            "--interval", "0.5")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("live-t1", r.stdout)
        finally:
            agent.terminate()
            out, _ = agent.communicate(timeout=30)
        self.assertEqual(agent.returncode, 0, out)
        self.assertIn("boxctl agent stopped", out)


if __name__ == "__main__":
    unittest.main()
