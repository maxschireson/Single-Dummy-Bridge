"""Gen 8 launch files: a plan that declares bidding systems, a bot that bids by the rule system, the system-aware
scorer as a cohort artifact, and a board whose two rooms seat different systems."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from bridge_harness import rule_bidder
from bridge_harness.corpus import generate
from bridge_harness.gen5_arena import run_board
from bridge_harness.gen7 import resolved
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from ops.gen5_runtime import validate
from ops.prepare_gen7_alpha import SYSTEM_SCORER, SYSTEM_SCORER_KEY, load_plan, make_bots, prepare
from test_gen5 import Toy
from test_gen7_launch import gen6_run

ROOT = Path(__file__).resolve().parents[1]
HOUSE, RULES = 'house-gen6', 'rules-precision'


def rule_entry(**settings):
    """A generator entry for the rule system with these settings, pinned to its identity."""
    full = asdict(rule_bidder.Settings(**settings))
    return dict(kind='python', factory='bridge_harness.rule_bidder:from_package', options=dict(settings=full),
                sha256=rule_bidder.RuleSystemBidder(full).sha256)


class Gen8PlanTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)
        self.old = gen6_run(self.tmp / 'source')
        self.scorer = self.old['bots']['6-32']['artifact_sha256']['scorer']
        release = self.tmp / 'release'
        release.mkdir()
        (release / 'policy.npz').write_bytes(b'policy')
        (release / 'manifest.json').write_text(json.dumps(dict(scorer_sha256=self.scorer)))
        self.systems_release = self.tmp / 'systems'
        self.systems_release.mkdir()
        (self.systems_release / 'system_scorer.npz').write_bytes(b'system scorer')
        (self.systems_release / 'manifest.json').write_text(json.dumps(dict(init_sha256=self.scorer)))
        plan = json.loads((ROOT / 'configs/round7-alpha.json').read_text())
        seven = plan['gen7_bots']['7a-32']
        eight = dict(base='6-32', label='Gen 8 test (32)', gen7=dict(seven['gen7'], play_weight=1.0, early_play_weight=1.0),
                     system_scorer=True, lead_systems=[HOUSE])
        plan['gen7_bots'].update({'8s-32': eight, '8c-32': dict(deepcopy(eight), label='Gen 8 test, rule system (32)', bidder=rule_entry())})
        plan.update(launch_enabled=True, pending=[], roster=['8s-32', '8c-32', '7a-32', '6-32'],
                    pair_weights={'8s-32~7a-32': 1, '8c-32~8s-32': 1}, audit_references={'8s-32': '3', '8c-32': '3', '7a-32': '3'},
                    systems={'8s-32': HOUSE, '8c-32': RULES, '7a-32': HOUSE, '6-32': HOUSE})
        plan['artifacts'] = dict(
            gen7_policy=dict(release=str(release), file='policy.npz', restore='restore.py', sha256=sha(release / 'policy.npz')),
            system_scorer=dict(release=str(self.systems_release), file='system_scorer.npz', restore='restore.py',
                               sha256=sha(self.systems_release / 'system_scorer.npz')))
        self.plan, self.plan_path = plan, self.tmp / 'plan.json'
        self.write()

    def tearDown(self):
        self.dir.cleanup()

    def write(self, plan=None):
        self.plan_path.write_text(json.dumps(plan or self.plan))

    def test_a_plan_without_systems_builds_the_bots_it_always_built(self):
        seven_only = deepcopy(self.plan)
        for key in ('8s-32', '8c-32'):
            seven_only['gen7_bots'].pop(key)
        seven_only['artifacts'].pop(SYSTEM_SCORER_KEY)
        seven_only.pop('systems')
        seven_only.update(roster=['7a-32', '6-32'], pair_weights={'7a-32~6-32': 1}, audit_references={'7a-32': '3'})
        self.write(seven_only)
        load_plan(self.plan_path)
        before, after = make_bots(self.old, seven_only), make_bots(self.old, self.plan)
        for key, spec in before.items():                # a Gen 8 plan changes no other bot: same spec, same identity
            self.assertEqual(after[key], spec)
            self.assertFalse({'bidder', 'system_scorer', 'lead_systems'} & set(spec))

    def test_gen8_bots_carry_their_system_settings_in_their_identity(self):
        load_plan(self.plan_path)
        bots = make_bots(self.old, self.plan)
        house, rules = bots['8s-32'], bots['8c-32']
        self.assertEqual(house['system_scorer'], SYSTEM_SCORER)
        self.assertEqual(house['artifact_sha256'][SYSTEM_SCORER_KEY], self.plan['artifacts'][SYSTEM_SCORER_KEY]['sha256'])
        self.assertEqual(house['lead_systems'], [HOUSE])
        self.assertNotIn('bidder', house)
        self.assertEqual(rules['bidder'], self.plan['gen7_bots']['8c-32']['bidder'])
        self.assertEqual(rules['bidding'], house['bidding'])        # its net stays, for the lead net's inputs
        self.assertEqual(house['gen7'], resolved(self.plan['gen7_bots']['8s-32']['gen7']))
        self.assertEqual(house['gen7']['early_play_weight'], 1.0)
        seen = {house['identity'], rules['identity']}
        self.assertEqual(len(seen), 2)
        for edit in (lambda p: p['gen7_bots']['8c-32'].update(bidder=rule_entry(game=24)),
                     lambda p: p['gen7_bots']['8c-32'].update(lead_systems=[HOUSE, RULES]),
                     lambda p: p['artifacts'][SYSTEM_SCORER_KEY].update(sha256='0' * 64)):
            plan = deepcopy(self.plan)
            edit(plan)
            seen.add(make_bots(self.old, plan)['8c-32']['identity'])
        self.assertEqual(len(seen), 5)

    def test_bad_system_plans_are_refused(self):
        for edit in (lambda p: p.pop('systems'),
                     lambda p: p['systems'].pop('6-32'),                                    # the common bidder declares too
                     lambda p: p['systems'].pop('8c-32'),
                     lambda p: p['systems'].update({'8s-32': ''}),
                     lambda p: p['gen7_bots']['8c-32']['bidder'].pop('sha256'),
                     lambda p: p['gen7_bots']['8c-32']['bidder'].update(kind='ben-lstm-keras'),
                     lambda p: p['gen7_bots']['8s-32'].update(system_scorer='models/x.npz'),
                     lambda p: p['gen7_bots']['8s-32'].update(lead_systems=HOUSE),
                     lambda p: p['artifacts'].pop(SYSTEM_SCORER_KEY),                        # asked for, not supplied
                     lambda p: p['artifacts'][SYSTEM_SCORER_KEY].pop('restore'),
                     lambda p: [b.pop('system_scorer') for b in p['gen7_bots'].values() if 'system_scorer' in b]):      # supplied, not asked for
            plan = deepcopy(self.plan)
            edit(plan)
            self.write(plan)
            with self.assertRaises(ValueError):
                load_plan(self.plan_path)

    def test_prepare_freezes_the_systems_the_scorer_and_the_rule_bidder(self):
        run = self.tmp / 'run'
        m = prepare(run, self.tmp / 'source', self.plan_path)
        verify_generation(run, m)
        self.assertEqual(m['systems'], self.plan['systems'])
        self.assertEqual(sha(run / SYSTEM_SCORER), self.plan['artifacts'][SYSTEM_SCORER_KEY]['sha256'])
        self.assertEqual(m['gen8'], dict(rule_bidders={'8c-32': self.plan['gen7_bots']['8c-32']['bidder']['sha256']},
                                         system_scorer=dict(release=str(self.systems_release), sha256=sha(run / SYSTEM_SCORER))))
        self.assertEqual(m['bots']['8c-32']['bidder'], self.plan['gen7_bots']['8c-32']['bidder'])
        self.assertEqual(m['gen7_alpha']['bots'], ['7a-32', '8c-32', '8s-32'])
        for key, spec in self.old['bots'].items():
            self.assertEqual(m['bots'][key], spec)

    def test_prepare_refuses_a_bidder_that_is_not_the_pinned_one_or_a_scorer_built_on_another(self):
        source = self.tmp / 'source'
        wrong = deepcopy(self.plan)
        wrong['gen7_bots']['8c-32']['bidder']['sha256'] = 'f' * 64
        self.write(wrong)
        with self.assertRaises(ValueError):
            prepare(self.tmp / 'run', source, self.plan_path)
        self.assertFalse((self.tmp / 'run').exists())
        self.write()
        for manifest in (dict(init_sha256='0' * 64), {}):
            (self.systems_release / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                prepare(self.tmp / 'run', source, self.plan_path)
            self.assertFalse((self.tmp / 'run').exists())
        (self.systems_release / 'manifest.json').write_text(json.dumps(dict(init_sha256=self.scorer)))
        (self.systems_release / 'system_scorer.npz').write_bytes(b'another file')
        with self.assertRaises(ValueError):
            prepare(self.tmp / 'run', source, self.plan_path)


class PassingNet:
    """A bidding net that always wants to pass (the interface gen5_arena.auction expects of a net)."""

    def predict(self, xs, lengths):
        raw = np.full((1, 40), -5., np.float32)
        raw[0, 2] = 5.
        return raw, None


class Seated(Toy):
    """A toy player that remembers the systems of every table it was seated at."""
    log = []

    def seat_table(self, systems):
        Seated.log.append((self.id, systems))


class MixedTableTests(unittest.TestCase):
    def manifest(self, **extra):
        quiet = dict(probability=0, multiplier=1, max_depth=0, max_forks=0)
        m = dict(identity='test8', roster=['8c-32', '8s-32'], target=64, seed=11,
                 bots={k: dict(id=k, identity=k, artifact_sha256={}) for k in ('8c-32', '8s-32', '6-32', '3')},
                 pair_schedule=['8c-32~8s-32'], audit_references={'8c-32': '3'}, common_bidder='6-32', audit=quiet, ben_audit=quiet)
        m.update(extra)
        return m

    def play(self, m, index):
        Seated.log = []
        net = PassingNet()
        bidders = {'8c-32': rule_bidder.RuleSystemBidder(), '8s-32': net, '6-32': net, '3': net}
        board = next(generate(1, 500 + index))
        return run_board('.', m, board.to_dict(), index, bidders, player_factory=Seated)

    def test_each_room_is_bid_by_its_own_systems_and_the_players_are_told(self):
        m = self.manifest(systems={'8c-32': RULES, '8s-32': HOUSE, '6-32': HOUSE})
        opened = 0
        for index in range(12):
            r = self.play(m, index)
            validate(r, m, index)                       # the runtime's own check of the record
            self.assertEqual(r['board']['auction_source'], f'systems:{HOUSE}|{HOUSE}')         # the common room: the house net bids every seat
            self.assertEqual(r['bidding']['native/0']['bidders'], ['8c-32', '8s-32'] * 2)
            self.assertEqual(r['bidding']['native/1']['bidders'], ['8s-32', '8c-32'] * 2)
            sources = {key: table['board']['auction_source'] for key, table in r['unique_tables'].items()}
            for room, systems in ((0, f'systems:{RULES}|{HOUSE}'), (1, f'systems:{HOUSE}|{RULES}')):
                table = r['bidding'][f'native/{room}']['table']
                if r['bidding'][f'native/{room}']['calls'] != ['PASS'] * 4:
                    opened += 1
                    self.assertEqual(sources[table], systems)
                    self.assertIn(('8c-32', tuple(systems[8:].split('|'))), Seated.log)
                    self.assertIn(('8s-32', tuple(systems[8:].split('|'))), Seated.log)
                    # only the rule system opens: every non-pass call in the room is from the seats of 8c-32
                    seats = {d['seat'] % 2 for d in r['bidding'][f'native/{room}']['decisions'] if d['call'] != 'PASS'}
                    self.assertEqual(seats, {room})
        self.assertGreater(opened, 8)

    def test_a_cohort_that_declares_nothing_is_run_as_before(self):
        m = self.manifest()
        r = self.play(m, 0)
        self.assertEqual(r['board']['auction_source'], 'gen5-neural-only')
        for table in r['unique_tables'].values():
            self.assertEqual(table['board']['auction_source'], 'gen5-neural-only')
        self.assertTrue(all(systems is None for _, systems in Seated.log))


if __name__ == '__main__':
    unittest.main()
