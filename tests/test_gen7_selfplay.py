"""Gen 7 self-play: the plan Max asked for on 12 November 2026, the runtime's check of a bot playing itself,
the cohort the plan prepares, and what the feed says about boards that have no IMP comparison."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import generate, load
from bridge_harness.gen5_arena import run_board
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops.export_gen5 import export
from ops.gen5_runtime import receipt, validate
from ops.prepare_gen7_alpha import load_plan, prepare
from test_gap_forks import GapToy
from test_gen5 import Toy
from test_gen7_launch import gen6_run

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'configs/round7-phase1-selfplay.json'
PHASE1 = ROOT / 'configs/round7-candidate-phase1-nonben.json'
SELF, CROSS = '7s-32~7s-32', '7s-32~6-32'


def manifest(**extra):
    """The parts of a prepared cohort that the board runner, the record check and the exporter read."""
    quiet = dict(probability=0, multiplier=1, max_depth=0, max_forks=0)
    m = dict(identity='testself7', generation=6, variant='6', roster=['7s-32', '6-32'], target=6, seed=11,
             bots={k: dict(id=k, identity=k, artifact_sha256={}) for k in ('7s-32', '6-32', '3')},
             pair_weights={CROSS: 1, SELF: 2}, pair_schedule=[SELF], audit_references={'7s-32': '3'}, common_bidder='6-32',
             audit=quiet, ben_audit=quiet, labels={'7s-32': 'Gen 7 standard (32)', '6-32': 'Gen 6 fast (32)', '3': 'Reference only'},
             order=['7s-32', '6-32'], created_epoch=time.time(), interpretation='Self-play', model_note='Gen 7 standard')
    m.update(extra)
    return m


def stand_in(tmp, name, source, **changes):
    """A plan file in `tmp`: a shipped plan, pointed at a stand-in policy release that names the source run's scorer."""
    old = json.loads((tmp / 'source' / 'manifest.json').read_text())
    release = tmp / 'release'
    if not release.exists():
        release.mkdir()
        (release / 'policy.npz').write_bytes(b'policy')
        (release / 'manifest.json').write_text(json.dumps(dict(scorer_sha256=old['bots']['6-32']['artifact_sha256']['scorer'])))
    plan = json.loads(Path(source).read_text())
    plan['artifacts']['gen7_policy'] = dict(release=str(release), file='policy.npz', restore='restore.py', sha256=sha(release / 'policy.npz'))
    plan.update(changes)
    (tmp / f'{name}.json').write_text(json.dumps(plan))
    return tmp / f'{name}.json'


def played(m, index=0, player=Toy):
    board = next(generate(1, 341 + index))
    with patch('bridge_harness.gen5_arena.auction', lambda b, actors: (b, [])):
        return run_board('.', m, board.to_dict(), index, {k: object() for k in m['bots']}, player_factory=player)


