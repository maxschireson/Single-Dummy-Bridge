import random
import unittest
from unittest.mock import patch
import numpy as np

from bridge_harness.core import Game, card
from bridge_harness.corpus import generate
from scripts.evaluate_policy_over_belief import make_players, CANDIDATE, BASELINE


class FakeBelief:
    def __init__(self, path): pass
    def logits(self, o):
        # Nonuniform ownership, requiring the real weighted sampler to run.
        return np.arange(208).reshape(52, 4) % 7 / 3.


class FakePolicy:
    def __init__(self, path): pass
    def choose(self, o, details, rng):
        values = {card(c): float(card(c)) for c,p in details['behavior_probabilities'].items() if p > 0}
        return max(values, key=values.get), values


class FakeDDS:
    def __init__(self): self.worlds = None
    def close(self): pass
    def solve_batch(self, worlds, trump, leader, trick, fixed_seats):
        self.worlds = worlds
        actor = (leader+len(trick)) % 4
        hand = worlds[0][actor]
        follow = [c for c in hand if trick and c//13 == trick[0][1]//13]
        legal = follow or hand
        return [({c: 3 for c in legal}, 1) for _ in worlds]


class PolicyOverBeliefTests(unittest.TestCase):
    @patch('scripts.evaluate_policy_over_belief.AuctionWeights', FakeBelief)
    @patch('bridge_harness.policy_selector.SelectorWeights', FakePolicy)
    @patch('bridge_harness.dds.DDS', FakeDDS)
    def test_same_belief_worlds_and_estimates_before_policy_selection(self):
        game = Game(next(generate(1, 638214)))
        players = make_players('unused', 'unused', game.board.id, 20261502)
        try:
            for ply in range(16):
                o = game.observation()
                a = players[CANDIDATE].choose(o, random.Random(11))
                b = players[BASELINE].choose(o, random.Random(99))
                if len(o.legal) > 1:
                    self.assertEqual(a.details['samples'], 32)
                    self.assertEqual(a.details['sampled_worlds_sha256'], b.details['sampled_worlds_sha256'])
                    self.assertEqual(a.details['estimates'], b.details['estimates'])
                    self.assertEqual(players[CANDIDATE].worlds, players[BASELINE].worlds)
                    self.assertEqual(a.card, max(o.legal))
                    self.assertNotIn('selector', b.details)
                    self.assertIn('selector', a.details)
                    for world in players[CANDIDATE].worlds:
                        for seat, hand in enumerate(o.known_hands):
                            if hand is not None: self.assertEqual(world[seat], hand)
                else:
                    self.assertEqual(a.details['samples'], 0)
                    self.assertEqual(players[CANDIDATE].worlds, [])
                game.play(b.card)
        finally:
            for p in players.values(): p.close()


if __name__ == '__main__': unittest.main()
