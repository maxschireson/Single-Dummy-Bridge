from copy import deepcopy
import unittest
from unittest.mock import patch

from bridge_harness.corpus import generate
from bridge_harness.players import Decision
from ops.gen4_ablation import play, validate, summary


class Toy:
    def __init__(self, spec, root):
        self.version = spec['id']

    def choose(self, observation, rng):
        cards = sorted(observation.legal)
        return Decision(cards[-1] if self.version in ('4', '4p') else cards[0], {})

    def close(self):
        pass


class ComponentTests(unittest.TestCase):
    def test_matched_rooms_and_tamper_rejection(self):
        manifest = dict(identity='diagnostic', target=1, seed=17,
            bots={v:dict(id=v, identity=v) for v in ('4', '3', '4p', '4b')})
        board = next(generate(1, 727))
        with patch('ops.gen4_ablation.ArenaPlayer', Toy):
            record = play('.', manifest, board.to_dict(), 0)
        validate(record, manifest, board, 0)
        self.assertEqual(record['matches']['4']['imps'], record['matches']['4p']['imps'])
        self.assertEqual(record['matches']['4b']['imps'], 0)
        bad = deepcopy(record)
        bad['matches']['4p']['imps'] += 1
        with self.assertRaises(ValueError):
            validate(bad, manifest, board, 0)
        bad = deepcopy(record)
        bad['matches']['4b']['rooms'][1]['assignments'] = ['4b', '3', '4b', '3']
        with self.assertRaises(ValueError):
            validate(bad, manifest, board, 0)

    def test_family_paired_contrasts(self):
        records = [dict(matches={v:dict(imps=x) for v,x in zip(('4','4p','4b'),row)})
                   for row in [(5, 2, 1), (1, -2, -3)]]
        s = summary(records, dict(identity='test', target=2))
        self.assertEqual(s['tables'], 12)
        self.assertEqual(s['comparisons']['4-4b']['mean'], 4)
        self.assertEqual(s['comparisons']['4-4p']['mean'], 3)
        self.assertEqual(s['comparisons']['interaction']['mean'], 4)
        self.assertIsNotNone(s['comparisons']['interaction']['descriptive_95_ci'])


if __name__ == '__main__':
    unittest.main()
