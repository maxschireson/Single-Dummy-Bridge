"""Candidate v3 player with auction AND public-play belief conditioning.

This is an explicit new factory. Existing frozen v2 players remain unchanged.
"""
from .combined_player import CombinedPlayer
from .belief_capacity import Weights


class PublicBeliefPlayer(CombinedPlayer):
    def __init__(self, belief, policy, **kwargs):
        super().__init__(belief, policy, **kwargs)
        # The inherited sampler callback reads self.belief at decision time.
        self.belief = Weights(belief)
