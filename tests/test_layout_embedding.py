import unittest
import struct
import numpy as np
from bridge_harness.layout_embedding import reduce_layouts, centered, encode


class LayoutEmbeddingTests(unittest.TestCase):
    def test_weighted_reduction_keeps_mass_and_distinct_layouts(self):
        z=np.array([[0.],[0.],[1.],[2.],[2.]])
        ix,w=reduce_layouts(z,np.array([.1,.2,.15,.25,.3]),3)
        self.assertEqual(len(set(ix)),3)
        self.assertAlmostEqual(w.sum(),1.)
        self.assertTrue((w>=0).all())
        self.assertAlmostEqual(float(w@z[ix,0]),1.25)

    def test_full_budget_is_exact_even_with_identical_embeddings(self):
        z=np.zeros((5,16));w=np.array([1,2,3,4,5.]);y=np.array([7,1,8,2,9.])
        ix,m=reduce_layouts(z,w,5)
        self.assertEqual(set(ix),set(range(5)))
        self.assertAlmostEqual(float(m@y[ix]),float(w@y/w.sum()))

    def test_random_within_clusters_is_unbiased_for_unseen_values(self):
        z=np.arange(12.)[:,None];w=np.arange(1,13.);y=np.sin(z[:,0]*2.3)
        rng=np.random.default_rng(88);means=[]
        for _ in range(4000):
            ix,m=reduce_layouts(z,w,3,rng);means.append(m@y[ix])
        expected=w@y/w.sum();se=np.std(means,ddof=1)/np.sqrt(len(means))
        self.assertLess(abs(np.mean(means)-expected),5*se)

    def test_centering_ignores_uniform_trick_offset(self):
        a=np.array([[9.,8.,-1.],[10.,9.,-1.]])
        c=centered(a,a>=0)
        np.testing.assert_array_equal(c[0],c[1])

    def test_suit_augmentation_matches_explicit_relabeling(self):
        rng=np.random.default_rng(71);deal=rng.permutation(52).reshape(4,13)
        hands=np.array([[sum(1 << (int(c)%13+2) for c in h if c//13==s)
                         for s in range(4)] for h in deal],np.uint16)
        raw=np.frombuffer(struct.pack('<BB3B16H',1,2,255,255,255,*hands.ravel()),np.uint8)[None,:]
        fixed=np.array([[0,0,1,1]]);legal=np.zeros((1,52),bool);legal[0,deal[2]]=True
        order=np.array([2,0,3,1]);inverse=np.argsort(order)
        relabeled=np.frombuffer(struct.pack('<BB3B16H',int(inverse[1]),2,255,255,255,
                                           *hands[:,order].ravel()),np.uint8)[None,:]
        card_order=(13*order[:,None]+np.arange(13)).ravel()
        augmented,_=encode(raw,fixed,legal,order)
        explicit,_=encode(relabeled,fixed,legal[:,card_order])
        self.assertEqual(augmented.shape,(1,445))
        np.testing.assert_array_equal(augmented,explicit)


if __name__=='__main__':unittest.main()
