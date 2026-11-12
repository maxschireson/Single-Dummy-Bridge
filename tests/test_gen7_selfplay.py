"""Gen 7 self-play: the plan Max asked for on 12 November 2026, the runtime's check of a bot playing itself,
the cohort the plan prepares, and what the feed says about boards that have no IMP comparison."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from bridge_harness.corpus import generate
from bridge_harness.gen5_arena import run_board
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops.export_gen5 import export
from ops.gen5_runtime import receipt, validate
from ops.prepare_gen7_alpha import load_plan, prepare
from test_gen5 import Toy
from test_gen7_launch import gen6_run

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'configs/round7-phase1-selfplay.json'
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


def played(m, index=0):
    board = next(generate(1, 341 + index))
    with patch('bridge_harness.gen5_arena.auction', lambda b, actors: (b, [])):
        return run_board('.', m, board.to_dict(), index, {k: object() for k in m['bots']}, player_factory=Toy)


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
        base = load_plan(ROOT / 'configs/round7-candidate-phase1-nonben.json')
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
            release = tmp / 'release'
            release.mkdir()
            (release / 'policy.npz').write_bytes(b'policy')
            (release / 'manifest.json').write_text(json.dumps(dict(scorer_sha256=old['bots']['6-32']['artifact_sha256']['scorer'])))
            entry = dict(release=str(release), file='policy.npz', restore='restore.py', sha256=sha(release / 'policy.npz'))
            made = {}
            for name, source in (('selfplay', PLAN), ('phase1', ROOT / 'configs/round7-candidate-phase1-nonben.json')):
                plan = json.loads(source.read_text())
                plan['artifacts']['gen7_policy'] = entry
                if name == 'phase1':                                                # the stand-in source run has no Gen 5 or Gen 1 bot
                    plan.update(roster=['7s-32', '6-32'], pair_weights={CROSS: 1})
                (tmp / f'{name}.json').write_text(json.dumps(plan))
                made[name] = prepare(tmp / name, tmp / 'source', tmp / f'{name}.json')
                verify_generation(tmp / name, made[name])
            m = made['selfplay']
            self.assertEqual(m['pair_schedule'], [CROSS, SELF, SELF])
            self.assertEqual(m['bots']['7s-32'], made['phase1']['bots']['7s-32'])       # same bot, same identity, as in phase 1
            self.assertEqual(m['audit_references']['7s-32'], '3')
            self.assertNotEqual(m['identity'], made['phase1']['identity'])
            self.assertFalse(m.get('two_self_rooms'))                               # carried from the source run: one table a deal
            self.assertEqual(m['audit'], old['audit'])


if __name__ == '__main__':
    unittest.main()
