"""Gen7 alpha launch files: the plan, cohort preparation, the runtime's player factory and the preflight's checks."""
from copy import deepcopy
from dataclasses import fields
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bridge_harness.corpus import generate
from bridge_harness.gen6 import Gen6Player
from bridge_harness.gen7 import USE_KEYS, Gen7Config, Gen7Player, resolved
from bridge_harness.gen7_tree import TreeConfig
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.players import GreedyPlayer
from bridge_harness.runner import play_table
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from ops import gen5_runtime, prepare_gen6
from ops.prepare_gen6 import GEN6_FILES
from ops.prepare_gen7_alpha import CARRIED, GEN7_POLICY, RUNTIME, load_plan, make_bots, parse_shard, prepare
from ops.smoke_gen7 import check_decision
from test_gen6 import FakeBelief, FakeState
from test_gen6_launch import source_run
from test_gen7 import Fixture

ROOT = Path(__file__).resolve().parents[1]


def gen6_run(root):
    """A drained Gen6 run: test_gen6_launch's three-bot run plus the shipped plan's Gen6 bots, with stand-in files."""
    old = source_run(root)
    plan = json.loads((ROOT / 'configs/round6.json').read_text())
    for key, target in GEN6_FILES.items():
        (root / target).parent.mkdir(parents=True, exist_ok=True)
        (root / target).write_bytes(key.encode())
        plan['artifacts'][key]['sha256'] = sha(root / target)
    plan['lead_state_bidder_sha256'] = old['bots']['5RZ32']['artifact_sha256']['bidding']
    m = dict(old, bots=prepare_gen6.make_bots(old, plan), generation=6, variant='6', independent_room_seeds=True,
             gap_fork=dict(per_band=2, bands=[.125, .5], max_cpu_share=1.5), allocation_trigger=dict(state='watching'))
    m.pop('identity')
    m['identity'] = digest(m)
    atomic_json(root / 'manifest.json', m)
    return m


