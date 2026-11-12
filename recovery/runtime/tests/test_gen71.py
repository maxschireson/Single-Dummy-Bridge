"""Gen 7.1: the Gen 7 bot with policy net v4.1. One cohort holds bots with different policy releases, so that
7.1 can play 7.0; the plans Max asked for on 12 November 2026; and that 7s-32 keeps the identity it has in phase 1."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from bridge_harness.corpus import generate
from bridge_harness.gen5_arena import run_board
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from ops.gen5_runtime import validate
from ops.prepare_gen7_alpha import GEN7_POLICY, load_plan, make_bots, policy_path, prepare
from test_gen5 import Toy
from test_gen7_launch import gen6_run

ROOT = Path(__file__).resolve().parents[1]
COMPARE, SELFPLAY, BEN = (ROOT / 'configs' / f'round71-{name}.json' for name in ('compare', 'selfplay', 'ben'))
PHASE1 = ROOT / 'configs/round7-candidate-phase1-nonben.json'
V41 = 'artifacts/gen7/gen7_policy_v41.npz'


def stand_in(tmp, name, source, **changes):
    """A plan file in `tmp`: a shipped plan with each policy release replaced by a stand-in that names the source run's scorer."""
    old = json.loads((tmp / 'source' / 'manifest.json').read_text())
    plan = json.loads(Path(source).read_text())
    for key in plan['artifacts']:
        release = tmp / ('release-' + key)
        if not release.exists():
            release.mkdir()
            (release / 'policy.npz').write_bytes(key.encode())
            (release / 'manifest.json').write_text(json.dumps(dict(scorer_sha256=old['bots']['6-32']['artifact_sha256']['scorer'])))
        plan['artifacts'][key] = dict(release=str(release), file='policy.npz', restore='restore.py', sha256=sha(release / 'policy.npz'))
    plan.update(changes)
    (tmp / f'{name}.json').write_text(json.dumps(plan))
    return tmp / f'{name}.json'


