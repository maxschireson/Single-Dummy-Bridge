"""V2: auction-weighted PIMC plus the outcome-trained near-tie selector.

Evaluation is greedy. Collection can mix epsilon uniform exploration into the
same eligible window, preserving coverage and logging the actual propensities.
"""
import math
import random

from .bidding_sampling import AuctionWeights, WeightedSampler
from .policy_selector import SelectorWeights
from .players import PIMCPlayer, Decision
from .core import symbol


class CombinedPlayer(PIMCPlayer):
    def __init__(self, belief, policy, samples=32, objective='tricks', batch=True,
                 near_tie=.125, exploration=0., strength=1.):
        if objective != 'tricks': raise ValueError('Current selector requires trick-valued PIMC estimates')
        if not math.isfinite(exploration) or not 0 <= exploration <= 1:
            raise ValueError('Exploration must lie in [0,1]')
        self.belief=AuctionWeights(belief);self.selector=SelectorWeights(policy)
        self.exploration=exploration
        super().__init__(samples,objective,batch,near_tie,
                         sampler_factory=lambda o:WeightedSampler(o,self.belief.logits(o),strength))

    def choose(self,o,rng):
        result=super().choose(o,rng);d=result.details
        if d.get('forced') or sum(v>0 for v in d['behavior_probabilities'].values())<2:return result
        # Use a copy of the post-search stream for ranking, leaving one common
        # random variate for the actual behavior draw.
        ranking_rng=random.Random();ranking_rng.setstate(rng.getstate())
        _,values=self.selector.choose(o,d,ranking_rng)
        best=max(values.values());ties={c for c,v in values.items() if abs(v-best)<=1e-7}
        probabilities={c:self.exploration/len(values)+(1-self.exploration)*(c in ties)/len(ties) for c in values}
        ticket=rng.random();chosen=None
        for c,p in sorted(probabilities.items()):
            chosen=c;ticket-=p
            if ticket<=0:break
        details=dict(d,selector='auction-belief-plus-policy-v2',exploration=self.exploration,
                     proposal_probabilities=d['behavior_probabilities'],
                     behavior_probabilities={symbol(c):p for c,p in probabilities.items()},
                     selected_probability=probabilities[chosen],
                     selector_predictions={symbol(c):v for c,v in values.items()},
                     selected_pimc_gap=d['estimates'][symbol(chosen)]['gap_to_best'])
        return Decision(chosen,details)
