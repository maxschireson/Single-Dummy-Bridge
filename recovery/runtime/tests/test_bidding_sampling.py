from dataclasses import replace
import itertools
import math
import random
import unittest
import numpy as np

from bridge_harness.core import Game
from bridge_harness.corpus import generate
from bridge_harness.sampling import Sampler
from bridge_harness.bidding_sampling import WeightedSampler


def ending(three=False):
    board=next(generate(1,20262211))
    g=Game(board);rng=random.Random(71)
    while len(g.history)<40:g.play(rng.choice(g.observation().legal))
    o=g.observation()
    if three:
        known=list(o.known_hands)
        for s in range(4):
            if s!=o.controller:known[s]=None
        o=replace(o,known_hands=tuple(known))
    return o


def enumerate_marginals(o,logits):
    base=Sampler(o);cards=[c for suit in base.suits for c in suit];worlds=[]
    for assign in itertools.product(range(len(base.unknown)),repeat=len(cards)):
        if tuple(assign.count(j) for j in range(len(base.unknown)))!=base.caps:continue
        if any(not base.allowed[c//13][j] for c,j in zip(cards,assign)):continue
        w=math.exp(sum(logits[c,base.unknown[j]] for c,j in zip(cards,assign)))
        worlds.append((assign,w))
    assert worlds
    p=np.zeros((52,4));z=sum(w for _,w in worlds)
    for s,h in enumerate(o.known_hands):
        if h is not None:p[list(h),s]=1
    for assign,w in worlds:
        for c,j in zip(cards,assign):p[c,base.unknown[j]]+=w/z
    return p,len(worlds)


class WeightedSamplingTests(unittest.TestCase):
    def test_exact_marginals_two_and_three_unknown_hands(self):
        logits=np.random.default_rng(48).normal(0,.5,(52,4))
        for three in (False,True):
            o=ending(three);expected,n=enumerate_marginals(o,logits)
            self.assertGreater(n,1)
            actual=WeightedSampler(o,logits).marginals()
            np.testing.assert_allclose(actual,expected,atol=1e-11)

    def test_zero_weights_equal_uniform_legal_allocations(self):
        o=ending();expected,_=enumerate_marginals(o,np.zeros((52,4)))
        np.testing.assert_allclose(WeightedSampler(o).marginals(),expected,atol=1e-11)

    def test_draws_respect_cards_counts_voids_and_distribution(self):
        o=ending();logits=np.random.default_rng(5).normal(0,.3,(52,4));sampler=WeightedSampler(o,logits)
        expected=sampler.marginals();observed=np.zeros((52,4));rng=random.Random(29)
        base=Sampler(o);remaining=set(range(52))-{c for _,c in o.history}
        for _ in range(6000):
            hands=sampler.draw(rng)
            self.assertEqual(set(c for h in hands for c in h),remaining)
            self.assertEqual(sum(map(len,hands)),len(remaining))
            for seat,hand in enumerate(hands):
                self.assertEqual(len(hand),13-sum(s==seat for s,c in o.history))
                if o.known_hands[seat] is not None:self.assertEqual(hand,o.known_hands[seat])
                else:
                    j=base.unknown.index(seat)
                    self.assertTrue(all(base.allowed[c//13][j] for c in hand))
                observed[list(hand),seat]+=1
        np.testing.assert_allclose(observed/6000,expected,atol=.025)

    def test_nonfinite_scores_rejected(self):
        with self.assertRaises(ValueError):WeightedSampler(ending(),np.full((52,4),np.nan))

    def test_equal_probabilities_score_ties_without_roundoff_bias(self):
        from scripts.evaluate_bidding_sampling import metrics
        p=np.zeros((52,4));p[:,1]=.5;p[:,3]=.5+1e-15
        truth=np.ones(52,int)
        self.assertEqual(metrics(p,truth,list(range(52)))[0],.5)


if __name__=='__main__':unittest.main()
