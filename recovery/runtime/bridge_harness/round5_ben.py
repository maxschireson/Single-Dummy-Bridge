"""Arena-compatible lifecycle and explicit sample-budget metadata for BEN."""
from .players import BenPlayer, Decision


class Round5BenPlayer(BenPlayer):
    def __init__(self,url="http://127.0.0.1:8087",timeout=600,samples=16):
        super().__init__(url,timeout);self.samples=samples

    def request(self,endpoint,params):
        return super().request(endpoint,dict(params,details='true'))

    def choose(self,observation,rng):
        result=super().choose(observation,rng)
        details=dict(result.details,engine='BEN',bidding_mode='neural-only',
            configured_opening_lead_samples=self.samples,configured_play_samples=self.samples)
        samples=details.get('response',{}).get('samples')
        if isinstance(samples,list):details['reported_samples']=len(samples)
        return Decision(result.card,details)

    def close(self):
        # The separately owned HTTP server remains available to the next match.
        pass
