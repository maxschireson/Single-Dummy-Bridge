"""First IMP head: a regularized linear readout of the frozen policy features.

Only audited action contrasts train this head. The auction/history representation
is the final predictive warm-start. More fork data can later justify unfreezing it.
"""
import random
import numpy as np
from .auction_policy import AuctionSelectorWeights,encode_decision
from .policy_selector import MAX_ACTIONS
from .core import symbol
from .players import PIMCPlayer,Decision
from .fork_audit import DraftPlayer


class ForkAdvantageWeights(AuctionSelectorWeights):
    def features(self,x):
        w=self.weights;n=len(x['state'])
        state=np.concatenate([x['state'],w['call_embedding'][x['calls']].reshape(n,-1),
            w['seat_embedding'][x['seats']].reshape(n,-1)],1)
        h=np.maximum(state@w['state_hidden_kernel']+w['state_hidden_bias'],0)
        shared=np.broadcast_to(h[:,None,:],(n,MAX_ACTIONS,h.shape[-1]))
        z=np.concatenate([x['actions'],shared],-1)
        for name in ('action_hidden','action_hidden_2'):
            z=np.maximum(z@w[name+'_kernel']+w[name+'_bias'],0)
        return np.concatenate([z,x['q'][...,None]/13],-1)

    def advantages(self,x,reference):
        values=self.features(x)@self.weights['imp_linear_coef']
        return values-values[np.arange(len(values)),reference,None]


class ForkPolicyPlayer(DraftPlayer):
    def __init__(self,belief,policy,reference,**kwargs):
        super().__init__(belief,policy,reference,**kwargs)
        self.imp=ForkAdvantageWeights(policy)
        if 'imp_linear_coef' not in self.imp.weights:raise ValueError('An audited IMP head is required')

    def choose(self,o,rng):
        result=PIMCPlayer.choose(self,o,rng);d=result.details
        if d.get('forced') or sum(p>0 for p in d['behavior_probabilities'].values())<2:return result
        ranking=random.Random();ranking.setstate(rng.getstate())
        reference,_=self.reference.choose(o,d,ranking)
        x,cards=encode_decision(o,d);valid=x['mask'][0]>0
        ri=int(np.flatnonzero((cards[0]==reference)&valid)[0])
        values=self.imp.advantages(x,np.array([ri]))[0];best=values[valid].max()
        ties=valid&np.isclose(values,best,rtol=0,atol=1e-7)
        probabilities=self.exploration*valid/valid.sum()+(1-self.exploration)*ties/ties.sum()
        ticket=rng.random();ix=int(np.flatnonzero(valid)[-1])
        for j in np.flatnonzero(valid):
            ticket-=probabilities[j]
            if ticket<=0:ix=int(j);break
        chosen=int(cards[0,ix])
        return Decision(chosen,dict(d,selector='direct-auction-audited-imp-head',
            proposal_probabilities=d['behavior_probabilities'],
            behavior_probabilities={symbol(int(cards[0,j])):float(probabilities[j]) for j in np.flatnonzero(valid)},
            selected_probability=float(probabilities[ix]),reference_card=symbol(reference),
            expected_gain_imps=float(values[ix]),prediction_units='matched-fork-imps',exploration=self.exploration,
            selector_predictions={symbol(int(cards[0,j])):float(values[j]) for j in np.flatnonzero(valid)}))
