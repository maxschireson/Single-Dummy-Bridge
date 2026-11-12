from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bridge_harness.corpus import generate, save
from bridge_harness.gen6 import Gen6Config
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from dataclasses import asdict
from ops import prepare_gen6
from ops.prepare_gen6 import GEN6_FILES, load_plan, make_bots, prepare

ROOT = Path(__file__).resolve().parents[1]


def source_run(root):
    """A drained three-bot source run with stand-in artifact files."""
    (root / 'artifacts/v5').mkdir(parents=True)
    for d in ('episodes', 'receipts', 'failures', 'assets'):
        (root / d).mkdir()
    for n in ('STOP', 'WATCHDOG_STOP'):
        (root / n).write_text('drained')
    for name in ('belief.npz', 'policy.npz', 'bidder.keras'):
        (root / 'artifacts/v5' / name).write_bytes(name.encode())
    save(list(generate(6, 5)), root / 'corpus.jsonl')
    base = dict(samples=32, near_tie=.125, exploration=0., belief_kind='public', belief='artifacts/v5/belief.npz',
                policy='artifacts/v5/policy.npz', bidding='artifacts/v5/bidder.keras')
    base['artifact_sha256'] = {k: sha(root / base[k]) for k in ('belief', 'policy', 'bidding')}
    bots = {}
    for key, extra in (('3', {}), ('5R32', dict(layout_reduction=dict(large_pool=128, large_budget=32))),
                       ('5RZ32', dict(layout_reduction=dict(large_pool=128, large_budget=32), near_tie=0., policy_role='pimc-ties-only'))):
        spec = dict(base, id=key, **extra)
        spec['identity'] = digest(spec)
        bots[key] = spec
    m = dict(schema='gen5-arena-manifest-v1', generation=5, variant='5RZ', target=6, seed=7, roster=['5RZ32', '5R32', '3'], bots=bots,
             pair_weights={'5RZ32~5R32': 1}, pair_schedule=['5RZ32~5R32'], audit_references={'5RZ32': '3', '5R32': '3'}, common_bidder='5R32',
             corpus='corpus.jsonl', corpus_sha256=sha(root / 'corpus.jsonl'), source_sha256='older-code', runtime_sha256={},
             audit=dict(probability=.5, multiplier=3., max_depth=2, max_forks=64), ben_audit=dict(probability=0., multiplier=1., max_depth=0, max_forks=0),
             bidding_conditions=['common', 'native'], labels={k: k for k in bots}, order=['5RZ32', '5R32', '3'])
    m['identity'] = digest(m)
    atomic_json(root / 'manifest.json', m)
    return m


