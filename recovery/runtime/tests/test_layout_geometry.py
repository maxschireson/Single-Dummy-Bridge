import struct
import unittest
import numpy as np
from bridge_harness.layout_geometry import encode


def packed(hands):
    words=[sum(1 << (c%13+2) for c in hand if c//13 == suit) for hand in hands for suit in range(4)]
    return np.frombuffer(struct.pack('<BB3B16H', 1, 2, 255, 255, 255, *words), np.uint8)


class LayoutGeometryTests(unittest.TestCase):
    def test_king_queen_swap_is_closer_than_spot_or_cross_suit_ace(self):
        dk, dq, d5, ca = 37, 36, 29, 51
        rest=[c for c in range(52) if c not in (dk, dq, d5, ca)]
        hands=[[dk]+rest[:12], [dq, d5, ca]+rest[12:22], rest[22:35], rest[35:]]
        variants=[hands]
        for c in (dq, d5, ca):
            h=[list(x) for x in hands]; h[0].remove(dk); h[1].remove(c); h[0].append(c); h[1].append(dk)
            variants.append(h)
        raw=np.stack([packed(h) for h in variants]); fixed=np.tile([0, 0, 1, 1], (4, 1))
        for cosine in (False, True):
            z=encode(raw, fixed, cosine=cosine)
            distance=np.square(z[1:]-z[:1]).sum(1)
            self.assertLess(distance[0], distance[1])
            self.assertLess(distance[0], distance[2])

    def test_same_suit_small_spots_are_interchangeable(self):
        hands=[list(range(13)), list(range(13, 26)), list(range(26, 39)), list(range(39, 52))]
        # Give two hidden hands some spades, then exchange two low spades.
        hands[0].remove(3); hands[1].remove(16); hands[0].append(16); hands[1].append(3)
        h=[list(x) for x in hands]; h[0].remove(2); h[1].remove(3); h[0].append(3); h[1].append(2)
        z=encode(np.stack([packed(hands), packed(h)]), np.tile([0, 0, 1, 1], (2, 1)))
        np.testing.assert_array_equal(z[0], z[1])


if __name__ == '__main__': unittest.main()
