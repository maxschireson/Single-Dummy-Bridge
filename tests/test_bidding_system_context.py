import random
import unittest
from bridge_harness.bidding_system_context import (
    encode_system_context, hide_system_context, require_verified_generator)


class SystemContextTests(unittest.TestCase):
    def test_default_is_unknown(self):
        x = encode_system_context(None, 2)
        self.assertEqual(x.ids, (0, 0, 0, 0))
        self.assertFalse(any(x.known))

    def test_relative_seats_and_partial_knowledge(self):
        x = encode_system_context(['gen6', None, 'gen6', 'gen5-ben'], 1)
        self.assertEqual(x.ids, (0, 2, 1, 2))
        self.assertEqual(x.known, (False, True, True, True))

    def test_unknown_hides_all_metadata(self):
        a = encode_system_context(['gen6'] * 4, 0)
        b = encode_system_context(['gen5-ben'] * 4, 0)
        self.assertEqual(hide_system_context(a, 'unknown'), hide_system_context(b, 'unknown'))

    def test_masking_never_fabricates_a_declaration(self):
        x = encode_system_context(['gen6', None, 'gen6', None], 0)
        for seed in range(20):
            y = hide_system_context(x, 'partnership', random.Random(seed))
            self.assertEqual(y.ids[0], y.ids[2])
            self.assertEqual(y.ids[1::2], (0, 0))
            self.assertEqual(y.known, tuple(i != 0 for i in y.ids))

    def test_missing_claude_binding_cannot_label_old_bidder_gen6(self):
        old = '9ee52f3baa79c837001e0cb515c61a9a179cb1bf66cd5503e46331245c014dcc'
        bindings = {'gen5-ben': [old], 'gen6': []}
        require_verified_generator('gen5-ben', old, bindings)
        with self.assertRaises(ValueError):
            require_verified_generator('gen6', old, bindings)

    def test_invalid_labels_and_seats_rejected(self):
        with self.assertRaises(ValueError):encode_system_context(['gen6'] * 3, 0)
        with self.assertRaises(ValueError):encode_system_context(['gen7'] * 4, 0)
        with self.assertRaises(ValueError):encode_system_context(None, 4)


if __name__ == '__main__':unittest.main()