class Gen6LaunchTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)
        self.old = source_run(self.tmp / 'source')
        plan = json.loads((ROOT / 'configs/round6.json').read_text())
        self.files = {}
        for key in GEN6_FILES:                      # stand-in release files, so the test needs no model weights
            path = self.tmp / (key + '.bin')
            path.write_bytes(key.encode())
            self.files[key] = path
            plan['artifacts'][key]['sha256'] = sha(path)
        plan.update(launch_enabled=True, pending=[], lead_state_bidder_sha256=self.old['bots']['5RZ32']['artifact_sha256']['bidding'])
        self.plan = plan
        self.plan_path = self.tmp / 'plan.json'
        self.write()
        self.release = patch.object(prepare_gen6, 'release_file', side_effect=lambda entry: next(
            p for k, p in self.files.items() if plan['artifacts'][k]['file'] == entry['file']))
        self.release.start()

    def tearDown(self):
        self.release.stop()
        self.dir.cleanup()

    def write(self):
        self.plan_path.write_text(json.dumps(self.plan))

    def test_shipped_plan_is_closed_until_the_match_mix_is_set(self):
        with self.assertRaises(ValueError):
            load_plan()
        shipped = load_plan(require_ready=False)
        self.assertFalse(shipped['launch_enabled'])
        self.assertTrue(shipped['pending'])
        for entry in list(shipped['gen6_bots'].values()) + list(shipped['gen6_variants_for_ablation'].values()):
            Gen6Config(**entry['gen6'])
        for key, entry in shipped['artifacts'].items():
            manifest = json.loads((ROOT / entry['release'] / 'manifest.json').read_text())
            self.assertIn(entry['sha256'], json.dumps(manifest))
            self.assertTrue((ROOT / entry['release'] / entry['restore']).exists())

    def test_gen6_bot_is_its_base_plus_engine_nets_and_zero_margin(self):
        bots = make_bots(self.old, self.plan)
        for key, spec in self.old['bots'].items():
            self.assertEqual(bots[key], spec)
        six, base = deepcopy(bots['6-32']), deepcopy(self.old['bots']['5RZ32'])
        self.assertEqual(six['identity'], digest({k: v for k, v in six.items() if k != 'identity'}))
        self.assertEqual((six.pop('engine'), six.pop('gen6'), six.pop('lead_state_bidder')), ('gen6', asdict(Gen6Config()), base['bidding']))
        self.assertEqual({k: six.pop(k) for k in ('lead_belief', 'scorer')}, {k: GEN6_FILES[k] for k in ('lead_belief', 'scorer')})
        hashes = six.pop('artifact_sha256')
        self.assertEqual(hashes, dict(base.pop('artifact_sha256'), lead_state_bidder=self.plan['lead_state_bidder_sha256'],
                                      **{k: self.plan['artifacts'][k]['sha256'] for k in GEN6_FILES}))
        self.assertEqual((six['bidding'], six['near_tie'], six['policy_role'], six['samples']), (GEN6_FILES['bidding'], 0., 'pimc-ties-only', 32))
        for key in ('id', 'identity', 'bidding'):
            six.pop(key)
            base.pop(key)
        self.assertEqual(six, base)                 # same policy, belief, sample count and layout reduction as the base

    def test_switches_change_the_identity_and_bad_plans_are_refused(self):
        plain = make_bots(self.old, self.plan)['6-32']['identity']
        self.plan['gen6_bots']['6-32']['gen6'] = dict(list_from_trick=8)
        changed = make_bots(self.old, self.plan)['6-32']
        self.assertNotEqual(changed['identity'], plain)
        self.assertEqual(changed['gen6']['list_from_trick'], 8)
        for edit in (lambda p: p['gen6_bots']['6-32'].update(gen6=dict(early_source='bidder')),
                     lambda p: p['gen6_bots']['6-32'].update(base='missing'),
                     lambda p: p.update(lead_state_bidder_sha256='0' * 64),
                     lambda p: p['gen6_bots'].update({'5R32': dict(base='5RZ32', gen6={})})):
            plan = deepcopy(self.plan)
            plan['gen6_bots']['6-32']['gen6'] = {}
            edit(plan)
            with self.assertRaises((ValueError, TypeError)):
                Path(self.plan_path).write_text(json.dumps(plan))
                make_bots(self.old, load_plan(self.plan_path))

    def test_prepare_freezes_unplayed_deals_bots_and_artifacts(self):
        self.plan.update(roster=['6-32', '5RZ32', '5R32'], pair_weights={'6-32~5RZ32': 3, '5RZ32~5R32': 1}, audit_references={'6-32': '3'})
        self.write()
        run = self.tmp / 'run'
        m = prepare(run, self.tmp / 'source', self.plan_path)
        verify_generation(run, m)
        self.assertEqual((m['generation'], m['variant'], m['target'], m['common_bidder']), (6, '6', 6, '5RZ32'))
        self.assertEqual(m['pair_schedule'], ['6-32~5RZ32'] * 3 + ['5RZ32~5R32'])
        self.assertEqual(m['audit_references'], {'5RZ32': '3', '5R32': '3', '6-32': '3'})
        self.assertEqual(m['source_generation'], self.old['identity'])
        self.assertEqual(set(m['runtime_sha256']), {'ops/gen5_runtime.py', 'ops/prepare_gen6.py'})
        for key, target in GEN6_FILES.items():
            self.assertEqual(sha(run / target), self.plan['artifacts'][key]['sha256'])
        for key, spec in self.old['bots'].items():
            self.assertEqual(m['bots'][key], spec)
        with self.assertRaises(ValueError):
            prepare(run, self.tmp / 'source', self.plan_path)                   # never overwrites

    def test_prepare_refuses_a_live_source_or_an_unknown_pair(self):
        (self.tmp / 'source' / 'STOP').unlink()
        with self.assertRaises(ValueError):
            prepare(self.tmp / 'run', self.tmp / 'source', self.plan_path)
        (self.tmp / 'source' / 'STOP').write_text('drained')
        for mix in (dict(pair_weights={'6-32~4b': 1}), dict(audit_references={}), dict(common_bidder='9'), dict(roster=['6-32', 'x'])):
            self.plan.update(pair_weights={'6-32~5RZ32': 1}, audit_references={'6-32': '3'}, common_bidder='5RZ32', roster=['6-32', '5RZ32'])
            self.plan.update(mix)
            self.write()
            with self.assertRaises(ValueError):
                prepare(self.tmp / 'run', self.tmp / 'source', self.plan_path)
            self.assertFalse((self.tmp / 'run').exists())


if __name__ == '__main__':
    unittest.main()
