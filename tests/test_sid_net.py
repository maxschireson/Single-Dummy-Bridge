"""The line-finder student's heads and labels (experiments/sid_loop/SPEC.md, Part B)."""
import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np

from bridge_harness import gen7_net

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('train_rollout_net', ROOT / 'scripts' / 'train_rollout_net.py')
trainer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trainer)
sys.path.insert(0, str(ROOT / 'experiments' / 'sid_loop'))


def batch(n, rng):
    b = dict(state=rng.integers(0, gen7_net.N_STATE, (n, 52)).astype(np.int8), order=rng.integers(0, 53, (n, 52)).astype(np.int8),
             legal=np.zeros((n, 52), bool), ctx=rng.random((n, gen7_net.N_CTX)).astype(np.float32),
             auction=np.zeros((n, gen7_net.N_AUCTION), np.int8), shown=rng.random((n, gen7_net.N_SHOWN)).astype(np.float32))
    b['legal'][:, :13] = True
    return b


class StudentHeadsTest(unittest.TestCase):
    def test_a_net_without_the_label_weights_behaves_as_before(self):
        plain = trainer.init(1, np.random.default_rng(0), 64)
        student = trainer.init(1, np.random.default_rng(0), 64, sid=True)
        self.assertEqual(sorted(set(student) - set(plain)), ['bd1s', 'bk14', 'wd1s', 'wk14'])
        for k in plain:                                      # the new weights are drawn last: the others are the same draw
            np.testing.assert_array_equal(plain[k], student[k])
        b = batch(6, np.random.default_rng(1))
        old = gen7_net.forward(dict(plain, kind=np.array(1)), b)
        new = gen7_net.forward(dict(student, kind=np.array(1)), b)
        self.assertEqual(sorted(old), ['gap', 'owner', 'policy', 'tricks'])
        for k in old:
            np.testing.assert_array_equal(old[k], new[k])
        for k in gen7_net.SID_HEADS:
            self.assertEqual(new[k].shape, (6, 52, 3))
        self.assertEqual(new['tricks14'].shape, (6, 14))

    def test_each_head_reads_its_own_weights(self):
        student = trainer.init(1, np.random.default_rng(0), 64, sid=True)
        student['wd1s'] = np.zeros_like(student['wd1s'])
        b = batch(3, np.random.default_rng(2))
        for i, k in enumerate(gen7_net.SID_HEADS):
            for t in range(3):
                bias = np.zeros(13 * len(gen7_net.SID_HEADS) * 3, np.float32).reshape(13, len(gen7_net.SID_HEADS), 3)
                bias[4, i, t] = 2.                           # the six of every suit, this head, this target
                out = gen7_net.forward(dict(student, bd1s=bias.reshape(-1), kind=np.array(1)), b)
                for other in gen7_net.SID_HEADS:
                    want = np.zeros((3, 52, 3), np.float32)
                    if other == k:
                        want[:, [4, 17, 30, 43], t] = 2.     # cards are 13 * suit + rank: rank index 4 is the six
                    np.testing.assert_allclose(out[other], want if other == k else 0., atol=1e-6)

    def test_labels_follow_the_legal_cards_in_rising_order(self):
        legal = np.zeros((3, 52), bool)
        legal[0, [5, 20, 40]] = True
        legal[1, [0, 1, 2, 3, 4, 5, 6, 7, 8]] = True         # nine legal cards: the ninth has no slot
        legal[2, [51]] = True
        sid = np.full((3, len(trainer.SID_KINDS), trainer.SID_SLOTS, 3), -1, np.int8)
        sid[0, 0, :3] = [[1, 0, 0], [1, 1, 0], [0, 0, 0]]    # guar of the three legal cards
        sid[0, 2, 1] = [1, 1, 1]                             # cert of the second legal card
        sid[1, 1, 7] = [0, 1, 0]                             # single of the eighth
        out = trainer.sid_labels(sid.reshape(3, -1), legal)
        self.assertEqual(out['sid_guar'][0, 5].tolist(), [1, 0, 0])
        self.assertEqual(out['sid_guar'][0, 20].tolist(), [1, 1, 0])
        self.assertEqual(out['sid_guar'][0, 40].tolist(), [0, 0, 0])
        self.assertEqual(out['sid_cert'][0, 20].tolist(), [1, 1, 1])
        self.assertEqual(out['sid_cert'][0, 5].tolist(), [-1, -1, -1])
        self.assertEqual(out['sid_single'][1, 7].tolist(), [0, 1, 0])
        self.assertTrue((out['sid_single'][1, 8] == -1).all())
        self.assertTrue((out['sid_guar'][0][~legal[0]] == -1).all())
        self.assertTrue((out['sid_guar'][2] == -1).all())


class RunsTest(unittest.TestCase):
    def test_touching_cards_are_one_run_unless_a_live_card_lies_between(self):
        import sidlabel
        hand = sidlabel.mask([0, 1, 3, 20])
        self.assertEqual(sidlabel.runs([0, 1, 3, 20], hand, hand | sidlabel.mask([2])), [[0, 1], [3], [20]])
        self.assertEqual(sidlabel.runs([0, 1, 3, 20], hand, hand), [[0, 1, 3], [20]])     # the card between is gone
        hand = sidlabel.mask([12, 13])                                                        # the ace of one suit, the two of the next
        self.assertEqual(sidlabel.runs([12, 13], hand, hand), [[12], [13]])


if __name__ == '__main__':
    unittest.main()