class Gen7SelfplayTests(unittest.TestCase):
    def test_selfplay_is_one_replayable_training_table_with_null_comparison(self):
        m = manifest()
        r = played(m)
        validate(r, m, 0)
        self.assertEqual((r['pair'], r['candidate'], r['opponent']), (SELF, '7s-32', '7s-32'))
        self.assertEqual(set(r['regimes']), {'self'})
        self.assertEqual(len(r['unique_tables']), 1)
        self.assertEqual(r['regimes']['self'], dict(tables=['table-0'], score_difference=None, imps=None))
        self.assertEqual(r['unique_tables']['table-0']['assignments'], ['candidate'] * 4)
        self.assertEqual(r['bidding']['self/0']['bidders'], ['6-32'] * 4)          # the cohort's common bidder, as in a common room
        r['decision_timing'] = {}
        with tempfile.TemporaryDirectory() as tmp:
            root, out = Path(tmp) / 'run', Path(tmp) / 'out'
            root.mkdir()
            path = root / 'episodes/000000.json.gz'
            atomic_json(path, r, compressed=True)
            got = receipt(r, path)
            self.assertIsNone(got['imps'])
            self.assertIsNone(got['own_imps'])
            self.assertEqual((got['root_games'], got['tables']), (1, 1))
            atomic_json(root / 'manifest.json', m)
            atomic_json(root / 'heartbeat.json', dict(epoch=0, workers=0))
            for _ in range(2):                                                      # the second export reads its own cached records
                export(root, out)
                data = json.loads((out / 'arena/data.json').read_text())
                s = data['views']['0']['groups'][SELF]
                self.assertEqual((s['n'], s['mean'], s['total'], s['wins'], s['ties'], s['losses']), (1, None, None, 0, 0, 0))
                self.assertIsNone(data['difference_views']['0']['groups'][SELF]['bidding']['mean'])
            shard = json.loads((out / 'arena/replays/data' / m['identity'] / 'boards-00000.json').read_text())['0']
            self.assertEqual({c['label'] for c in shard['conditions'].values()}, {'Self-play (training only)'})
            self.assertIsNone(shard['differences']['total'])

    def test_a_selfplay_record_with_a_score_or_the_wrong_tables_is_refused(self):
        m = manifest()
        for change in (lambda r: r['regimes']['self'].update(imps=0),                 # a zero would read as a tied match
                       lambda r: r['regimes']['self'].update(score_difference=0),
                       lambda r: r['regimes']['self'].update(tables=['table-0', 'table-0']),
                       lambda r: r['unique_tables']['table-0'].update(assignments=['candidate', 'opponent'] * 2),
                       lambda r: r['bidding']['self/0'].update(bidders=['7s-32'] * 4),
                       lambda r: r['regimes'].update(common=r['regimes']['self'])):
            r = played(m)
            change(r)
            with self.assertRaises(ValueError):
                validate(r, m, 0)
        two = manifest(two_self_rooms=True)                                         # a source run may ask for two self-play rooms
        r = played(two)
        self.assertEqual(len(r['regimes']['self']['tables']), 2)
        validate(r, two, 0)
        with self.assertRaises(ValueError):
            validate(r, m, 0)

    def test_a_selfplay_table_carries_the_cohorts_gap_forks(self):
        """Self-play is collected for training, so the source run's capture settings apply to it as to any table."""
        capture = dict(audit=dict(probability=.5, multiplier=1000, max_depth=1, max_forks=8), gap_fork=dict(per_band=2, bands=[.125, .5], max_cpu_share=1e9))
        m = manifest(**capture)
        r = played(m, player=GapToy)
        validate(r, m, 0)
        table = r['unique_tables']['table-0']
        self.assertEqual((set(r['regimes']), r['regimes']['self']['imps'], len(r['unique_tables'])), ({'self'}, None, 1))
        self.assertTrue(table['gap_forks'])
        self.assertEqual(r['gap_fork_count'], len(table['gap_forks']))
        plain = played(manifest(audit=capture['audit']), player=GapToy)             # without the manifest key the record is as before
        self.assertNotIn('gap_forks', plain['unique_tables']['table-0'])
        self.assertNotIn('gap_fork_count', plain)

    def test_one_cohort_mixes_selfplay_with_the_gen6_comparison(self):
        m = manifest(pair_schedule=[CROSS, SELF, SELF])
        pairs = []
        for index in range(6):
            r = played(m, index)
            validate(r, m, index)
            pairs.append(r['pair'])
            if r['pair'] == CROSS:                                                  # two tables, both conditions, a real IMP result
                self.assertEqual(set(r['regimes']), {'common', 'native'})
                self.assertIsInstance(r['regimes']['common']['imps'], int)
            else:
                self.assertIsNone(r['regimes']['self']['imps'])
        self.assertEqual((pairs.count(CROSS), pairs.count(SELF)), (2, 4))

    def test_the_shipped_plan_is_phase_1_without_the_two_anchors(self):
        plan = load_plan(PLAN)                                                      # open: preparation accepts it
        base = load_plan(PHASE1)
        self.assertEqual(plan['pair_weights'], {CROSS: 1, SELF: 2})
        self.assertEqual(plan['roster'], ['7s-32', '6-32'])
        self.assertEqual(sum(plan['pair_weights'].values()), sum(base['pair_weights'].values()))    # weight for weight
        for key in ('gen7_bots', 'artifacts', 'common_bidder', 'audit_references', 'model_note', 'schema'):
            self.assertEqual(plan[key], base[key], key)                             # so 7s-32 keeps its phase 1 identity
        self.assertNotEqual(plan['campaign'], base['campaign'])
        self.assertIn('04:09 UTC', plan['notes'][0])
        self.assertIn('no IMP comparison', plan['interpretation'])

    def test_prepare_freezes_a_cohort_whose_bot_is_the_phase_1_bot(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            old = gen6_run(tmp / 'source')
            m = prepare(tmp / 'selfplay', tmp / 'source', stand_in(tmp, 'selfplay', PLAN))
            verify_generation(tmp / 'selfplay', m)
            # the stand-in source run has no Gen 5 or Gen 1 bot, so phase 1 is prepared with its Gen 6 pair only
            phase1 = prepare(tmp / 'phase1', tmp / 'source', stand_in(tmp, 'phase1', PHASE1, roster=['7s-32', '6-32'], pair_weights={CROSS: 1}))
            self.assertEqual(m['pair_schedule'], [CROSS, SELF, SELF])
            self.assertEqual(m['bots']['7s-32'], phase1['bots']['7s-32'])           # same bot, same identity, as in phase 1
            self.assertEqual(m['audit_references']['7s-32'], '3')
            self.assertNotEqual(m['identity'], phase1['identity'])
            self.assertFalse(m.get('two_self_rooms'))                               # carried from the source run: one table a deal
            self.assertEqual(m['audit'], old['audit'])

    def test_the_plan_takes_over_the_unplayed_deals_of_a_drained_phase_1_cohort(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gen6_run(tmp / 'source')
            first = prepare(tmp / 'first', tmp / 'source', stand_in(tmp, 'phase1', PHASE1, roster=['7s-32', '6-32'], pair_weights={CROSS: 1}))
            boards = list(load(tmp / 'first' / 'corpus.jsonl'))
            for i in (0, 3):                                                        # two boards were played before the cohort was stopped
                episode = tmp / 'first' / 'episodes' / f'{i:06d}.json.gz'
                episode.write_bytes(b'episode %d' % i)
                atomic_json(tmp / 'first' / 'receipts' / f'{i:06d}.json', dict(index=i, manifest_identity=first['identity'],
                            family=deal_key(boards[i].hands, True), episode_sha256=sha(episode)))
            plan = stand_in(tmp, 'selfplay', PLAN)
            with self.assertRaises(ValueError):                                     # a cohort that is still collecting is not a source
                prepare(tmp / 'next', tmp / 'first', plan)
            for name in ('STOP', 'WATCHDOG_STOP'):
                (tmp / 'first' / name).write_text('drained')
            m = prepare(tmp / 'next', tmp / 'first', plan)
            verify_generation(tmp / 'next', m)
            left = [i for i in range(first['target']) if i not in (0, 3)]
            self.assertEqual((m['target'], m['source_generation'], m['source_completed']), (len(left), first['identity'], 2))
            self.assertEqual(json.loads((tmp / 'next' / 'source-indices.json').read_text()), left)
            self.assertEqual([b.to_dict() for b in load(tmp / 'next' / 'corpus.jsonl')], [boards[i].to_dict() for i in left])
            self.assertEqual(m['bots'], first['bots'])                              # every bot as it was, 7s-32 and its identity included
            self.assertEqual(m['pair_schedule'], [CROSS, SELF, SELF])
            self.assertEqual(sha(tmp / 'next' / 'artifacts/gen7/policy.npz'), sha(tmp / 'first' / 'artifacts/gen7/policy.npz'))
            changed = json.loads(plan.read_text())
            changed['gen7_bots']['7s-32']['gen7']['tree'][0]['trust'] = .25
            (tmp / 'changed.json').write_text(json.dumps(changed))
            with self.assertRaises(ValueError):                                     # the same id with other settings is another bot
                prepare(tmp / 'other', tmp / 'first', tmp / 'changed.json')
            self.assertFalse((tmp / 'other').exists())


if __name__ == '__main__':
    unittest.main()
