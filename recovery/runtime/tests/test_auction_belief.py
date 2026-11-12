import unittest
import numpy as np
from bridge_harness.auction_belief import encode_auction, CALL_ID


class AuctionBeliefTests(unittest.TestCase):
    def test_only_own_hand_and_prefix_are_encoded(self):
        own=tuple(range(13));prefix=['1C','PASS','1H']
        x,s=encode_auction(own,2,0,'NS',prefix)
        np.testing.assert_array_equal(x['calls'][:3],[CALL_ID[c] for c in prefix])
        self.assertFalse(x['calls'][3:].any())
        np.testing.assert_array_equal(x['seats'][:3],[2,3,0])
        self.assertTrue(np.all(s[:13]==[True,False,False,False]))
        self.assertTrue(np.all(s[13:]==[False,True,True,True]))

    def test_rotation_equivariance(self):
        a,sa=encode_auction(tuple(range(13)),0,1,'NS',['PASS','1N','PASS'])
        b,sb=encode_auction(tuple(range(13)),1,2,'EW',['PASS','1N','PASS'])
        for k in a:np.testing.assert_array_equal(a[k],b[k])
        np.testing.assert_array_equal(sa,sb)

    def test_no_silent_history_truncation(self):
        with self.assertRaises(ValueError):encode_auction(tuple(range(13)),0,0,'None',['PASS']*65)


if __name__=='__main__':unittest.main()
