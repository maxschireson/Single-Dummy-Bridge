"""The ladder (scripts/arena_ladder.py, G9-D9): sources, counting, the fit with priors, features."""
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import arena_ladder as L  # noqa: E402

JS = """ const sources=[
  {key:'gen6',group:'gen6',generation:6,variant:'6',environment:'codex',name:'Gen 6 · primary',branch:'arena-gen6-codex-feed',cohort:'aa'},
  {key:'gen5initial',generation:5,retired:true,allowed_pairs:['5~ben','5~5-32'],environment:'codex',name:'Gen 5',branch:'b',cohort:'bb'}
 ];
"""


def row(pair, x, fam, t=1.0, source='s', native_ok=True, snapshot=10.0, allowed=None, cohort='c'):
    return dict(source=source, pair=pair, native=x, native_ok=native_ok, family=fam, completed_epoch=t,
                snapshot_epoch=snapshot, allowed_pairs=allowed, cohort=cohort)


class Sources(unittest.TestCase):
    def test_builtin_list_and_registry_merge(self):
        b = L.builtin_sources(JS)
        self.assertEqual([s['key'] for s in b], ['gen6', 'gen5initial'])
        self.assertEqual(b[1]['allowed_pairs'], ['5~ben', '5~5-32'])
        self.assertTrue(b[1]['retired'])
        merged = L.dashboard_sources({'sources': [{'key': 'gen6', 'cohort': 'new'}, {'key': 'gen8', 'cohort': 'cc'}]}, JS)
        self.assertEqual([s['key'] for s in merged], ['gen8', 'gen6', 'gen5initial'])
        self.assertEqual(merged[1]['cohort'], 'new')
        self.assertEqual(merged[1]['branch'], 'arena-gen6-codex-feed')

    def test_members_are_canonical(self):
        self.assertEqual(L.members('PQ'), ['4p', '4b'])
        self.assertEqual(L.members('8s-32~ben64'), ['8s-32', 'ben64'])


class Counting(unittest.TestCase):
    def test_page_rules(self):
        rows = [row('a~b', 1, 'f1', t=1), row('b~a', 3, 'f1', t=2),          # same family, same pair: the first counts
                row('a~a', 5, 'f2'),                                          # self-play
                row('a~b', 7, 'f3', t=20),                                    # after the snapshot
                row('a~ben32', 2, 'f4'),                                      # hidden actor
                row('a~b', 4, 'f5', native_ok=False),                         # untrusted native column
                row('a~b', 6, 'f6', allowed=['a~c']),                         # not an allowed pair
                row('a~b', -2, 'f7', t=3)]
        self.assertEqual(L.native_results(rows, lambda s, b: b), [('a', 'b', 1), ('a', 'b', -2)])

    def test_variants_are_players(self):
        rows = [row('a~b', 1, 'f1', source='s1'), row('a~b', 2, 'f1', source='s2')]
        who = lambda s, b: f'{b}#{s}' if b == 'a' else b
        self.assertEqual(len(L.native_results(rows, who)), 2)       # two variants of a: two pairs, the family counts in each


class Fit(unittest.TestCase):
    def setUp(self):
        rng = random.Random(5)
        truth = {'z': 0.0, 'p': -1.0, 'c': -0.5, 'q': 0.3}
        self.results = []
        for i, j, n in [('p', 'z', 800), ('c', 'z', 800), ('c', 'p', 800), ('q', 'z', 30)]:
            for _ in range(n):
                self.results.append((i, j, truth[i] - truth[j] + rng.gauss(0, 3.0)))
        self.players = ['c', 'p', 'q', 'z']

    def test_data_dominate_and_prior_share(self):
        pri = {'c': ('p', 0.5, 0.1), 'p': (None, 0, 2.0), 'q': (None, 0, 2.0)}
        F = L.fit_population(self.results, self.players, 'z', pri, 2.0)
        s = dict(zip(self.players, F['s']))
        self.assertAlmostEqual(s['p'], -1.0, delta=0.3)
        self.assertAlmostEqual(s['c'] - s['p'], 0.5, delta=0.1)
        self.assertEqual(F['share']['z'], 0.0)
        self.assertLess(F['share']['p'], 0.05)                     # many boards, weak prior
        self.assertGreater(F['share']['c'], 0.05)                  # a tight prior carries some weight
        self.assertGreater(F['boards']['p'], 1000)

    def test_player_without_boards_is_all_prior(self):
        pri = {'c': (None, 0, 2.0), 'p': (None, 0, 2.0), 'q': (None, 0, 2.0), 'n': ('c', 0.2, 0.1)}
        F = L.fit_population(self.results, self.players + ['n'], 'z', pri, 2.0)
        s = dict(zip(self.players + ['n'], F['s']))
        self.assertAlmostEqual(s['n'] - s['c'], 0.2, places=6)
        self.assertEqual(F['share']['n'], 1.0)


class Features(unittest.TestCase):
    def test_grouped_named_and_matched(self):
        parent = {'gen7.play_weight': 0.5, 'gen7.tie_break': 'net', 'samples': 32}
        child = {'gen7.play_weight': 1.0, 'gen7.tie_break': 'net', 'samples': 32, 'gen7.early_pool': 512,
                 'gen7.early_play_weight': 1.0, 'artifact_sha256.system_scorer': 'a' * 64}
        impacts = [{'id': 'x', 'features': ['play reading weight (deal-list exponent)'], 'when': 'changed'},
                   {'id': 'y', 'features': ['play reading weight (deal-list exponent)'], 'when': 'added'},
                   {'id': 'z', 'features': ['early play reading (from trick 1, before the deal list)']}]
        f = {r['feature']: r for r in L.features(child, parent, impacts)}
        self.assertEqual(set(f), {'play reading weight (deal-list exponent)', 'early play reading (from trick 1, before the deal list)',
                                  "system scorer (reads other systems' auctions)"})
        self.assertEqual([i['id'] for i in f['play reading weight (deal-list exponent)']['impacts']], ['x'])
        self.assertEqual([i['id'] for i in f['early play reading (from trick 1, before the deal list)']['impacts']], ['z'])
        self.assertEqual(f["system scorer (reads other systems' auctions)"]['value'], 'file aaaaaaaa')
        self.assertEqual(L.features(child, None, impacts), [])

    def test_settings_ignore_paths_and_names(self):
        a = L.spec_settings({'id': '1', 'label': 'Gen 1', 'bidding': 'models/bidder-v1.keras', 'samples': 32,
                             'artifact_sha256': {'bidding': 'ab'}})
        b = L.spec_settings({'id': 'v1', 'bidding': 'assets/bidding/dds.keras', 'samples': 32, 'artifact_sha256': {'bidding': 'ab'}})
        self.assertEqual(L.fingerprint(a), L.fingerprint(b))
        self.assertEqual(L.fingerprint(None), 'unpublished')


if __name__ == '__main__':
    unittest.main()
