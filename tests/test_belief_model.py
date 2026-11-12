import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
from bridge_harness.belief_model import (build_model, capacity_prior,
    encode_inputs, masked_probabilities, masked_loss, permute_observation)


def example_arrays():
    return dict(known=np.zeros((2, 4, 52)), played=np.zeros((2, 4, 52)),
        visible=np.zeros((2, 4)), voids=np.zeros((2, 4, 4)),
        remaining_counts=np.full((2, 4), 13), context=np.zeros((2, 11), dtype=int),
        history_cards=np.full((2, 52), 52), history_seats=np.full((2, 52), 4),
        owner_support=np.ones((2, 52, 4), dtype=bool))


class BeliefEncoderTests(unittest.TestCase):
    def test_privileged_fields_cannot_change_inputs(self):
        a = example_arrays(); expected = encode_inputs(a)
        a.update(owner_target=np.ones((2, 52)), return_target=np.full(2, 13),
                 episode_id=["future", "secret"], behavior_policy=np.ones((2, 52)))
        actual = encode_inputs(a)
        for key in expected: np.testing.assert_array_equal(expected[key], actual[key])

    def test_ordered_history_retained(self):
        a = example_arrays(); a["history_cards"][0, :2] = [3, 7]
        first = encode_inputs(a)
        a["history_cards"][0, :2] = [7, 3]
        self.assertFalse(np.array_equal(first["cards"], encode_inputs(a)["cards"]))

    def test_support_and_empty_rows(self):
        s = np.array([[[True, False, True, False], [False] * 4]])
        p = masked_probabilities(np.zeros((1, 2, 4)), s)
        np.testing.assert_array_equal(p, [[[.5, 0, .5, 0], [0] * 4]])

    def test_capacity_prior_respects_known_cards(self):
        s = np.array([[[True, False], [True, True], [True, True]]])
        p = capacity_prior(s, np.array([[2., 1.]]))
        np.testing.assert_allclose(p, [[[1, 0], [.5, .5], [.5, .5]]], atol=1e-6)

    def test_symmetry_round_trip_and_label_alignment(self):
        a = example_arrays()
        a["known"][0, 1, 17] = 1
        a["history_cards"][0, :3] = [13, 27, 45]
        a["history_seats"][0, :3] = [1, 2, 3]
        a["context"][0] = [1, 2, 3, 0, 2, 4, 1, 1, 1, 3, 3]
        a["voids"][0, 2, 1] = 1
        a["owner_support"][0, 17] = [False, True, False, False]
        suits = np.array([2, 0, 3, 1])
        b, cards, _ = permute_observation(a, 1, suits)
        new_card = int(np.flatnonzero(cards == 17)[0])
        self.assertEqual(b["known"][0, 2, new_card], 1)
        self.assertTrue(b["owner_support"][0, new_card, 2])
        restored, _, _ = permute_observation(b, 3, np.argsort(suits))
        for key in a: np.testing.assert_array_equal(a[key], restored[key], err_msg=key)


@unittest.skipUnless(importlib.util.find_spec("tensorflow"), "TensorFlow optional")
class BeliefTrainingTests(unittest.TestCase):
    def test_masked_loss_ignores_known_labels_and_gradients(self):
        import tensorflow as tf
        x = tf.Variable(np.zeros((1, 2, 4), np.float32))
        support = np.array([[[True, False, True, False], [True] * 4]])
        mask = np.array([[1., 0.]], np.float32)
        with tf.GradientTape() as tape:
            n, d = masked_loss(x, np.array([[2, 3]]), mask, support)
        g = tape.gradient(n, x).numpy()
        self.assertAlmostEqual(float(n), np.log(2), places=6)
        self.assertEqual(float(d), 1)
        np.testing.assert_array_equal(g[0, 1], np.zeros(4))
        self.assertEqual(g[0, 0, 1], 0)
        other, _ = masked_loss(x, np.array([[2, 0]]), mask, support)
        self.assertEqual(float(n), float(other))

    def test_saved_model_round_trip(self):
        import tensorflow as tf
        x = encode_inputs(example_arrays())
        model = build_model(x["state"].shape[1])
        self.assertTrue(80000 < model.count_params() < 110000)
        before = model(x, training=False).numpy()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "model.keras"; model.save(p)
            after = tf.keras.models.load_model(p)(x, training=False).numpy()
        np.testing.assert_allclose(before, after, atol=1e-7)


if __name__ == "__main__": unittest.main()
