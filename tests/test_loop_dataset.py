"""The rollout loop's dataset rows: the gap an 8X rollout decision gives its candidates (scripts/gen7_build_dataset.py
--rollout-gap), and the trainer's scores when some legal cards have no gap."""
import base64
import importlib.util
from pathlib import Path
import unittest

import numpy as np

from bridge_harness.core import card

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load('gen7_build_dataset')


def pack(a, dtype):
    return base64.b64encode(np.ascontiguousarray(a, dtype).tobytes()).decode()


def note(tricks, weights, floor=None, alive=(0, 1, 2), mode='rollout'):
    """A rollout note for three candidates (the second a run of two touching cards) with per-layout results."""
    t = np.array(tricks, np.int8)
    w = np.array(weights, np.float32)
    f = np.zeros(t.shape, np.uint8) if floor is None else np.array(floor, np.uint8)
    played = t >= 0
    roll = [float(w[played[:, j]] @ t[played[:, j], j] / w[played[:, j]].sum()) for j in range(t.shape[1])]
    return dict(mode=mode, cards=['SA', 'HK', 'D2'], runs=[['SA'], ['HK', 'HQ'], ['D2']], roll=roll, alive=list(alive),
                cap=dict(shape=list(t.shape), t=pack(t, np.int8), f=pack(f, np.uint8), w=pack(w, np.float32)))


class RolloutGapTest(unittest.TestCase):
    def test_the_deficit_is_paired_over_the_layouts_both_cards_were_played_on(self):
        # the third candidate was dropped after two layouts, both of them bad for every card
        n = note([[9, 9, 8], [8, 8, 7], [11, 10, -1], [11, 10, -1]], [1, 1, 1, 1], alive=(0, 1))
        got = builder.rollout_gaps(n, True, 10)
        self.assertEqual(sorted(got), sorted(card(x) for x in ('SA', 'HK', 'HQ', 'D2')))
        self.assertAlmostEqual(got[card('SA')], 0.)
        self.assertAlmostEqual(got[card('HK')], .5)
        self.assertAlmostEqual(got[card('HQ')], .5)             # a touching card has its candidate's value
        self.assertAlmostEqual(got[card('D2')], 1.)             # paired: 1.0; the difference of the two means would be 2.25

    def test_without_the_per_layout_results_it_is_the_difference_of_the_means(self):
        n = note([[9, 9, 8], [8, 8, 7], [11, 10, -1], [11, 10, -1]], [1, 1, 1, 1], alive=(0, 1))
        del n['cap']
        got = builder.rollout_gaps(n, True, 10)
        self.assertAlmostEqual(got[card('D2')], 9.75 - 7.5)
        self.assertAlmostEqual(got[card('HK')], .5)

    def test_weights_the_defending_side_and_the_contract_floor(self):
        n = note([[9, 10, 9], [8, 8, 9]], [3, 1])
        declaring = builder.rollout_gaps(n, True, 10)           # candidate means 8.75, 9.5, 9.0: the second is best
        self.assertAlmostEqual(declaring[card('HK')], 0.)
        self.assertAlmostEqual(declaring[card('SA')], .75)
        self.assertAlmostEqual(declaring[card('D2')], .5)
        defending = builder.rollout_gaps(dict(n, roll=[-r for r in n['roll']]), False, 10)      # a defender wants declarer's tricks low
        self.assertAlmostEqual(defending[card('SA')], 0.)
        self.assertAlmostEqual(defending[card('HK')], .75)
        self.assertAlmostEqual(defending[card('D2')], .25)
        floored = note([[9, 10, 9], [8, 8, 9]], [3, 1], floor=[[1, 0, 0], [0, 0, 0]])       # the first card's 9 counts as the contract's 10
        got = builder.rollout_gaps(dict(floored, roll=[9.5, 9.5, 9.0]), True, 10)
        self.assertAlmostEqual(got[card('SA')], 0.)
        self.assertAlmostEqual(got[card('HK')], 0.)
        self.assertAlmostEqual(got[card('D2')], .5)

    def test_the_zero_is_the_best_surviving_candidate_and_values_are_never_negative(self):
        # on the layouts they share the dropped third candidate did better than the reference: it is not the zero, and is 0
        n = note([[9, 8, 10], [9, 9, -1], [9, 9, -1]], [1, 1, 1], alive=(0, 1))
        got = builder.rollout_gaps(n, True, 12)
        self.assertAlmostEqual(got[card('SA')], 0.)
        self.assertAlmostEqual(got[card('HK')], 1 / 3)
        self.assertAlmostEqual(got[card('D2')], 0.)

    def test_other_decisions_have_no_rollout_gap(self):
        n = note([[9, 9, 8]], [1])
        self.assertIsNone(builder.rollout_gaps(None, True, 10))
        self.assertIsNone(builder.rollout_gaps(dict(n, mode='blend'), True, 10))
        self.assertIsNone(builder.rollout_gaps(dict(mode='claim', chosen='SA'), True, 10))
        self.assertIsNone(builder.rollout_gaps(dict(mode='rollout', cards=['SA'], runs=[['SA']], roll=[None], alive=[0]), True, 10))


class UnratedCardsTest(unittest.TestCase):
    def test_scores_count_rated_cards_only(self):
        trainer = load('train_rollout_net')
        legal = np.zeros((3, 52), bool)
        legal[:, :4] = True
        gap = np.zeros((3, 52), np.float16)
        gap[0, :4] = [0., .5, -1., -1.]                 # a rollout row: two candidates rated, two legal cards not
        gap[1, :4] = [1., 0., 2., 3.]                   # a searched row
        gap[2, :4] = [0., .5, -1., -1.]
        logp = np.full((3, 52), -9., np.float32)
        logp[0, 1], logp[1, 1], logp[2, 3] = 0., 0., 0.     # the net's cards: a rated one, the best one, an unrated one
        meta = np.zeros((3, 11), np.int32)
        meta[:, 0] = [0, 1, 0]
        meta[:, 10] = 1
        data = dict(legal=legal, gap=gap, meta=meta, state=np.zeros((3, 52), np.int8), order=np.zeros((3, 52), np.int8),
                    ctx=np.zeros((3, 1), np.float32), auction=np.zeros((3, 1), np.int8), shown=np.zeros((3, 1), np.float32))
        out = trainer.evaluate(lambda b: (logp[:len(b["legal"])], np.where(gap >= 0, gap, 0.).astype(np.float32)[:len(b["legal"])]), data, np.arange(3))["all"]
        self.assertEqual(out['rated_pick'], round(2 / 3, 4))
        self.assertEqual(out['regret'], .25)            # over the two rows whose card was rated: 0.5 and 0
        self.assertEqual(out['in_best'], round(1 / 3, 4))
        self.assertEqual(out['regret_random'], round((.25 + 1.5 + .25) / 3, 4))
        self.assertEqual(out['regret_gap_head'], 0.)    # the gap head's own card is chosen among the rated cards


if __name__ == '__main__':
    unittest.main()
