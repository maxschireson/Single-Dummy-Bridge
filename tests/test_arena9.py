"""Tests for the Gen 9 population arena (bridge_harness/arena9.py, G9-D4) on synthetic boards. numpy only."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import arena9 as a9  # noqa: E402

RULES = dict(schema='arena-rules-v1', version='test', condition='native', reference='anchor-a',
             promotion=dict(alpha=0.05, beta=0.10, d=0.1, cap=10000), admission=dict(se=0.15, max_boards=2000),
             retirement=dict(min_epochs=1, gap=1.0), shares=dict(training=0.55, promotion=0.20, panel=0.15, admission=0.10),
             epoch=dict(boards=600), weight_units=100, max_weight_ratio=2)


def package(pid, kind, strength, bidding=0.0, **extra):
    return dict(dict(schema='player-package-v1', id=pid, label=pid, kind=kind, bundle=dict(source='sim', sim=dict(strength=strength, bidding=bidding)),
                     declaration=dict(system=None), lineage=dict(training_families={}), needs={}, licence='redistributable'), **extra)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.pkgs = {p['id']: p for p in (package('champ', 'house', 0.0), package('anchor-a', 'anchor', -0.8),
                                          package('anchor-b', 'anchor', -1.8), package('weak', 'house', -3.0),
                                          package('cand', 'house', 1.0), package('late', 'synthetic', -0.3))}
        self.backend = a9.SimBackend(self.pkgs, noise_sd=3.0)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def control(self, name='c', only=('champ', 'anchor-a', 'anchor-b', 'weak'), rules=RULES):
        c = self.dir / name
        a9.init(c, {k: v for k, v in self.pkgs.items() if k in only}, rules, 'champ', 'test', 'unit test')
        return c

    def queue(self, c, kind, player):
        (c / 'queue' / f'0-{kind}-{player}.json').write_text(json.dumps(a9.event(kind, player, 'max', 'unit test')))

    def epoch(self, c):
        a9.play_epoch(c, self.backend)
        return a9.close_epoch(c, self.pkgs)


class Packages(Base):
    def test_checks(self):
        self.assertEqual(a9.check_package(self.pkgs['champ']), [])
        bad = package('x', 'house', 0, licence='private')
        self.assertTrue(any('licence' in p for p in a9.check_package(bad)))
        oracle = package('o', 'house', 0); oracle['bundle']['gen9'] = dict(oracle=dict(mode='tilt'))
        self.assertTrue(any('oracle' in p for p in a9.check_package(oracle)))
        nolineage = package('n', 'house', 0); nolineage['lineage'] = {}
        self.assertTrue(any('lineage' in p for p in a9.check_package(nolineage)))
        self.assertTrue(a9.check_package(package('a~b', 'house', 0)))

    def test_identity_ignores_artifact_paths(self):
        a = package('p', 'house', 0); a['bundle'] = dict(source='capsule', bot='6-32', overrides=dict(gen7_policy='models/x/v4.npz'))
        b = json.loads(json.dumps(a)); b['bundle']['overrides']['gen7_policy'] = 'anchors/models/x/v4.npz'
        c = json.loads(json.dumps(a)); c['bundle']['overrides']['gen7'] = dict(trust=0.25)
        self.assertEqual(a9.identity(a, {'gen7_policy': 'h1'}), a9.identity(b, {'gen7_policy': 'h1'}))
        self.assertNotEqual(a9.identity(a, {'gen7_policy': 'h1'}), a9.identity(a, {'gen7_policy': 'h2'}))
        self.assertNotEqual(a9.identity(a), a9.identity(c))
        d = json.loads(json.dumps(a)); d['bundle']['artifact_sha256'] = {'gen7_policy': 'h1'}
        e = json.loads(json.dumps(a)); e['bundle']['artifact_sha256'] = {'gen7_policy': 'h2'}
        self.assertEqual(a9.identity(d), a9.identity(a, {'gen7_policy': 'h1'}))   # hashes in the bundle count, not blanked
        self.assertNotEqual(a9.identity(d), a9.identity(e))


class Epochs(Base):
    def test_first_epoch(self):
        c = self.control(only=('champ', 'anchor-a', 'anchor-b', 'weak', 'cand'))
        m = a9.current(c)
        self.assertEqual((m['epoch'], m['champion']), (1, 'champ'))
        purposes = m['schedule']['purposes']
        # every package submitted at the start is a candidate except the anchors, so `weak` is being admitted too
        self.assertEqual(sorted(purposes['admission']), ['cand~anchor-a', 'cand~anchor-b', 'cand~champ',
                                                         'weak~anchor-a', 'weak~anchor-b', 'weak~champ'])
        self.assertEqual(sorted(purposes['panel']), ['champ~anchor-a', 'champ~anchor-b'])
        self.assertIn('champ~champ', purposes['training'])
        self.assertNotIn('promotion', purposes)
        self.assertEqual(m['id'], a9.epoch_id(m))

    def test_an_epoch_is_played_closed_and_never_edited(self):
        c = self.control()
        nxt, _ = self.epoch(c)
        self.assertEqual((a9.current(c)['epoch'], nxt['previous']), (2, json.loads(a9.epoch_path(c, 1).read_text())['id']))
        self.assertEqual(len([l for l in (c / 'results' / 'e0001' / 'slot0.jsonl').read_text().splitlines() if l]), RULES['epoch']['boards'])
        with self.assertRaises(ValueError):
            a9.write_epoch(c, json.loads(a9.epoch_path(c, 1).read_text()))
        self.assertTrue((c / 'ratings' / '0001-native.json').exists())
        with self.assertRaises(ValueError):                 # an epoch closes only when its boards are in
            a9.close_epoch(c, self.pkgs)

    def test_the_next_epoch_is_a_function_of_its_inputs(self):
        ids = []
        for name in ('one', 'two'):
            c = self.control(name)
            self.queue(c, 'submit', 'late')
            nxt, _ = self.epoch(c)
            ids.append(nxt['id'])
        self.assertEqual(ids[0], ids[1])

    def test_a_player_arrives_and_one_leaves_with_no_code_change(self):
        c = self.control()
        self.queue(c, 'submit', 'late')
        self.queue(c, 'retire', 'weak')
        nxt, decisions = self.epoch(c)
        rostered = set(nxt['players'])
        self.assertIn('late', rostered)
        self.assertNotIn('weak', rostered)
        self.assertIn('late~champ', nxt['schedule']['purposes']['admission'])
        self.assertEqual(sorted(p.suffix for p in (c / 'queue').iterdir()), ['.applied', '.applied'])
        st = a9.fold(a9.read_log(c))
        self.assertEqual((st['late']['status'], st['weak']['status']), ('candidate', 'retired'))

    def test_a_queued_oracle_or_unknown_package_is_refused(self):
        c = self.control()
        self.pkgs['o'] = package('o', 'house', 0); self.pkgs['o']['bundle']['gen9'] = dict(oracle=dict(mode='tilt'))
        self.queue(c, 'submit', 'o')
        self.queue(c, 'submit', 'nobody')
        nxt, decisions = self.epoch(c)
        self.assertEqual(sorted(d['player'] for d in decisions if d['kind'] == 'refused'), ['nobody', 'o'])
        self.assertNotIn('o', nxt['players'])

    def test_weight_changes_are_capped(self):
        st = a9.fold([dict(seq=0, event='submit', player='h', kind='house', package_sha256='x'),
                      dict(seq=1, event='submit', player='a', kind='anchor', package_sha256='y'),
                      dict(seq=2, event='champion', player='h')])
        prev = dict(purposes=dict(panel=['h~a'], training=['h~h']), pair_weights={'h~a': 2, 'h~h': 40})
        sch = a9.schedule(st, RULES, previous=prev)
        self.assertLessEqual(sch['pair_weights']['h~a'], 4)
        self.assertGreaterEqual(sch['pair_weights']['h~h'], 20)
        moved = dict(purposes=dict(admission=['h~a'], training=['h~h']), pair_weights={'h~a': 1, 'h~h': 40})
        self.assertGreater(a9.schedule(st, RULES, previous=moved)['pair_weights']['h~a'], 2)   # new purpose: not capped


class Rules(Base):
    def test_a_far_weaker_player_is_retired_by_rule_and_anchors_are_not(self):
        c = self.control(rules=dict(RULES, epoch=dict(boards=1500)))
        self.queue(c, 'activate', 'weak')
        for _ in range(4):
            nxt, decisions = self.epoch(c)
            if any(d['kind'] == 'retire' for d in decisions):
                break
        st = a9.fold(a9.read_log(c))
        self.assertEqual(st['weak']['status'], 'retired')
        self.assertEqual((st['anchor-b']['status'], st['champ']['status']), ('anchor', 'champion'))
        retire = [e for e in a9.read_log(c) if e['event'] == 'retire'][0]
        self.assertTrue(retire['authority'].startswith('rules test'))
        self.assertLess(retire['evidence']['gap'], -1.0)

    def test_a_clearly_better_candidate_is_admitted_tested_and_promoted(self):
        c = self.control(only=('champ', 'anchor-a', 'anchor-b', 'cand'), rules=dict(RULES, epoch=dict(boards=2000)))
        seen = []
        for _ in range(6):
            nxt, decisions = self.epoch(c)
            seen += [d['kind'] for d in decisions]
            if nxt['champion'] == 'cand':
                break
        self.assertEqual(nxt['champion'], 'cand', seen)
        self.assertLess(seen.index('admit'), seen.index('open-test'))
        promote = [e for e in a9.read_log(c) if e['event'] == 'promote'][0]
        self.assertGreaterEqual(promote['evidence']['K'], 20.0)
        st = a9.fold(a9.read_log(c))
        self.assertEqual(st['champ']['status'], 'active')       # the old champion stays in the league


if __name__ == '__main__':
    unittest.main()
