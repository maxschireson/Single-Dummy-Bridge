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
from bridge_harness import arena_ratings as ar  # noqa: E402

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


class Locking(Base):
    def test_a_second_runner_is_refused_and_a_board_written_twice_counts_once(self):
        c = self.control()
        held = a9.lock(c)
        with self.assertRaises(SystemExit):
            a9.lock(c)
        held.close()
        a9.lock(c).close()
        a9.play_epoch(c, self.backend)
        path = c / 'results' / 'e0001' / 'slot0.jsonl'
        first = path.read_text().splitlines()[0]
        path.write_text(path.read_text() + first + '\n')
        self.assertEqual(len(a9.read_results(c)), RULES['epoch']['boards'])


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


class GainSchedule(Base):
    """The arrival run's shares (G9-D6): self-play only for training, and a gain pool of admission and panel pairs."""
    GAIN = dict(RULES, shares=dict(training=0.10, promotion=0.30, gain=0.60), gain_purposes=['admission', 'panel'],
                training_pairs='self-play', epoch=dict(sizes=[300, 600, 900], boards=1200))

    def test_epoch_sizes_by_epoch(self):
        self.assertEqual([a9.epoch_boards(self.GAIN, n) for n in (1, 2, 3, 4)], [300, 600, 900, 1200])
        self.assertEqual([a9.epoch_boards(RULES, n) for n in (1, 2)], [600, 600])

    def test_a_newcomer_draws_the_gain_before_a_well_measured_pair(self):
        pairs = [ar.Pair('champ', 'anchor-a', 400, 0.5, 14.0), ar.Pair('champ', 'anchor-b', 400, 1.5, 14.0), ar.Pair('anchor-a', 'anchor-b', 400, 1.0, 14.0)]
        R = ar.fit(pairs, ['champ', 'anchor-a', 'anchor-b'], 'anchor-a')
        got = a9.gain_units(['new~champ', 'champ~anchor-a'], 10, R, {}, 30)
        self.assertGreater(got['new~champ'], got['champ~anchor-a'])
        self.assertEqual(sum(got.values()), 10)
        fed = a9.gain_units(['new~champ', 'champ~anchor-a'], 10, R, {'new~champ': 3000}, 30)    # a floor already measures it
        self.assertLess(fed['new~champ'], got['new~champ'])

    def test_shares_with_a_test_open_and_without(self):
        c = self.control(rules=self.GAIN)
        m = a9.current(c)
        w = m['schedule']['pair_weights']
        self.assertEqual(w['champ~champ'], 10)                         # no test open: its 0.30 joins the pool, not training
        self.assertEqual(sum(w.values()), 100)
        self.queue(c, 'activate', 'weak')
        (c / 'queue' / '1-open.json').write_text(json.dumps(a9.event('open-test', 'weak', 'max', 'unit test', champion='champ', epoch=2)))
        nxt, _ = self.epoch(c)
        w = nxt['schedule']['pair_weights']
        self.assertEqual((w['champ~champ'], w['weak~champ']), (10, 30))
        self.assertNotIn('champ~weak', w)                               # an active player under test is not trained against
        self.assertEqual(sum(v for p, v in w.items() if p not in ('champ~champ', 'weak~champ')), 60)


class PlayerFiles(unittest.TestCase):
    """configs/players: a package's override files are the nets its artifact_sha256 names (guest-b bids the Gen 5 net)."""

    def test_every_override_file_is_the_net_the_package_names(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('arena9_cli', ROOT / 'scripts' / 'arena9.py')
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        checked = 0
        for f in sorted((ROOT / 'configs' / 'players').glob('*.json')):
            b = json.loads(f.read_text())['bundle']
            named = b.get('artifact_sha256') or {}
            for k in cli.OVERRIDE_FILES:
                v = (b.get('overrides') or {}).get(k)
                if not isinstance(v, str) or not (ROOT / v).is_file() or k not in named:
                    continue                    # a net kept as parts is checked by the runner once it is restored
                self.assertEqual(cli.file_sha256(ROOT / v), named[k], f'{f.stem}: {k}')
                checked += 1
        if not checked:
            self.skipTest('no override files restored in this checkout')


if __name__ == '__main__':
    unittest.main()