class Gen7LaunchTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)
        self.old = gen6_run(self.tmp / 'source')
        release = self.tmp / 'release'
        release.mkdir()
        (release / 'policy.npz').write_bytes(b'policy')
        self.scorer = self.old['bots']['6-32']['artifact_sha256']['scorer']
        (release / 'manifest.json').write_text(json.dumps(dict(scorer_sha256=self.scorer)))
        plan = json.loads((ROOT / 'configs/round7-alpha.json').read_text())
        plan.update(launch_enabled=True, pending=[])
        plan['artifacts']['gen7_policy'] = dict(release=str(release), file='policy.npz', restore='restore.py', sha256=sha(release / 'policy.npz'))
        self.plan, self.plan_path, self.release = plan, self.tmp / 'plan.json', release
        self.write()

    def tearDown(self):
        self.dir.cleanup()

    def write(self):
        self.plan_path.write_text(json.dumps(self.plan))

    # ---- the plan ------------------------------------------------------------------------
    def test_shipped_plan_is_closed_and_spells_out_every_setting(self):
        with self.assertRaises(ValueError):
            load_plan()
        shipped = load_plan(require_ready=False)
        self.assertFalse(shipped['launch_enabled'])
        self.assertTrue(shipped['pending'])
        entry = shipped['artifacts']['gen7_policy']
        manifest = json.loads((ROOT / entry['release'] / 'manifest.json').read_text())
        self.assertIn(entry['sha256'], json.dumps(manifest))
        self.assertTrue((ROOT / entry['release'] / entry['restore']).exists())
        for bot in shipped['gen7_bots'].values():
            block = bot['gen7']
            self.assertEqual(resolved(block), block)        # nothing is left to a default in code
            self.assertEqual(set(block) - {'tree'}, {f.name for f in fields(Gen7Config) if not f.name.startswith('early_') and f.name != 'opponent_play_weight'})
            for stage in block['tree']:
                self.assertEqual(set(stage), set(USE_KEYS) | {f.name for f in fields(TreeConfig)})

    def test_phase_1_plans_are_open_phase_2_is_closed_and_every_setting_is_spelled_out(self):
        mix = json.loads((ROOT / 'configs' / 'gen7-candidate-mix.json').read_text())
        self.assertEqual(mix['status'], 'phase1_authorized')
        plans = {}
        for phase, total, is_open in (('phase1', 5, True), ('phase1_nonben', 3, True), ('phase1_ben', 2, True), ('phase2', 20, False)):
            path = ROOT / mix['plans'][phase]
            if is_open:
                plan = load_plan(path)                           # ready: preparation accepts it
                self.assertTrue(plan['launch_enabled'])
                self.assertEqual(plan['pending'], [])
                self.assertTrue(plan['model_note'] and plan['interpretation'])
            else:
                with self.assertRaises(ValueError):
                    load_plan(path)
                plan = load_plan(path, require_ready=False)
                self.assertFalse(plan['launch_enabled'])
                self.assertTrue(plan['pending'])
            plans[phase] = plan
            self.assertEqual(sum(plan['pair_weights'].values()), total)
            self.assertEqual({m for pair in plan['pair_weights'] for m in pair.split('~')}, set(plan['roster']))
            entry = plan['artifacts']['gen7_policy']
            manifest = json.loads((ROOT / entry['release'] / 'manifest.json').read_text())
            self.assertIn(entry['sha256'], json.dumps(manifest))
            self.assertTrue((ROOT / entry['release'] / entry['restore']).exists())
            for key, bot in plan['gen7_bots'].items():
                block = bot['gen7']
                self.assertEqual(resolved(block), block)        # nothing is left to a default in code
                self.assertEqual(set(block) - {'tree'}, {f.name for f in fields(Gen7Config) if not f.name.startswith('early_') and f.name != 'opponent_play_weight'})
                self.assertEqual('tree' in block, key == '7s-32')   # fast has no tree; standard has one
                for stage in block.get('tree', []):
                    self.assertEqual(set(stage), set(USE_KEYS) | {f.name for f in fields(TreeConfig)})
                    # what Max set on 12 November: margin 0.25, trust 0.3, the stake rule at 0.5 IMPs, 3 tricks
                    self.assertEqual((stage['root_margin'], stage['trust'], stage['path'], stage['tricks']), (.25, .3, .5, 3))
        self.assertEqual(plans['phase1']['pair_weights'], mix['phase1']['pair_weights'])
        self.assertEqual(plans['phase2']['pair_weights'], mix['phase2']['pair_weights'])
        # the two halves are the five pairs of phase 1, split by whether the machine needs a BEN server
        halves = dict(plans['phase1_nonben']['pair_weights'], **plans['phase1_ben']['pair_weights'])
        self.assertEqual(halves, plans['phase1']['pair_weights'])
        self.assertFalse(set(plans['phase1_nonben']['pair_weights']) & set(plans['phase1_ben']['pair_weights']))
        self.assertFalse(any('ben' in pair for pair in plans['phase1_nonben']['pair_weights']))
        self.assertTrue(all('ben' in pair for pair in plans['phase1_ben']['pair_weights']))
        for phase in ('phase1_nonben', 'phase1_ben'):
            for key in ('campaign', 'gen7_bots', 'artifacts', 'common_bidder', 'audit_references', 'model_note', 'interpretation'):
                self.assertEqual(plans[phase][key], plans['phase1'][key], (phase, key))
        self.assertEqual(plans['phase2']['gen7_bots']['7s-32'], plans['phase1']['gen7_bots']['7s-32'])     # one standard bot in both phases

    def test_bad_plans_are_refused(self):
        for edit in (lambda p: p['gen7_bots']['7a-32']['gen7']['tree'][0].update(depth=3),
                     lambda p: p['gen7_bots']['7a-32']['gen7'].update(tie_break='coin'),
                     lambda p: p['gen7_bots']['7a-32'].update(gen6=dict(early_source='bidder')),
                     lambda p: p['gen7_bots']['7a-32'].update(samples=0),
                     lambda p: p.update(gen7_bots={}),
                     lambda p: p['artifacts'].update(extra=dict(release='x', file='y', restore='z', sha256='0')),
                     lambda p: p['artifacts']['gen7_policy'].pop('sha256'),
                     lambda p: p.update(roster=['7a-32']),
                     lambda p: p.update(pair_weights={'7a-32~6-32': 0}),
                     lambda p: p.update(pending=['the model'])):
            plan = deepcopy(self.plan)
            edit(plan)
            self.plan_path.write_text(json.dumps(plan))
            with self.assertRaises((ValueError, TypeError)):
                load_plan(self.plan_path)

    # ---- the bots ------------------------------------------------------------------------
    def test_gen7_bot_is_its_gen6_base_plus_engine_policy_and_settings(self):
        bots = make_bots(self.old, self.plan)
        for key, spec in self.old['bots'].items():
            self.assertEqual(bots[key], spec)
        seven, base = deepcopy(bots['7a-32']), deepcopy(self.old['bots']['6-32'])
        self.assertEqual(seven['identity'], digest({k: v for k, v in seven.items() if k != 'identity'}))
        self.assertEqual((seven.pop('engine'), seven.pop('gen7_policy'), seven.pop('policy_role')), ('gen7', GEN7_POLICY, 'gen7-alpha'))
        self.assertEqual(seven.pop('gen7'), resolved(self.plan['gen7_bots']['7a-32']['gen7']))
        self.assertEqual(seven.pop('artifact_sha256'), dict(base.pop('artifact_sha256'), gen7_policy=self.plan['artifacts']['gen7_policy']['sha256']))
        for key in ('id', 'identity'):
            seven.pop(key)
            base.pop(key)
        base.pop('engine')
        base.pop('policy_role')
        self.assertEqual(seven, base)       # same bidder, lead net, scorer, policy, sample count and Gen6 layout settings

    def test_every_setting_is_part_of_the_bots_identity(self):
        plain = make_bots(self.old, self.plan)['7a-32']
        seen = {plain['identity']}
        for edit in (lambda b: b['gen7']['tree'][0].update(tricks=3), lambda b: b['gen7']['tree'][0].update(breadth=2),
                     lambda b: b['gen7']['tree'][0].update(layouts=16), lambda b: b['gen7']['tree'][0].update(from_trick=5),
                     lambda b: b['gen7']['tree'][0].update(root_margin=.25), lambda b: b['gen7']['tree'][0].update(trust=.5),
                     lambda b: b['gen7']['tree'][0].update(reply='search'), lambda b: b['gen7'].update(play_weight=0.),
                     lambda b: b['gen7'].pop('tree'), lambda b: b.update(gen6=dict(list_from_trick=8)), lambda b: b.update(samples=64),
                     lambda b: b['gen7'].update(tree=[dict(b['gen7']['tree'][0], to_trick=5), dict(b['gen7']['tree'][0], from_trick=6, to_trick=13, tricks=3)])):
            plan = deepcopy(self.plan)
            edit(plan['gen7_bots']['7a-32'])
            seen.add(make_bots(self.old, plan)['7a-32']['identity'])
        self.assertEqual(len(seen), 13)
        plan = deepcopy(self.plan)
        plan['artifacts']['gen7_policy']['sha256'] = '0' * 64       # another model is another bot
        self.assertNotIn(make_bots(self.old, plan)['7a-32']['identity'], seen)
        for edit in (lambda p: p['gen7_bots']['7a-32'].update(base='missing'), lambda p: p['gen7_bots']['7a-32'].update(base='5RZ32'),
                     lambda p: p['gen7_bots'].update({'6-32': dict(base='6-32', gen7={})})):
            plan = deepcopy(self.plan)
            edit(plan)
            with self.assertRaises(ValueError):
                make_bots(self.old, plan)

    # ---- the cohort ----------------------------------------------------------------------
    def test_prepare_freezes_unplayed_deals_bots_policy_and_carried_settings(self):
        self.plan.update(roster=['7a-32', '6-32', '5RZ32'], pair_weights={'7a-32~6-32': 1, '6-32~5RZ32': 3}, audit_references={'7a-32': '3', '6-32': '3'})
        self.write()
        run = self.tmp / 'run'
        m = prepare(run, self.tmp / 'source', self.plan_path)
        verify_generation(run, m)
        self.assertEqual((m['generation'], m['variant'], m['target'], m['common_bidder'], m['seed']), (6, '6', 6, '6-32', self.old['seed']))
        self.assertEqual(m['pair_schedule'], ['7a-32~6-32'] + ['6-32~5RZ32'] * 3)
        self.assertEqual(m['audit_references'], dict(self.old['audit_references'], **{'7a-32': '3', '6-32': '3'}))
        self.assertEqual(m['source_generation'], self.old['identity'])
        self.assertEqual(set(m['runtime_sha256']), set(RUNTIME))
        self.assertEqual(sha(run / GEN7_POLICY), self.plan['artifacts']['gen7_policy']['sha256'])
        self.assertEqual(m['gen7_alpha'], dict(bots=['7a-32'], policy_release=str(self.release), policy_sha256=sha(run / GEN7_POLICY)))
        for key in CARRIED:
            self.assertEqual(m.get(key), self.old.get(key), key)
        self.assertEqual((m['gap_fork'], m['independent_room_seeds'], m['audit']), (self.old['gap_fork'], True, self.old['audit']))
        self.assertNotIn('allocation_trigger', m)           # a producer's own state is not carried
        for key, spec in self.old['bots'].items():
            self.assertEqual(m['bots'][key], spec)
        self.assertEqual(m['labels']['7a-32'], 'Gen 7 alpha (32)')
        with self.assertRaises(ValueError):
            prepare(run, self.tmp / 'source', self.plan_path)                   # never overwrites

    def test_pruned_actor_restoration_requires_exact_direct_ancestor(self):
        from ops.prepare_gen7_alpha import inherited_actors
        ancestor = self.tmp / 'source'
        retained = deepcopy(self.old)
        retained['bots'] = {k: v for k, v in retained['bots'].items() if k != '5RZ32'}
        retained['source_generation'] = self.old['identity']
        restored = inherited_actors(ancestor, retained, ancestor)
        self.assertEqual(restored['bots']['5RZ32'], self.old['bots']['5RZ32'])
        retained['source_generation'] = 'unrelated'
        with self.assertRaisesRegex(ValueError, 'direct frozen predecessor'):
            inherited_actors(ancestor, retained, ancestor)
        retained['source_generation'] = self.old['identity']
        retained['bots']['6-32']['samples'] += 1
        with self.assertRaisesRegex(ValueError, 'Retained actor differs'):
            inherited_actors(ancestor, retained, ancestor)

    def test_machines_sharing_a_source_run_take_disjoint_deals(self):
        self.plan.update(model_note='the cohort in its own words', interpretation='how to read it')
        self.write()
        whole = prepare(self.tmp / 'whole', self.tmp / 'source', self.plan_path)
        self.assertNotIn('shard', whole)
        self.assertEqual((whole['model_note'], whole['interpretation']), ('the cohort in its own words', 'how to read it'))
        every = json.loads((self.tmp / 'whole' / 'source-indices.json').read_text())
        parts = []
        for k in range(2):
            run = self.tmp / f'box{k}'
            m = prepare(run, self.tmp / 'source', self.plan_path, shard=(k, 2))
            verify_generation(run, m)
            self.assertEqual(m['shard'], dict(index=k, of=2))
            parts.append(json.loads((run / 'source-indices.json').read_text()))
            self.assertEqual((parts[-1], m['target']), (every[k::2], len(every[k::2])))
            self.assertNotEqual(m['identity'], whole['identity'])
        self.assertFalse(set(parts[0]) & set(parts[1]))
        self.assertEqual(sorted(parts[0] + parts[1]), every)
        self.assertEqual(parse_shard('3/4'), (3, 4))
        for bad in ('4/4', '-1/4', '0/0', '1', 'a/b', '1/65'):
            with self.assertRaises(ValueError):
                parse_shard(bad)
        with self.assertRaises(ValueError):
            prepare(self.tmp / 'empty', self.tmp / 'source', self.plan_path, shard=(60, 64))        # more machines than deals: nothing left for this one

    def test_prepare_refuses_a_live_source_a_bad_mix_or_the_wrong_scorer(self):
        source = self.tmp / 'source'
        (source / 'STOP').unlink()
        with self.assertRaises(ValueError):
            prepare(self.tmp / 'run', source, self.plan_path)
        (source / 'STOP').write_text('drained')
        good = dict(pair_weights={'7a-32~6-32': 1}, audit_references={'7a-32': '3'}, common_bidder='6-32', roster=['7a-32', '6-32'])
        for mix in (dict(pair_weights={'7a-32~4b': 1}), dict(audit_references={}), dict(common_bidder='9'), dict(roster=['7a-32', 'x']),
                    dict(pair_weights={'6-32~5RZ32': 1}, audit_references={'6-32': '3'})):          # the last leaves the Gen7 bot in no pair
            self.plan.update(good)
            self.plan.update(mix)
            self.write()
            with self.assertRaises(ValueError):
                prepare(self.tmp / 'run', source, self.plan_path)
            self.assertFalse((self.tmp / 'run').exists())
        self.plan.update(good)
        self.write()
        for manifest in (dict(scorer_sha256='0' * 64), {}):
            (self.release / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                prepare(self.tmp / 'run', source, self.plan_path)
            self.assertFalse((self.tmp / 'run').exists())
        (self.release / 'policy.npz').write_bytes(b'another model')
        (self.release / 'manifest.json').write_text(json.dumps(dict(scorer_sha256=self.scorer)))
        with self.assertRaises(ValueError):
            prepare(self.tmp / 'run', source, self.plan_path)


class RuntimeAndPreflightTests(Fixture):
    TREE = dict(from_trick=1, root_margin=.5, root_cards=3, tricks=1, breadth=2, layouts=4, max_solves=2000)

    def spec(self, **gen7):
        return dict(id='7-test', engine='gen7', samples=8, near_tie=0., exploration=0., scorer='scorer.npz', lead_belief='lead.npz',
                    lead_state_bidder='bidder.keras', belief='belief.npz', belief_kind='public', gen6=dict(list_solve=16),
                    gen7_policy='gen7.npz', gen7=gen7)

    def test_the_runtime_builds_a_gen7_player_for_a_gen7_spec(self):
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            seven = gen5_runtime.player(self.spec(tree=self.TREE), self.root)
            six = gen5_runtime.player(dict(self.spec(), engine='gen6'), self.root)
        self.players += [seven, six]
        self.assertIs(type(seven), Gen7Player)
        self.assertIs(type(six), Gen6Player)
        self.assertEqual(len(seven.stages), 1)

    def test_the_preflight_accepts_real_decisions_and_catches_a_broken_record(self):
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            p = gen5_runtime.player(self.spec(tree=self.TREE), self.root)
        self.players.append(p)
        board = next(generate(1, 702))
        actions = []
        for room in (0, 1):
            t = play_table(board, ['x' if s % 2 == room else 'g' for s in range(4)], {'x': p, 'g': GreedyPlayer()}, seed=5)
            self.assertEqual(t['status'], 'ok', t.get('traceback'))
            actions += [a for a in t['actions'] if a['player'] == 'x' and 'gen6' in a]
        got = [check_decision(a, p.stages) for a in actions]
        self.assertGreater(sum(c for _, c, _, _ in got), 5)                     # consulted
        self.assertEqual(sum(s for s, _, _, _ in got), sum(a['ply'] > 0 for a in actions))
        used = next(a for a in actions if a.get('gen7_tree', {}).get('consulted'))
        for edit in (lambda a: a.update(selected_pimc_gap=.75),
                     lambda a: a['gen7_tree']['candidates'][0].update(adjusted=a['gen7_tree']['candidates'][0]['adjusted'] + .5),
                     lambda a: a['gen7_tree']['candidates'][-1].update(gap=.6),
                     lambda a: a.update(card=next(c for c in a['estimates'] if all(c not in x['cards'] or not x['kept']
                                                                                   for x in a['gen7_tree']['candidates']))),
                     lambda a: a['gen7_tree'].update(stage=0, solves=5000),
                     lambda a: a.update(near_tie=.125)):
            broken = deepcopy(used)
            try:
                edit(broken)
            except StopIteration:               # every legal card was kept: nothing to break this way
                continue
            with self.assertRaises(AssertionError):
                check_decision(broken, p.stages)
        outside = next(a for a in actions if 'gen7_tree' not in a)
        with self.assertRaises(AssertionError):
            check_decision(dict(outside, selected_pimc_gap=.1), p.stages)

    def test_a_stake_rule_stage_plays_whole_tables_and_its_records_pass_the_preflight(self):
        stake = dict(self.TREE, tricks=3, breadth=3, mass=.98, max_solves=20000, trust=.25, plain=1, path=.25, spread=.5, path_solves=400)
        with patch('bridge_harness.gen6.BidderState', FakeState), patch('bridge_harness.mixed_arena.Weights', FakeBelief):
            p = gen5_runtime.player(self.spec(tree=stake), self.root)
            shut = gen5_runtime.player(self.spec(tree=dict(stake, path=1e9)), self.root)
        self.players += [p, shut]
        board = next(generate(1, 702))
        actions, unsearched = [], []
        for room in (0, 1):
            seats = ['x' if s % 2 == room else 'g' for s in range(4)]
            t = play_table(board, seats, {'x': p, 'g': GreedyPlayer()}, seed=5)
            self.assertEqual(t['status'], 'ok', t.get('traceback'))
            actions += [a for a in t['actions'] if a['player'] == 'x' and 'gen6' in a]
            t = play_table(board, seats, {'x': shut, 'g': GreedyPlayer()}, seed=5)
            self.assertEqual(t['status'], 'ok', t.get('traceback'))
            unsearched += [a for a in t['actions'] if a['player'] == 'x' and 'gen6' in a]
        for a in actions:
            check_decision(a, p.stages)
        used = [a['gen7_tree'] for a in actions if a.get('gen7_tree', {}).get('consulted')]
        self.assertGreater(len(used), 5)
        self.assertTrue(all(n['stake'] >= 0 for n in used))
        self.assertTrue(any(n['stake'] > 1 for n in used))
        for n in (a['gen7_tree'] for a in unsearched if a.get('gen7_tree', {}).get('consulted')):
            for x in n['candidates']:                       # a threshold nothing clears: every candidate is a leaf, so no correction
                self.assertAlmostEqual(x['tree'], x['same_layouts'], places=9)


if __name__ == '__main__':
    unittest.main()
