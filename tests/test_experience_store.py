"""Tests for bridge_harness/experience_store.py (G9-D5). Standard library only."""
import gzip
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness import experience as xp  # noqa: E402
from bridge_harness import experience_store as st  # noqa: E402
from bridge_harness.player_model import PlayerModel  # noqa: E402


def board_envelopes(cohort, index, t, family, player='bot-a', bidder='house'):
    """What a collector would write for one board: card statistics for the player at both tables (opposite seats)
    and bidding statistics for whoever bid the common auction."""
    auction = ['1N', 'P', '3N', 'P', 'P', 'P']
    out = []
    for room, seats in ((0, 'NS'), (1, 'EW')):
        key = f'{cohort}/{index}/{room}'
        stats = {'card.count': xp.count(**{'hit/3': room, 'all/3': 1}),
                 'play.info': xp.moment([0.3, 1.0], [0.1 * index, 0.05 * room + 0.01]),
                 'bid.1nt.miss': xp.hist([index % 3 - 1])}
        out.append(st.envelope(xp.delta(player, key, stats), cohort, t + room, st.occasion(family, seats, auction)))
    out.append(st.envelope(xp.delta(bidder, f'{cohort}/{index}/auction', {'profile': xp.loglik(std=-1.5 - index * 0.01, precision=-2.25)}),
                           cohort, t, st.occasion(family, 'NESW', auction)))
    return out


def corpus():
    env = []
    for i in range(40):
        env += board_envelopes('cohort-1' if i < 25 else 'cohort-2', i, 1000.0 + 10 * i, f'fam{i}')
    return env


class Merge(unittest.TestCase):
    def test_any_order_gives_the_same_stores(self):
        env = corpus()
        want, report = st.merge(env)
        for seed in range(5):
            shuffled = env[:]
            random.Random(seed).shuffle(shuffled)
            got, _ = st.merge(shuffled)
            self.assertEqual(st.canonical(got), st.canonical(want))
        self.assertEqual(report['counted'], 120)
        self.assertEqual(want['bot-a']['boards'], 80)          # both rooms of each of 40 boards
        self.assertEqual(want['house']['boards'], 40)

    def test_matches_folding_with_add_in_key_order(self):
        env = corpus()
        got, _ = st.merge(env)
        store = xp.empty('bot-a')
        for e in sorted((e for e in env if e['delta']['player'] == 'bot-a'), key=lambda e: e['delta']['key']):
            store = xp.add(store, e['delta'])
        self.assertEqual(st.canonical(got['bot-a']), st.canonical(store))

    def test_a_repeated_delta_is_ignored(self):
        env = corpus()
        repeated = env + [dict(e, source='republisher') for e in env[:9]]
        got, report = st.merge(repeated)
        want, _ = st.merge(env)
        self.assertEqual(st.canonical(got), st.canonical(want))
        self.assertEqual(report['repeats'], 9)

    def test_two_different_deltas_for_one_key_are_refused(self):
        env = corpus()
        bad = json.loads(json.dumps(env[0]))
        bad['delta']['stats']['card.count']['n']['all/3'] = 2.0
        with self.assertRaises(ValueError):
            st.merge(env + [bad])

    def test_a_replayed_occasion_counts_once_and_the_earliest_wins(self):
        env = corpus()
        replay = board_envelopes('cohort-9', 3, 5000.0, 'fam3')        # deal 3 again, later, in another cohort
        got, report = st.merge(env + replay)
        want, _ = st.merge(env)
        self.assertEqual(st.canonical(got), st.canonical(want))
        self.assertEqual(len(report['occasion_repeats']), 3)
        self.assertTrue(all(r['dropped'].startswith('cohort-9/') for r in report['occasion_repeats']))

    def test_the_other_room_is_a_different_occasion(self):
        a = st.occasion('fam', 'NS', ['1N', 'P', 'P', 'P'])
        self.assertNotEqual(a, st.occasion('fam', 'EW', ['1N', 'P', 'P', 'P']))
        self.assertNotEqual(a, st.occasion('fam', 'NS', ['1S', 'P', 'P', 'P']))

    def test_cut_off_leaves_out_later_boards(self):
        env = corpus()
        got, report = st.merge(env, cut_off=1000.0 + 10 * 19 + 1)
        self.assertEqual(got['house']['boards'], 20)
        self.assertGreater(report['after_cut_off'], 0)

    def test_files_round_trip(self):
        env = corpus()
        with tempfile.TemporaryDirectory() as d:
            st.write(Path(d) / 'c1.jsonl.gz', env[:60])
            st.write(Path(d) / 'c2.jsonl', env[60:])
            st.write(Path(d) / 'c1.jsonl.gz', env[:3])                 # appended again: repeats
            back = st.read(sorted(Path(d).iterdir()))
        got, report = st.merge(back)
        self.assertEqual(st.canonical(got), st.canonical(st.merge(env)[0]))
        self.assertEqual(report['repeats'], 3)


class Snapshots(unittest.TestCase):
    def setUp(self):
        self.stores, _ = st.merge(corpus())

    def test_named_by_content_and_reproducible(self):
        a = st.epoch_snapshot(self.stores, 3, 1400.0)
        b = st.epoch_snapshot(json.loads(json.dumps(self.stores)), 3, 1400.0)
        self.assertEqual(a['id'], b['id'])
        self.assertNotEqual(a['id'], st.epoch_snapshot(self.stores, 4, 1400.0)['id'])
        self.assertTrue(all(p['snapshot'] == a['id'] and 'applied' not in p for p in a['players'].values()))

    def test_written_once_and_checked_on_load(self):
        doc = st.epoch_snapshot(self.stores, 3, 1400.0)
        with tempfile.TemporaryDirectory() as d:
            path = st.write_snapshot(d, doc)
            self.assertEqual(st.write_snapshot(d, doc), path)          # same content: no-op
            other = st.epoch_snapshot(self.stores, 4, 1400.0)
            impostor = dict(other, id=doc['id'])
            with self.assertRaises(ValueError):
                st.write_snapshot(d, impostor)                          # wrong name for the content
            with gzip.open(path, 'rt') as f:
                body = json.load(f)
            body['players']['bot-a']['boards'] += 1                     # edited on disk
            with gzip.open(path, 'wt') as f:
                f.write(st.canonical(body))
            with self.assertRaises(ValueError):
                st.load_snapshot(path)

    def test_a_snapshot_takes_no_more_boards(self):
        doc = st.epoch_snapshot(self.stores, 3, 1400.0)
        with self.assertRaises(ValueError):
            xp.add(doc['players']['bot-a'], board_envelopes('cohort-3', 99, 9000.0, 'famx')[0]['delta'])

    def test_player_models_accept_it_and_a_newcomer_gets_an_empty_named_one(self):
        doc = st.epoch_snapshot(self.stores, 3, 1400.0)
        m = PlayerModel(id='bot-a', experience=st.player_snapshot(doc, 'bot-a'))
        self.assertEqual((m.boards, m.snapshot), (80, doc['id']))
        new = PlayerModel(id='guest', experience=st.player_snapshot(doc, 'guest'))
        self.assertEqual((new.boards, new.snapshot), (0, doc['id']))


if __name__ == '__main__':
    unittest.main()
