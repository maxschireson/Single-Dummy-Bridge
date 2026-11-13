"""The Gen 9 cohort's plans and the collector's Gen 9 support (ops/prepare_gen7_alpha.py, ops/gen5_runtime.py)."""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ops import prepare_gen7_alpha as P  # noqa: E402

CAPSULE = Path(os.environ.get('BRIDGE_CAPSULE', '/nonexistent')) / 'manifest.json'   # a Gen 6 run's manifest with 6-32
ARENA = {'8s-32': '269fdf1854f474f4ec19429bba453ce810d68681ed55c8118897b6d9f25b5a6a',
         '71s-32': '7b0f58b4c40337fe021d8df495e343dcaf009beeb9d6e1052e31e7fc0f246c0f'}


class Plans(unittest.TestCase):
    def test_plans_load_and_declare_systems(self):
        P.load_plan(ROOT / 'configs/round9-cohort.json')         # opened on g9's go, 13 Nov 06:16 UTC
        P.load_plan(ROOT / 'configs/round9-cohort-ben.json')     # opened when BEN 64 answered on azure4, 07:04 UTC
        for name in ('round9-cohort.json', 'round9-cohort-ben.json'):
            path = ROOT / 'configs' / name
            plan = P.load_plan(path, require_ready=False)
            P.check_systems(plan)
            self.assertTrue(plan['exclude_training_families'])
            self.assertEqual(plan['gen7_bots']['9a-32']['engine'], 'gen9')
            self.assertEqual(plan['gen7_bots']['9a-32']['exploration'], 1.0)

    def test_control_is_the_gen9_bot_without_its_model(self):
        plan = P.load_plan(ROOT / 'configs/round9-cohort.json', require_ready=False)
        a, c = plan['gen7_bots']['9a-32'], plan['gen7_bots']['8p-32']
        self.assertEqual(a['gen7'], c['gen7'])
        self.assertEqual(a['policy'], c['policy'])
        self.assertNotIn('gen9', c)
        self.assertNotIn('exploration', c)

    @unittest.skipUnless(CAPSULE.exists(), 'set BRIDGE_CAPSULE to a run directory whose manifest has 6-32')
    def test_arena_bots_keep_their_identities(self):
        old = json.loads(CAPSULE.read_text())
        bots = P.make_bots(old, P.load_plan(ROOT / 'configs/round9-cohort.json', require_ready=False))
        for key, identity in ARENA.items():
            self.assertEqual(bots[key]['identity'], identity)
        self.assertEqual(bots['9a-32']['engine'], 'gen9')
        self.assertEqual(bots['9a-32']['exploration'], 1.0)
        self.assertEqual(bots['9a-32']['policy_role'], 'gen9-proto')


class Gen9Block(unittest.TestCase):
    def test_refusals(self):
        with self.assertRaises(ValueError):
            P.gen9_block('x', {'gen9': {'oracle': {'near': 0.2}}})
        with self.assertRaises(ValueError):
            P.gen9_block('x', {'gen9': {'surprise': 1}})
        with self.assertRaises(ValueError):
            P.gen9_block('x', {'gen9': {'models': {'a': {'kind': 'house', 'experience': {'boards': 3}}}}})
        with self.assertRaises((ImportError, AttributeError)):
            P.gen9_block('x', {'gen9': {'replay_reader': 'bridge_harness.cards.replay:nothing_here'}})

    def test_the_cohort_block_passes(self):
        plan = json.loads((ROOT / 'configs/round9-cohort.json').read_text())
        block = P.gen9_block('9a-32', plan['gen7_bots']['9a-32'])
        self.assertEqual(set(block['models']), {'6-32', '71s-32', '8s-32', '8p-32', '9a-32'})


class Runtime(unittest.TestCase):
    def test_the_runtime_knows_the_engine(self):
        src = (ROOT / 'ops/gen5_runtime.py').read_text()
        self.assertIn("spec.get('engine')=='gen9'", src)
        self.assertIn("'gen9')", (ROOT / 'ops/smoke_gen7.py').read_text())


if __name__ == '__main__':
    unittest.main()
