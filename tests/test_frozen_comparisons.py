import random
from dataclasses import replace
import unittest
from unittest.mock import patch
import numpy as np
from bridge_harness.core import Game, card
from bridge_harness.corpus import generate
from bridge_harness.players import PIMCPlayer
from bridge_harness.policy_selector import SelectorPlayer
from scripts.evaluate_frozen_comparisons import CoupledBeliefPlayer, BlindPlayer, SEED
from bridge_harness.sampling import Sampler
from bridge_harness.runner import decision_rng

class Belief:
    def logits(self,o):return np.arange(208).reshape(52,4)%7/3.

class Policy:
    def __init__(self,path):pass
    def choose(self,o,details,rng):
        values={card(c):float(card(c)) for c,p in details['behavior_probabilities'].items() if p>0}
        return max(values,key=values.get),values

class DDS:
    def close(self):pass
    def solve_batch(self,worlds,trump,leader,trick,fixed_seats):
        self.worlds=worlds;legal=worlds[0][leader];best=sorted(legal)[:2]
        # Two exact best moves, with every other move 1/32 trick below them.
        return [({c:4+int(i==0 and c in best) for c in legal},1) for i in range(len(worlds))]

class ComparisonTests(unittest.TestCase):
    @patch('bridge_harness.dds.DDS',DDS)
    def test_blind_sampler_matches_uniform_and_ignores_auction(self):
        game=Game(next(generate(1,728391)));o=game.observation()
        player=BlindPlayer(game.board.id)
        try:
            d=player.choose(o,random.Random(8));worlds=list(player.worlds)
            sampler=Sampler(o);rng=decision_rng(SEED,game.board.id,'belief32-shared',o)
            self.assertEqual(worlds,[sampler.draw(rng) for _ in range(32)])
            changed=replace(o,auction=('7N','PASS','PASS','PASS'))
            other=player.choose(changed,random.Random(78))
            self.assertEqual(worlds,player.worlds)
            self.assertEqual(d,other)
            self.assertEqual(d.details['selected_pimc_gap'],0)
            self.assertIsNone(d.details['belief_sha256'])
            self.assertNotIn('selector',d.details)
        finally:player.close()

    @patch('bridge_harness.dds.DDS',DDS)
    @patch('bridge_harness.policy_selector.SelectorWeights',Policy)
    def test_zero_band_keeps_only_exact_best_with_identical_belief_worlds(self):
        game=Game(next(generate(1,728391)));o=game.observation();belief=Belief()
        candidate=CoupledBeliefPlayer(SelectorPlayer('unused'),belief,game.board.id,SEED)
        strict=CoupledBeliefPlayer(PIMCPlayer(32,'tricks',True,0),belief,game.board.id,SEED)
        try:
            a=candidate.choose(o,random.Random(1));b=strict.choose(o,random.Random(9))
            self.assertEqual(a.details['sampled_worlds_sha256'],b.details['sampled_worlds_sha256'])
            self.assertEqual(a.details['estimates'],b.details['estimates'])
            self.assertEqual(candidate.worlds,strict.worlds)
            self.assertEqual(len(strict.worlds),32)
            self.assertEqual(b.details['selected_pimc_gap'],0)
            support={card(c):p for c,p in b.details['behavior_probabilities'].items() if p>0}
            self.assertEqual(set(support),set(sorted(o.legal)[:2]))
            self.assertEqual(set(support.values()),{.5})
            self.assertEqual(a.card,max(o.legal))
            self.assertEqual(a.details['selected_pimc_gap'],1/32)
            self.assertTrue(a.details['selector'])
        finally:candidate.close();strict.close()

if __name__=='__main__':unittest.main()
