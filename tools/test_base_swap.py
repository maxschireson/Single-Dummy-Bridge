"""Tests for tools/base_swap.py on a synthetic repository shaped like feature/gen9. Run: python3 tools/test_base_swap.py"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("base_swap", HERE / "base_swap.py")
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)


class Repo:
    def __init__(self, path: Path):
        self.p = path
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@invalid", *args], cwd=self.p, capture_output=True, text=True)
        if r.returncode:
            raise AssertionError(f"git {args}: {r.stderr}")
        return r.stdout.strip()

    def commit(self, msg, **files):
        for name, text in files.items():
            f = self.p / name.replace("__", "/")
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def show(self, ref, path):
        return self.git("show", f"{ref}:{path}")


GEN8A = "def type_log_weights():\n    return 1\n\n\ndef meet():\n    pass\n"


class BaseSwapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.r = Repo(Path(self.tmp.name))
        r.commit("main", **{"gen8a.py": "def type_log_weights():\n    return 0\n\n\ndef meet():\n    pass\n", "gen8b.py": "B0\n", "other.py": "x\n"})
        self.main = r.git("rev-parse", "HEAD")
        r.git("checkout", "-q", "-b", "gen9")
        self.snap = r.commit("Gen 8 prototype snapshot", **{"gen8a.py": GEN8A, "gen8b.py": "B1 prototype\n", "gen8new.py": "N\n"})
        r.commit("Gen 9: player shell", **{"gen9.py": "import gen8a\n"})
        r.commit("Gen 9: hook in gen8a", **{"gen8a.py": GEN8A + "\n\ndef gen9_hook():\n    return 'hook'\n"})
        r.git("checkout", "-q", "-b", "side")
        r.commit("Gen 9 arena note", **{"docs__arena.md": "arena\n"})
        r.git("checkout", "-q", "gen9")
        r.git("merge", "-q", "--no-ff", "side", "-m", "Merge side: the arena note")
        r.commit("Gen 9: after the merge", **{"gen9.py": "import gen8a\nimport gen8b\n"})
        self.tip = r.git("rev-parse", "HEAD")
        r.git("checkout", "-q", "-b", "pr-x")
        r.commit("PR x: a reader", **{"reader.py": "r\n"})
        self.g = bs.Git(r.p)

    def tearDown(self):
        self.tmp.cleanup()

    def landed_base(self, gen8a=GEN8A):
        """main, then an unrelated commit, then Gen 8 as it landed: gen8a as the snapshot had it, gen8b different."""
        r = self.r
        r.git("checkout", "-q", "main")
        r.commit("unrelated main work", **{"other.py": "y\n"})
        return r.commit("Gen 8 on main", **{"gen8a.py": gen8a, "gen8b.py": "B2 as landed\n", "gen8new.py": "N\n"})

    def test_analysis_names_hooks_and_drift(self):
        base = self.landed_base()
        a = bs.analyse(self.g, self.snap, "gen9", base)
        self.assertEqual(a["hooks"], ["gen8a.py"])
        self.assertEqual(a["drift"], ["gen8b.py"])
        self.assertEqual(a["gone"], [])
        self.assertEqual((a["commits"], a["merges"]), (5, 1))
        self.assertEqual(a["hook_stats"]["gen8a.py"], "+4 -0")

    def test_apply_replays_merges_and_drops_the_snapshot(self):
        base = self.landed_base()
        a = bs.analyse(self.g, self.snap, "gen9", base)
        res = bs.rebase(self.g, a["new_base"], a["snapshot"], a["branch_sha"], "gen9-rebased")
        self.assertTrue(res["ok"], res)
        r = self.r
        subjects = r.git("log", "--format=%s", f"{base}..gen9-rebased").splitlines()
        self.assertNotIn("Gen 8 prototype snapshot", subjects)
        self.assertIn("Merge side: the arena note", subjects)
        self.assertEqual(len(r.git("rev-list", "--merges", f"{base}..gen9-rebased").splitlines()), 1)
        self.assertIn("gen9_hook", r.show("gen9-rebased", "gen8a.py"))
        self.assertEqual(r.show("gen9-rebased", "gen8b.py"), "B2 as landed")  # Gen 8 as landed wins where Gen 9 did not touch
        self.assertEqual(r.show("gen9-rebased", "docs/arena.md"), "arena")
        cmp = dict(bs.compare(self.g, a, res["sha"]))
        self.assertEqual(set(cmp.values()), {"same change"}, cmp)
        self.assertEqual(r.git("rev-parse", "gen9"), self.tip)  # the original branch is untouched
        text = bs.render(a, res, list(cmp.items()), [])
        self.assertIn("Every Gen 9 file change is the same patch as before", text)
        self.assertIn("`gen8b.py`", text)

    def test_conflict_stops_cleanly(self):
        base = self.landed_base(gen8a=GEN8A.replace("def meet():\n    pass\n", "def meet(opponent):\n    return opponent\n"))
        a = bs.analyse(self.g, self.snap, "gen9", base)
        self.assertEqual(a["drift"], ["gen8a.py", "gen8b.py"])
        res = bs.rebase(self.g, a["new_base"], a["snapshot"], a["branch_sha"], "gen9-rebased")
        self.assertFalse(res["ok"])
        self.assertEqual(res["conflicts"], ["gen8a.py"])
        r = subprocess.run(["git", "rev-parse", "--verify", "refs/heads/gen9-rebased"], cwd=self.r.p, capture_output=True)
        self.assertNotEqual(r.returncode, 0)  # nothing written
        self.assertIn("**drifted on the new base**", bs.render(a, res, None, []))

    def test_branch_cut_from_gen9_follows(self):
        base = self.landed_base()
        a = bs.analyse(self.g, self.snap, "gen9", base)
        res = bs.rebase(self.g, a["new_base"], a["snapshot"], a["branch_sha"], "gen9-rebased")
        mb = self.g.out("merge-base", "pr-x", a["branch_sha"])
        pr = bs.rebase(self.g, res["sha"], mb, self.g.sha("pr-x"), "pr-x-rebased")
        self.assertTrue(pr["ok"])
        self.assertEqual(self.r.git("rev-list", "--count", "gen9-rebased..pr-x-rebased"), "1")
        self.assertEqual(self.r.show("pr-x-rebased", "reader.py"), "r")


if __name__ == "__main__":
    unittest.main()
