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
        self.assertIn("+ sudo ip netns add g9ben-1", text)
        self.assertIn("+ sudo ip -n g9ben-2 link set lo up", text)
        self.assertIn("--unit=g9-ben-1", text)
        self.assertIn("--property=NetworkNamespacePath=/run/netns/g9ben-2", text)
        self.assertIn("src/gameapi.py --config " + str(ROOT / "configs" / "ben-gen5-16.conf") + " --host 127.0.0.1 --port 8087", text)
        self.assertIn("scripts/gen9_match.py --source /w/capsule/recovery --pair '9p-32~ben' --deals 8 --first 0 --seed 91 --workers 1 --out /w/runs/w7/lane-1", text)
        self.assertIn("--deals 8 --first 8 --seed 91 --workers 1 --out /w/runs/w7/lane-2", text)
        self.assertIn("--setenv=BRIDGE_DDS_CACHE=/w/runs/w7/lane-1.dds.sqlite", text)
        self.assertIn("lane 2: (dry run) would wait for BEN in g9ben-2", text)
        self.assertIn("+ sudo systemctl stop g9-ben-2", text)
        self.assertIn("+ sudo ip netns delete g9ben-2", text)

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
