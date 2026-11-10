import unittest
import numpy as np
from bridge_harness.belief_lab import public_support,project,probabilities,swap_loss_numpy

class PublicConstraints(unittest.TestCase):
    def test_exact_likelihood_matches_enumerated_worlds(self):
        from scripts.score_belief_joint import exact_two_seat
        import itertools
        rng=np.random.default_rng(12);z=rng.normal(size=(52,4));y=np.zeros(52,dtype=int);y[:2]=1;y[2:4]=3
        m=np.zeros(52,bool);m[:4]=True;s=np.zeros((52,4),bool);s[:4,1]=True;s[:4,3]=True
        play=np.zeros(523);play[-1]=1;play[484:488]=np.array([0,2,0,2])/13
        scores=[]
        for ix in itertools.combinations(range(4),2):
            owners=np.full(4,3);owners[list(ix)]=1;scores.append(z[np.arange(4),owners].sum())
        expected=(np.logaddexp.reduce(scores)-z[np.arange(4),y[:4]].sum())/4
        self.assertAlmostEqual(exact_two_seat(z,y,m,s,play),expected,places=12)
        shifted=z+rng.normal(size=(52,1))+rng.normal(size=(1,4))
        self.assertAlmostEqual(exact_two_seat(shifted,y,m,s,play),expected,places=12)
    def test_swap_loss_is_invariant_to_sampler_gauge(self):
        rng=np.random.default_rng(3);z=rng.normal(size=(2,52,4));y=rng.integers(0,4,(2,52));m=np.ones((2,52),bool);s=np.ones((2,52,4),bool)
        loss=swap_loss_numpy(z,y,m,s)
        shifted=z+rng.normal(size=(2,52,1))+rng.normal(size=(2,1,4))
        np.testing.assert_allclose(loss,swap_loss_numpy(shifted,y,m,s),atol=1e-10)
        good=np.eye(4)[y]*10
        self.assertTrue(np.all(swap_loss_numpy(good,y,m,s)<loss))
    def test_auction_capacities_without_hidden_labels(self):
        x={'state':np.zeros((1,64),np.float32),'play':np.zeros((1,523),np.float32)}
        x['state'][0,:13]=1
        z=np.random.default_rng(1).normal(size=(1,52,4)).astype(np.float32);z[:,:,1]+=3
        support=public_support(x);q=probabilities(project(z,x,iterations=100),support)
        np.testing.assert_allclose(q.sum(-1),1,atol=1e-6)
        np.testing.assert_allclose(q.sum(1),13,atol=1e-4)
        self.assertTrue(np.all(q[~support]==0))
    def test_public_play_forced_cards_and_empty_seats(self):
        x={'state':np.zeros((1,64),np.float32),'play':np.zeros((1,523),np.float32)}
        p=x['play'];p[0,-1]=1;p[0,484:488]=np.array([1,2,0,1])/13
        p[0,488]=1;p[0,0]=1
        # Forty-eight already played cards; card 0 visible, 1-3 hidden.
        p[0,208+4:208+52]=1
        support=public_support(x);self.assertTrue(support[0,0,0]);self.assertFalse(support[0,4:].any())
        q=probabilities(project(np.zeros((1,52,4),np.float32),x,iterations=100),support)
        np.testing.assert_allclose(q.sum(1),[[1,2,0,1]],atol=1e-5)

if __name__=='__main__':unittest.main()
