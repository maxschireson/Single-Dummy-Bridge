import unittest
from scripts.run_filtered_arena import cancellation_plan, scheduled_pair, verify_plan
from bridge_harness.v4_arena import run_board
from bridge_harness.bidding_env import make_board
from tests.test_v4_arena import PassBidder, Player, ArenaTests


class FilteredArenaTests(unittest.TestCase):
    def test_selection_matches_actual_play_and_keeps_completed_self(self):
        manifest = ArenaTests().manifest()
        manifest.update(target=32, pair_schedule=['44'] * 8 + ['43'] * 4 + ['42'] * 2 + ['41', '32'],
                        common_bidder='4', two_self_rooms=True,
                        independent_room_seeds=True, audit_references={'4': '3', '3': '2'})
        bidders = {key: PassBidder() for key in manifest['roster']}
        actual = {}
        for index in range(32):
            row = run_board('.', manifest, make_board(73, index, 'train').to_dict(), index,
                            bidders, player_factory=Player)
            actual[index] = tuple(row['pair'])
            self.assertEqual(scheduled_pair(manifest, index), actual[index])
        self_indices = {i for i, pair in actual.items() if pair == ('4', '4')}
        done = {min(self_indices), next(i for i in actual if i not in self_indices)}
        plan = cancellation_plan(manifest, done)
        self.assertEqual(set(plan['skipped_indices']), self_indices - done)
        self.assertEqual(plan['target'], 17)
        self.assertEqual(set(plan['retained_self_indices']), self_indices & done)
        remaining = set(range(32)) - done - set(plan['skipped_indices'])
        self.assertTrue(all(actual[i] != ('4', '4') for i in remaining))
        self.assertTrue({('4', '3'), ('4', '2'), ('4', '1'), ('3', '2')} <= {actual[i] for i in remaining})
        verify_plan(plan, manifest, done | remaining)
        with self.assertRaises(ValueError):
            verify_plan(plan, manifest, done | {next(iter(self_indices - done))})

    def test_component_schedule_retained(self):
        manifest = dict(identity='fixture', seed=42, target=60, roster=['4', '4p', '4b', '3'],
                        pair_schedule=[['4p', '3'], ['4b', '3'], ['4p', '4b'],
                                       ['4p', '4'], ['4b', '4'], ['4', '3']])
        plan = cancellation_plan(manifest, set())
        self.assertEqual(plan['skipped_indices'], [])
        self.assertEqual(plan['target'], 60)


if __name__ == '__main__':
    unittest.main()
