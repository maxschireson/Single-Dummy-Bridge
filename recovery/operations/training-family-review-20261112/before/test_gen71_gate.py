import hashlib
import json
from unittest import TestCase, main
from unittest.mock import patch

import gen71_gate as g


class GateTests(TestCase):
    def row(self, i=0, **kwargs):
        return dict(dict(index=i, family=f'family{i}', pair=g.PAIR, imps=1,
                         completed_epoch=10+i, episode_sha256='episode'), **kwargs)

    def test_reverse_orientation_and_outcome_blind_family_choice(self):
        early = g.observation(self.row(imps=-4), 'a')
        late = g.observation(self.row(i=1, family='family0', imps=9), 'b')
        reverse = g.observation(self.row(i=2, pair='7s-32~71s-32', imps=3), 'a')
        result = g.deduplicate([late, early, reverse, early])
        self.assertEqual([r['imps'] for r in result], [-4, -3])

    def test_same_receipt_conflict_is_an_error(self):
        a = g.observation(self.row(), 'a')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            g.deduplicate([a, dict(a, imps=-9)])

    def test_both_gate_conditions_are_required(self):
        positive = [dict(imps=1) for _ in range(1000)]
        self.assertFalse(g.statistics_for(positive[:999])['qualified'])
        self.assertTrue(g.statistics_for(positive)['qualified'])
        self.assertFalse(g.statistics_for([dict(imps=0) for _ in range(1000)])['qualified'])
        self.assertFalse(g.statistics_for([dict(imps=(-1)**i * 10 + .01) for i in range(1000)])['qualified'])
        self.assertIsNone(g.statistics_for([])['ci95'])

    def test_null_nonfinite_scores_rejected(self):
        for value in (None, float('inf'), float('nan'), True):
            with self.assertRaises(ValueError):
                g.observation(self.row(imps=value), 'a')
        self.assertIsNone(g.observation(self.row(pair='71s-32~6-32', imps=None), 'a'))

    def fixture(self, ready=True, corrupt=False, wrong_actor=False):
        actors = {'71s-32': '71actor', '7s-32': '7actor'}
        manifest = dict(identity='cohort', campaign='independent-campaign',
            bots={k:dict(identity=v) for k,v in actors.items()}, pair_weights={g.PAIR:1})
        if wrong_actor:
            manifest['bots']['71s-32']['identity'] = 'research-net'
        shard = json.dumps([self.row(), self.row(i=1, completed_epoch=999)]).encode()
        documents = {'arena/manifest.json':manifest,
            'recovery/plan.json':dict(launch_enabled=ready, pending=[], campaign=manifest['campaign'],
                                     pair_weights=manifest['pair_weights'], common_bidder='6-32'),
            'arena/data.json':dict(manifest_identity='cohort', generated_epoch=30),
            'arena/replays/data/cohort/index.json':dict(cohort='cohort', record_shards=['records.json'],
                record_shard_sha256={'records.json':'bad' if corrupt else hashlib.sha256(shard).hexdigest()}),
            'arena/replays/data/cohort/records.json':shard}
        def fetch(rev, path):
            value = documents[path]
            return value if isinstance(value, bytes) else json.dumps(value).encode()
        return actors, fetch

    def test_ready_independent_campaign_snapshot_cutoff_and_checksum(self):
        actors, fetch = self.fixture()
        with patch.object(g, 'fetch_bytes', side_effect=fetch):
            result = g.fetch_snapshot(('arena-gen71-independent-feed', 'rev'), actors)
        self.assertEqual(len(result['rows']), 1)
        actors, fetch = self.fixture(corrupt=True)
        with patch.object(g, 'fetch_bytes', side_effect=fetch), self.assertRaisesRegex(ValueError, 'checksum'):
            g.fetch_snapshot(('arena-gen71-independent-feed', 'rev'), actors)

    def test_closed_plan_and_different_policy_excluded(self):
        for options in (dict(ready=False), dict(wrong_actor=True)):
            actors, fetch = self.fixture(**options)
            with patch.object(g, 'fetch_bytes', side_effect=fetch):
                result = g.fetch_snapshot(('arena-gen71-independent-feed', 'rev'), actors)
            self.assertIn('excluded', result)
            self.assertNotIn('rows', result)


if __name__ == '__main__':
    main()
