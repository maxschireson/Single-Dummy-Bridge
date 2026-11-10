"""Arena-compatible lifecycle and explicit sample-budget metadata for BEN."""
from .players import BenPlayer, Decision


class Round5BenPlayer(BenPlayer):
    def choose(self,observation,rng):
        result=super().choose(observation,rng)
        details=dict(result.details,engine='BEN',bidding_mode='neural-only',
            configured_opening_lead_samples=32,configured_play_samples=32)
        return Decision(result.card,details)

    def close(self):
        # The separately owned HTTP server remains available to the next match.
        pass
