"""Operational invariants for shared phase-1 limits, independent of scores."""
import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from phase1_fleet import update, fetch_snapshot
from phase1_fleet import canonical_pair, count_families, PAIRS


class FleetTests(unittest.TestCase):
    def snapshot(self, campaign, ready=True, actor='actor'):
        pair = '7s-32~6-32'
        files = {
            'arena/manifest.json': dict(identity='cohort', campaign=campaign,
                bots={'7s-32': {'identity': actor}}, pair_weights={pair: 1}),
            'recovery/plan.json': dict(campaign=campaign, launch_enabled=ready, pending=[],
                pair_weights={pair: 1}, common_bidder='6-32'),
            'arena/data.json': dict(manifest_identity='cohort', generated_epoch=2),
            'arena/replays/data/cohort/index.json': dict(cohort='cohort',
                records=[dict(pair=pair, family='family', completed_epoch=1)])}
        return {p: json.dumps(d).encode() for p,d in files.items()}

    def test_independent_and_selfplay_campaigns_contribute_comparison_families(self):
        for campaign in ['gen7-phase1-independent-20261112', 'gen7-phase1-selfplay-20261112',
                         'gen7-independent-selfplay-ben-20261112']:
            with self.subTest(campaign=campaign), patch('phase1_fleet.fetch_bytes', side_effect=lambda rev,path:self.snapshot(campaign)[path]):
                result = fetch_snapshot(('feed', 'revision'), 'actor')
                self.assertEqual(result['rows'], [dict(pair='7s-32~6-32', family='family')])

    def test_pre7_closed_plans_and_different_actors_do_not_count(self):
        cases = [('gen7-pre7-20261112', True, 'actor'),
                 ('gen7-phase1-independent-20261112', False, 'actor'),
                 ('gen7-phase1-independent-20261112', True, 'older-trust')]
        for campaign, ready, actor in cases:
            with self.subTest(campaign=campaign, ready=ready, actor=actor), patch('phase1_fleet.fetch_bytes', side_effect=lambda rev,path:self.snapshot(campaign, ready, actor)[path]):
                self.assertIn('excluded', fetch_snapshot(('feed', 'revision'), 'actor'))

    def test_manifest_and_ready_plan_must_agree(self):
        campaign = 'gen7-independent-selfplay-ben-20261112'
        files = self.snapshot(campaign)
        plan = json.loads(files['recovery/plan.json'])
        plan['pair_weights'] = {'7s-32~1': 1}
        files['recovery/plan.json'] = json.dumps(plan).encode()
        with patch('phase1_fleet.fetch_bytes', side_effect=lambda rev,path:files[path]):
            with self.assertRaisesRegex(ValueError, 'plan/manifest mismatch'):
                fetch_snapshot(('feed', 'revision'), 'actor')

    def test_outcomes_published_after_the_snapshot_do_not_count(self):
        campaign = 'gen7-independent-selfplay-ben-20261112'
        files = self.snapshot(campaign)
        path = 'arena/replays/data/cohort/index.json'
        index = json.loads(files[path])
        index['records'].append(dict(pair='7s-32~6-32', family='later', completed_epoch=3))
        files[path] = json.dumps(index).encode()
        with patch('phase1_fleet.fetch_bytes', side_effect=lambda rev,path:files[path]):
            result = fetch_snapshot(('feed', 'revision'), 'actor')
        self.assertEqual([row['family'] for row in result['rows']], ['family'])

    def test_replay_shard_checksum_failure_stops_accounting(self):
        campaign = 'gen7-independent-selfplay-ben-20261112'
        files = self.snapshot(campaign)
        prefix = 'arena/replays/data/cohort/'
        index = json.loads(files[prefix+'index.json'])
        index.update(records=[], record_shards=['shard.json'], record_shard_sha256={'shard.json': '0'*64})
        files[prefix+'index.json'] = json.dumps(index).encode()
        files[prefix+'shard.json'] = b'[]'
        with patch('phase1_fleet.fetch_bytes', side_effect=lambda rev,path:files[path]):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fetch_snapshot(('feed', 'revision'), 'actor')

    def test_mirrored_feeds_and_unpublished_local_receipts_do_not_double_count(self):
        first = [dict(pair='7s-32~6-32', family=str(i), imps=10) for i in range(2000)]
        mirror = [dict(pair='6-32~7s-32', family=str(i), imps=-10) for i in range(2000)]
        local = [dict(pair='7s-32~6-32', family='1999', imps=0)]
        seen = count_families(first + mirror + local)
        self.assertEqual(len(seen['7s-32~6-32']), 2000)
        self.assertFalse(all(len(v) >= 2000 for v in seen.values()))

    def test_only_authorized_pairs_can_satisfy_phase1(self):
        rows = [dict(pair=p, family=str(i)) for p in PAIRS for i in range(2000)]
        rows += [dict(pair='7f-32~7f-32', family='not-phase1'), dict(pair='7s-32~7s-32', family='not-phase1')]
        self.assertTrue(all(len(v) == 2000 for v in count_families(rows).values()))
        self.assertIsNone(canonical_pair('7s-32~7s-32'))
        self.assertIsNone(canonical_pair('7s-32~unknown'))

    def test_drain_only_after_all_owned_pooled_pairs_reach_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / 'receipts').mkdir()
            owned = ['7s-32~6-32', '7s-32~5RZ32', '7s-32~1']
            manifest = dict(identity='cohort', bots={'7s-32': {'identity': 'actor'}},
                            phase1=dict(owned_pairs=owned))
            (run / 'manifest.json').write_text(json.dumps(manifest))
            families = {p: [str(i) for i in range(2000 if p in owned else 0)] for p in PAIRS}
            families[owned[-1]].pop()
            (run / 'phase1-seen-families.json').write_text(json.dumps(dict(actor_identity='actor', families=families)))
            with patch('phase1_fleet.subprocess.check_output', return_value=''):
                self.assertFalse(update(run, run)['owned_complete'])
                self.assertFalse((run / 'STOP').exists())
                (run / 'receipts' / '000001.json').write_text(json.dumps(dict(
                    manifest_identity='cohort', pair=owned[-1], family='1999')))
                result = update(run, run)
            self.assertTrue(result['owned_complete'])
            self.assertFalse(result['all_five_complete'])
            self.assertFalse(result['phase2_authorized'])
            self.assertIn('drain', (run / 'STOP').read_text())

    def test_selfplay_only_has_no_comparison_stop_predicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / 'receipts').mkdir()
            (run / 'manifest.json').write_text(json.dumps(dict(identity='cohort',
                bots={'7s-32': {'identity': 'actor'}}, phase1=dict(owned_pairs=[]))))
            (run / 'phase1-seen-families.json').write_text(json.dumps(dict(actor_identity='actor',
                families={p:[str(i) for i in range(2000)] for p in PAIRS})))
            with patch('phase1_fleet.subprocess.check_output', return_value=''):
                result = update(run, run)
            self.assertTrue(result['all_five_complete'])
            self.assertFalse(result['owned_complete'])
            self.assertFalse((run / 'STOP').exists())


if __name__ == '__main__':
    unittest.main()