class Gen71Tests(unittest.TestCase):
    def test_the_shipped_plans_are_gen7_with_the_net_changed(self):
        compare, ben, base = load_plan(COMPARE), load_plan(BEN), load_plan(PHASE1)
        with self.assertRaises(ValueError):
            load_plan(SELFPLAY)                                         # closed until 7.1 has established its lead
        later = load_plan(SELFPLAY, require_ready=False)
        self.assertTrue(later['pending'] and not later['launch_enabled'])
        self.assertEqual(compare['pair_weights'], {'71s-32~6-32': 1, '71s-32~7s-32': 2})
        self.assertEqual(later['pair_weights'], {'71s-32~6-32': 1, '71s-32~71s-32': 2})
        self.assertEqual(ben['pair_weights'], {'71s-32~ben64': 1, '71s-32~ben': 1})
        self.assertEqual(compare['gen7_bots']['7s-32'], base['gen7_bots']['7s-32'])      # the phase 1 bot, untouched
        self.assertEqual(compare['artifacts']['gen7_policy'], base['artifacts']['gen7_policy'])
        for plan in (compare, later, ben):
            new = plan['gen7_bots']['71s-32']
            self.assertEqual(new['gen7'], base['gen7_bots']['7s-32']['gen7'])              # every setting as in 7.0
            self.assertEqual((new['base'], new['policy'], new['label']), ('6-32', 'gen7_policy_v41', 'Gen 7.1 standard (32)'))
            entry = plan['artifacts']['gen7_policy_v41']
            manifest = json.loads((ROOT / entry['release'] / 'manifest.json').read_text())
            self.assertEqual(manifest['files'][0]['sha256'], entry['sha256'])
            old = json.loads((ROOT / base['artifacts']['gen7_policy']['release'] / 'manifest.json').read_text())
            self.assertEqual(manifest['scorer_sha256'], old['scorer_sha256'])           # v4.1 reads the same hand-fit scorer
            self.assertIn('05:42 UTC', plan['notes'][0])
            self.assertEqual({m for pair in plan['pair_weights'] for m in pair.split('~')}, set(plan['roster']))

    def test_a_plan_names_exactly_the_policy_releases_its_bots_use(self):
        plan = json.loads(COMPARE.read_text())
        for edit in (lambda p: p['artifacts'].pop('gen7_policy_v41'),                    # a bot names a release the plan lacks
                     lambda p: p['gen7_bots'].pop('7s-32'),                              # a release no bot uses
                     lambda p: p['gen7_bots']['71s-32'].update(policy='v41'),             # not a policy artifact name
                     lambda p: p['artifacts'].update(gen7_policy_v41=dict(release='x', file='y', restore='z')),
                     lambda p: p['artifacts'].update(other=p['artifacts']['gen7_policy'])):
            bad = json.loads(json.dumps(plan))
            edit(bad)
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / 'plan.json').write_text(json.dumps(bad))
                with self.assertRaises((ValueError, KeyError)):
                    load_plan(Path(tmp) / 'plan.json')
        self.assertEqual((policy_path('gen7_policy'), policy_path('gen7_policy_v41')), (GEN7_POLICY, V41))

    def test_one_cohort_holds_both_nets_and_7s_32_keeps_its_phase_1_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gen6_run(tmp / 'source')
            # the stand-in source run has no Gen 5 or Gen 1 bot, so phase 1 is prepared with its Gen 6 pair only
            phase1 = prepare(tmp / 'phase1', tmp / 'source', stand_in(tmp, 'phase1', PHASE1, roster=['7s-32', '6-32'], pair_weights={'7s-32~6-32': 1}))
            m = prepare(tmp / 'compare', tmp / 'source', stand_in(tmp, 'compare', COMPARE))
            verify_generation(tmp / 'compare', m)
            old, new = m['bots']['7s-32'], dict(m['bots']['71s-32'])
            self.assertEqual(old, phase1['bots']['7s-32'])                               # same spec, same identity
            self.assertEqual((old['gen7_policy'], new['gen7_policy']), (GEN7_POLICY, V41))
            self.assertEqual(sha(tmp / 'compare' / GEN7_POLICY), old['artifact_sha256']['gen7_policy'])
            self.assertEqual(sha(tmp / 'compare' / V41), new['artifact_sha256']['gen7_policy'])
            self.assertNotEqual(sha(tmp / 'compare' / GEN7_POLICY), sha(tmp / 'compare' / V41))
            differ = {k for k in old if old[k] != new.get(k)}
            self.assertEqual(differ, {'id', 'identity', 'gen7_policy', 'artifact_sha256'})   # the net and nothing else
            self.assertEqual({k for k in old['artifact_sha256'] if old['artifact_sha256'][k] != new['artifact_sha256'][k]}, {'gen7_policy'})
            self.assertEqual(m['pair_schedule'], ['71s-32~6-32', '71s-32~7s-32', '71s-32~7s-32'])
            self.assertEqual(m['labels']['71s-32'], 'Gen 7.1 standard (32)')
            block = m['gen7_alpha']
            self.assertEqual(block['bots'], ['71s-32', '7s-32'])
            self.assertEqual(block['policy_sha256'], old['artifact_sha256']['gen7_policy'])
            self.assertEqual({k: v['artifact'] for k, v in block['policies'].items()}, {'71s-32': 'gen7_policy_v41', '7s-32': 'gen7_policy'})
            self.assertNotIn('policies', phase1['gen7_alpha'])                            # a one-policy cohort's manifest is as before
            # a Gen 7.1 cohort without 7.0 carries only the new release
            only = prepare(tmp / 'ben', tmp / 'source', stand_in(tmp, 'ben', BEN, roster=['71s-32', '6-32'], pair_weights={'71s-32~6-32': 1}))
            self.assertEqual(only['bots']['71s-32'], m['bots']['71s-32'])
            self.assertFalse((tmp / 'ben' / GEN7_POLICY).exists())
            self.assertNotIn('policy_sha256', only['gen7_alpha'])

    def test_a_drained_gen7_cohort_hands_its_unplayed_deals_to_the_gen71_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gen6_run(tmp / 'source')
            first = prepare(tmp / 'first', tmp / 'source', stand_in(tmp, 'phase1', PHASE1, roster=['7s-32', '6-32'], pair_weights={'7s-32~6-32': 1}))
            for name in ('STOP', 'WATCHDOG_STOP'):
                (tmp / 'first' / name).write_text('drained')
            m = prepare(tmp / 'next', tmp / 'first', stand_in(tmp, 'compare', COMPARE))
            verify_generation(tmp / 'next', m)
            self.assertEqual(m['bots']['7s-32'], first['bots']['7s-32'])
            self.assertEqual((m['target'], m['source_generation']), (first['target'], first['identity']))
            self.assertTrue((tmp / 'next' / V41).exists() and (tmp / 'next' / GEN7_POLICY).exists())
            lanes = prepare(tmp / 'lane', tmp / 'first', stand_in(tmp, 'ben', BEN, roster=['71s-32', '6-32'], pair_weights={'71s-32~6-32': 1}))
            self.assertEqual(lanes['bots']['7s-32'], first['bots']['7s-32'])            # the source's bots stay, 7s-32 among them
            verify_generation(tmp / 'lane', lanes)

    def test_a_board_of_71_against_70_is_two_tables_scored_for_71(self):
        quiet = dict(probability=0, multiplier=1, max_depth=0, max_forks=0)
        m = dict(identity='test71', generation=6, variant='6', roster=['71s-32', '7s-32', '6-32'], target=1, seed=11,
                 bots={k: dict(id=k, identity=k, artifact_sha256={}) for k in ('71s-32', '7s-32', '6-32', '3')},
                 pair_weights={'71s-32~6-32': 1, '71s-32~7s-32': 2}, pair_schedule=['71s-32~7s-32'],
                 audit_references={'71s-32': '3', '7s-32': '3'}, common_bidder='6-32', audit=quiet, ben_audit=quiet, created_epoch=time.time())
        board = next(generate(1, 341))
        with patch('bridge_harness.gen5_arena.auction', lambda b, actors: (b, [])):
            r = run_board('.', m, board.to_dict(), 0, {k: object() for k in m['bots']}, player_factory=Toy)
        validate(r, m, 0)
        self.assertEqual((r['pair'], r['candidate'], r['opponent']), ('71s-32~7s-32', '71s-32', '7s-32'))
        self.assertEqual(set(r['regimes']), {'common', 'native'})
        self.assertIsInstance(r['regimes']['common']['imps'], int)
        self.assertEqual(r['unique_tables'][r['regimes']['common']['tables'][0]]['assignments'], ['candidate', 'opponent'] * 2)


if __name__ == '__main__':
    unittest.main()
