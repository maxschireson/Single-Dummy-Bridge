"""Outcome probabilities and IMP utility against a frozen self-predicted baseline.

The reference distribution is the network's expected-trick choice at the current
position, frozen before IMP reranking. Product probabilities implement a virtual
comparison table; they do not estimate same-deal outcome correlations.
"""
from functools import lru_cache
import numpy as np
from .auction_policy import build_model, restore_parent, export_weights
from .core import Contract, score, imps

BINS=14
LAYERS=('state_distribution','action_distribution')


def public_context(state):
    state=np.asarray(state)
    if state.shape[-1]!=737:
        raise ValueError('Distribution decoder requires versioned Gen3 state encoding (737 features)')
    # Layout is documented in policy_selector.encode and auction_policy.public_extra.
    ply=np.rint(state[:,674]*52).astype(int)
    already=np.rint(state[:,675]*13).astype(int)
    level=np.rint(state[:,676]*7).astype(int)
    strain=np.argmax(state[:,660:665],axis=1)
    declaring=np.argmax(state[:,656:660],axis=1)%2==0
    doubled=np.argmax(state[:,730:733],axis=1)
    vul=np.where(declaring,state[:,733],state[:,734])>.5
    return dict(ply=ply,already=already,level=level,strain=strain,
                declaring=declaring,doubled=doubled,vulnerable=vul,remaining=13-ply//4)


@lru_cache(None)
def _payoffs(level,strain,doubled,vul,declaring,already):
    contract=Contract(int(level),'SHDCN'[int(strain)],0,int(doubled))
    reference=score(contract,int(level)+6,bool(vul))
    sign=1 if declaring else -1
    output=[]
    for remaining in range(BINS):
        partnership=already+remaining
        tricks=partnership if declaring else 13-partnership
        # Impossible outcomes have zero probability; clamp solely for score API.
        actual=score(contract,int(np.clip(tricks,0,13)),bool(vul))
        output.append(imps(sign*(actual-reference)))
    return np.asarray(output,np.float32)


def imp_payoffs(state):
    c=public_context(state)
    return np.stack([_payoffs(*row) for row in zip(c['level'],c['strain'],c['doubled'],
                     c['vulnerable'],c['declaring'],c['already'])])


@lru_cache(None)
def _pairwise_payoffs(level,strain,doubled,vul,declaring,already):
    contract=Contract(int(level),'SHDCN'[int(strain)],0,int(doubled))
    sign=1 if declaring else -1
    scores=[]
    for remaining in range(BINS):
        partnership=already+remaining
        tricks=partnership if declaring else 13-partnership
        scores.append(sign*score(contract,int(np.clip(tricks,0,13)),bool(vul)))
    return np.asarray([[imps(a-b) for b in scores] for a in scores],np.float32)


def self_reference_values(probabilities,state,mask):
    """One common reference per decision; do not compare each move with itself."""
    expected=(probabilities*np.arange(BINS)).sum(-1)
    eligible=np.where(mask>0,expected,-np.inf)
    best=eligible.max(1,keepdims=True)
    ties=(mask>0)&np.isclose(eligible,best,rtol=0,atol=1e-7)
    reference=(probabilities*ties[...,None]).sum(1)/ties.sum(1,keepdims=True)
    c=public_context(state)
    matrices=np.stack([_pairwise_payoffs(*row) for row in zip(c['level'],c['strain'],c['doubled'],
                         c['vulnerable'],c['declaring'],c['already'])])
    utility=np.einsum('nij,nj->ni',matrices,reference)
    return np.einsum('nak,nk->na',probabilities,utility),reference


def matchpoint_values(probabilities,reference):
    # Within a fixed contract, another partnership trick strictly improves its
    # duplicate score. Use score order, not rounded IMP differences, for ties.
    k=np.arange(BINS)
    reward=(k[:,None]>k[None,:]).astype(float)+.5*(k[:,None]==k[None,:])
    utility=reference@reward.T
    return np.einsum('nak,nk->na',probabilities,utility)


def build_distribution_model(state_size,action_size):
    import tensorflow as tf
    base=build_model(state_size,action_size)
    k=tf.keras
    state_logits=k.layers.Dense(BINS,kernel_initializer='zeros',bias_initializer='zeros',
                               name='state_distribution')(base.get_layer('state_hidden').output)
    action_logits=k.layers.Dense(BINS,kernel_initializer='zeros',bias_initializer='zeros',
                                name='action_distribution')(base.get_layer('action_hidden_2').output)
    return k.Model(base.input,dict(**base.output,state_logits=state_logits,action_logits=action_logits))


def export_distribution(model,path,log_sd):
    export_weights(model,path)
    with np.load(path,allow_pickle=False) as z:w={k:z[k] for k in z.files}
    for layer in LAYERS:w[layer+'_kernel'],w[layer+'_bias']=model.get_layer(layer).get_weights()
    np.savez_compressed(path,**w,outcome_distribution=np.int8(1),distribution_log_sd=np.float32(log_sd))


def restore_distribution(model,path):
    restore_parent(model,path)
    with np.load(path,allow_pickle=False) as z:
        for layer in LAYERS:model.get_layer(layer).set_weights([z[layer+'_kernel'],z[layer+'_bias']])
        return float(z['distribution_log_sd'])


class DistributionWeights:
    prediction_units='expected-imps-vs-frozen-self-distribution'

    def __init__(self,path):
        with np.load(path,allow_pickle=False) as z:self.w={k:z[k] for k in z.files}

    def probabilities(self,x):
        w=self.w;n=len(x['state'])
        state=np.concatenate([x['state'],w['call_embedding'][x['calls']].reshape(n,-1),
                              w['seat_embedding'][x['seats']].reshape(n,-1)],axis=1)
        h=np.maximum(state@w['state_hidden_kernel']+w['state_hidden_bias'],0)
        a=np.concatenate([x['actions'],np.broadcast_to(h[:,None,:],
                            (n,x['actions'].shape[1],h.shape[1]))],axis=-1)
        for layer in ('action_hidden','action_hidden_2'):
            a=np.maximum(a@w[layer+'_kernel']+w[layer+'_bias'],0)
        raw=(a@w['action_score_kernel']+w['action_score_bias'])[...,0]
        raw-=(raw*x['mask']).sum(1,keepdims=True)/x['mask'].sum(1,keepdims=True)
        mean=x['q']+(h@w['state_value_kernel']+w['state_value_bias'])+raw
        sd=np.exp(np.clip(w['distribution_log_sd'],-3,3))
        logits=-.5*((np.arange(BINS)[None,None,:]-mean[...,None])/sd)**2
        logits+=(h@w['state_distribution_kernel']+w['state_distribution_bias'])[:,None,:]
        logits+=a@w['action_distribution_kernel']+w['action_distribution_bias']
        remaining=public_context(x['state'])['remaining']
        logits=np.where(np.arange(BINS)[None,None,:]<=remaining[:,None,None],logits,-1e9)
        p=np.exp(logits-logits.max(-1,keepdims=True));p/=p.sum(-1,keepdims=True)
        return p

    def values(self,x):
        p=self.probabilities(x)
        self_values,reference=self_reference_values(p,x['state'],x['mask'])
        return dict(expected_tricks=(p*np.arange(BINS)).sum(-1),
                    expected_imps=self_values,
                    expected_matchpoints=matchpoint_values(p,reference),
                    contract_imps=(p*imp_payoffs(x['state'])[:,None,:]).sum(-1))

    def predict(self,x):
        return self.values(x)['expected_imps']

    def choose(self,observation,details,rng):
        from .auction_policy import encode_decision
        x,cards=encode_decision(observation,details)
        values=self.predict(x)[0];valid=x['mask'][0]>0
        best=values[valid].max()
        tied=np.flatnonzero(valid&np.isclose(values,best,rtol=0,atol=1e-7))
        index=rng.choice(tied.tolist())
        return int(cards[0,index]),{int(c):float(v) for c,v in zip(cards[0,valid],values[valid])}
