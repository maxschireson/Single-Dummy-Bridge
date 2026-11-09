import unittest
import numpy as np
from bridge_harness.belief_consequence import card_information_value


class CardImportanceTests(unittest.TestCase):
    def test_informative_card_is_distinguished_from_irrelevant_card(self):
        # Both halves retain independent balanced owner groups.
        i=np.arange(32);owners=np.zeros((32,52),np.int8)
        owners[:,0]=(i//2)%2;owners[:,1]=(i//4)%2
        u=np.stack([10*(owners[:,0]==0),10*(owners[:,0]==1)],1)
        v=card_information_value(owners,u)
        self.assertAlmostEqual(v[0],5.)
        self.assertAlmostEqual(v[1],0.)
        self.assertTrue(np.all(v[2:]==0))

    def test_common_value_volatility_is_not_card_importance(self):
        rng=np.random.default_rng(123);owners=rng.integers(0,4,(32,52));level=rng.normal(size=32)
        u=np.stack([level,level-1,level-2],1)
        np.testing.assert_array_equal(card_information_value(owners,u),np.zeros(52))

    def test_rare_groups_and_forced_decisions_get_no_bonus(self):
        owners=np.zeros((32,52),np.int8);owners[:4,0]=1
        u=np.stack([owners[:,0]*10,(1-owners[:,0])*10],1)
        self.assertEqual(card_information_value(owners,u)[0],0)
        np.testing.assert_array_equal(card_information_value(owners,u[:,:1]),np.zeros(52))


if __name__=='__main__':unittest.main()
