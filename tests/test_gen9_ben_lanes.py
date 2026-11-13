"""ops/gen9_ben_lanes.py without a box: the deal split, the commands it would run, and the merge of lane results."""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gen9_ben_lanes", ROOT / "ops" / "gen9_ben_lanes.py")
lanes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lanes)


def lane(out: Path, k: int, indices, identity="i-ben", seed=91, pair="9p-32~ben"):
    d = out / f"lane-{k}"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps(dict(seed=seed, pair_schedule=[pair], bots={
        "9p-32": {"identity": "i-9p"}, "ben": {"identity": identity}})))
    (d / "results.jsonl").write_text("".join(json.dumps(dict(index=i, common=float(i % 3 - 1), native=float(i % 3 - 1), cpu=10.0,
                                                             systems=None)) + "\n" for i in indices))


class BenLanesTest(unittest.TestCase):
    def test_split_covers_every_deal_once(self):
        for first, deals, n in ((0, 16, 2), (100, 17, 4), (5, 3, 3)):
            ranges = lanes.split(first, deals, n)
            covered = [i for f, c in ranges for i in range(f, f + c)]
            self.assertEqual(covered, list(range(first, first + deals)))
            self.assertLessEqual(max(c for _, c in ranges) - min(c for _, c in ranges), 1)
        with self.assertRaises(SystemExit):
            lanes.split(0, 1, 2)

    def test_dry_run_commands(self):
        out = io.StringIO()
        argv = ["gen9_ben_lanes.py", "--dry-run", "run", "--pair", "9p-32~ben", "--deals", "16", "--lanes", "2", "--seed", "91",
                "--source", "/w/capsule/recovery", "--bots", "configs/gen9-proto-bots.json", "--out", "/w/runs/w7"]
        with patch.object(sys, "argv", argv), redirect_stdout(out):
            lanes.main()
        text = out.getvalue()
        self.assertIn("+ sudo ip netns add g9ben-w7-1", text)
        self.assertIn("+ sudo ip -n g9ben-w7-2 link set lo up", text)
        self.assertIn("--unit=g9-ben-w7-1", text)
        self.assertIn("--property=NetworkNamespacePath=/run/netns/g9ben-w7-2", text)
        self.assertIn("src/gameapi.py --config /w/capsule/recovery/assets/ben-16.conf --host 127.0.0.1 --port 8087 --record false", text)
        self.assertIn("--property=Restart=on-failure", text)
        self.assertIn("scripts/gen9_match.py --source /w/capsule/recovery --pair '9p-32~ben' --deals 8 --first 0 --seed 91 --workers 1 --out /w/runs/w7/lane-1", text)
        self.assertIn("--deals 8 --first 8 --seed 91 --workers 1 --out /w/runs/w7/lane-2", text)
        self.assertIn("--setenv=BRIDGE_DDS_CACHE=/w/runs/w7/lane-1.dds.sqlite", text)
        self.assertIn("lane 2: (dry run) would wait for BEN in g9ben-w7-2", text)
        self.assertIn("+ sudo systemctl stop g9-ben-w7-2", text)
        self.assertIn("+ sudo ip netns delete g9ben-w7-2", text)

    def dry(self, *args):
        out = io.StringIO()
        with patch.object(sys, "argv", ["gen9_ben_lanes.py", "--dry-run", *args]), redirect_stdout(out):
            lanes.main()
        return out.getvalue()

    def test_two_runs_on_one_box_use_different_names_and_ben64_its_own_server(self):
        base = ["run", "--pair", "r9b-32~ben", "--deals", "8", "--lanes", "2", "--seed", "910", "--source", "/w/capsule/recovery"]
        one = self.dry(*base, "--out", "/w/g9/runs/e9-10-r9b-ben16")
        two = self.dry(*base, "--out", "/w/g9/runs/e9-10-8x-ben16")
        self.assertIn("--unit=g9-ben-e910r9bben16-1", one)
        self.assertIn("--unit=g9-lane-e9108xben16-2", two)
        self.assertNotIn("g9ben-e910r9bben16", two)
        b64 = self.dry("run", "--pair", "r9b-32~ben64", "--deals", "8", "--lanes", "2", "--seed", "910", "--source", "/w/capsule/recovery",
                       "--out", "/w/g9/runs/b64", "--ben-bot", "ben64")
        self.assertIn("src/gameapi.py --config /w/capsule/recovery/assets/ben-64.conf --host 127.0.0.1 --port 8089 --record false", b64)
        self.assertIn("at 127.0.0.1:8089", b64)
        self.assertIn("--unit=g9-ben-x-1", self.dry("down", "--lanes", "1", "--tag", "x") + self.dry("up", "--lanes", "1", "--tag", "x"))

    def test_merge(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            lane(out, 1, range(0, 8))
            lane(out, 2, range(8, 16))
            (out / "lanes.json").write_text(json.dumps([dict(lane=1, seconds=360), dict(lane=2, seconds=400)]))
            s = lanes.merge(out)
            rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines()]
            self.assertEqual([r["index"] for r in rows], list(range(16)))
            self.assertEqual((s["boards"], s["lanes"], s["seed"], s["boards_per_hour"]), (16, 2, 91, 144))
            self.assertIn("common", s)
            self.assertEqual(json.loads((out / "summary.json").read_text())["boards"], 16)

    def test_merge_refuses_mismatched_lanes(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            lane(out, 1, range(0, 8))
            lane(out, 2, range(7, 16))
            with self.assertRaises(SystemExit) as cm:
                lanes.merge(out)
            self.assertIn("deal 7 was played in two lanes", str(cm.exception))
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            lane(out, 1, range(0, 8))
            lane(out, 2, range(8, 16), identity="another-ben")
            with self.assertRaises(SystemExit) as cm:
                lanes.merge(out)
            self.assertIn("different bots", str(cm.exception))


if __name__ == "__main__":
    unittest.main()


class ServeTest(unittest.TestCase):
    """serve: a stand-in server on a free port, a command that connects to it; the command's code comes back and the
    server is gone afterwards; a taken port is refused."""

    def setUp(self):
        lanes.DRY = False  # main() --dry-run in another test leaves the module flag set

    def free_port(self):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def test_serve_runs_the_command_while_the_server_answers(self):
        import subprocess
        port = self.free_port()
        server = [sys.executable, "-c", f"import socket,time;s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
                                        f"s.bind(('127.0.0.1',{port}));s.listen();time.sleep(120)"]
        cmd = [sys.executable, "-c", f"import socket,sys;socket.create_connection(('127.0.0.1',{port}),timeout=2).close();sys.exit(3)"]
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            code = lanes.serve(Path(d), Path(d), Path(d) / "ben-64.conf", port, cmd, wait=20, server=server)
        self.assertEqual(code, 3)
        self.assertTrue(lanes.port_free(port))

    def test_serve_refuses_a_taken_port(self):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); s.listen()
            port = s.getsockname()[1]
            with tempfile.TemporaryDirectory() as d, self.assertRaises(SystemExit):
                lanes.serve(Path(d), Path(d), Path(d) / "c", port, ["true"], wait=5, server=["sleep", "5"])

    def test_serve_command_line(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "assets").mkdir()
            (Path(d) / "assets" / "ben-64.conf").write_text("[models]\n")
            buf = io.StringIO()
            with patch.object(sys, "argv", ["gen9_ben_lanes.py", "--dry-run", "serve", "--ben-bot", "ben64", "--source", d,
                                            "--", "python3", "ops/run_gen9_cohort.py", "--workers", "1"]), redirect_stdout(buf):
                self.assertEqual(lanes.main(), 0)
            out = buf.getvalue()
            self.assertIn("--port 8089", out)
            self.assertIn(str(Path(d) / "assets" / "ben-64.conf"), out)
            self.assertIn("ops/run_gen9_cohort.py --workers 1", out)
