"""Public auction/history selector: predictive bootstrap, then fork-only advantages."""
from dataclasses import asdict
import numpy as np
from .auction_belief import CALL_ID, CALLS, MAX_CALLS
from .policy_selector import INPUT_KEYS, MAX_ACTIONS, SelectorWeights, encode
from .training import input_tensors
from .core import card, vulnerable

LAYERS=('state_hidden','state_value','action_hidden','action_hidden_2','action_score')


def public_extra(o, samples, near_tie, synthetic=False):
    calls=np.zeros(MAX_CALLS,np.int32);seats=np.full(MAX_CALLS,4,np.int32)
    if len(o.auction)>MAX_CALLS:raise ValueError('Auction too long')
    if not synthetic:
        for i,c in enumerate(o.auction):calls[i]=CALL_ID[c];seats[i]=(o.dealer+i-o.actor)%4
    order=np.zeros(52,np.float32)
    for i,(_,c) in enumerate(o.history):order[c]=(i+1)/52
    extra=np.r_[order,np.eye(3)[o.contract.doubled],
        vulnerable(o.vulnerability,o.actor),vulnerable(o.vulnerability,o.actor^1),
        np.log2(max(samples,1))/6,near_tie].astype(np.float32)
    return calls,seats,extra


def encode_decision(o, details, synthetic=False):
    proposal=details.get('proposal_probabilities',details.get('behavior_probabilities',{}))
    active=[c for c,p in proposal.items() if p>0]
    if not active or not details.get('estimates'):return None
    policy=np.zeros((1,52),np.float32);utility=np.zeros((1,52),np.float32)
    for c in active:policy[0,card(c)]=1/len(active)
    for c,s in details['estimates'].items():utility[0,card(c)]=s['utility']
    a={k:v[None] for k,v in input_tensors(asdict(o)).items() if k in INPUT_KEYS}
    x,cards=encode(a,policy,utility)
    calls,seats,extra=public_extra(o,details.get('samples',32),details.get('near_tie',.125),synthetic)
    x['state']=np.concatenate([x['state'],extra[None]],1)
    x.update(calls=calls[None],seats=seats[None])
    return x,cards


def build_model(state_size,action_size):
    import tensorflow as tf
    k=tf.keras
    state=k.Input((state_size,),name='state');actions=k.Input((MAX_ACTIONS,action_size),name='actions')
    calls=k.Input((MAX_CALLS,),dtype='int32',name='calls');seats=k.Input((MAX_CALLS,),dtype='int32',name='seats')
    c=k.layers.Flatten()(k.layers.Embedding(len(CALLS)+1,4,name='call_embedding')(calls))
    s=k.layers.Flatten()(k.layers.Embedding(5,2,name='seat_embedding')(seats))
    h=k.layers.Dense(32,activation='relu',name='state_hidden')(k.layers.Concatenate()([state,c,s]))
    value=k.layers.Dense(1,name='state_value')(h)
    x=k.layers.Concatenate()([actions,k.layers.RepeatVector(MAX_ACTIONS)(h)])
    x=k.layers.Dense(16,activation='relu',name='action_hidden')(x)
    x=k.layers.Dense(8,activation='relu',name='action_hidden_2')(x)
    score=k.layers.Dense(1,name='action_score')(x)
    return k.Model(dict(state=state,actions=actions,calls=calls,seats=seats),dict(value=value,score=score))


def restore_parent(model,path):
    with np.load(path,allow_pickle=False) as z:
        for name in LAYERS:
            w,b=z[name+'_kernel'],z[name+'_bias']
            if name=='state_hidden':
                target=np.zeros_like(model.get_layer(name).get_weights()[0]);target[:len(w)]=w;w=target
            model.get_layer(name).set_weights([w,b])
        if 'call_embedding' in z:
            for name in ('call_embedding','seat_embedding'):model.get_layer(name).set_weights([z[name]])


def export_weights(model,path):
    weights={}
    for name in LAYERS:weights[name+'_kernel'],weights[name+'_bias']=model.get_layer(name).get_weights()
    for name in ('call_embedding','seat_embedding'):weights[name]=model.get_layer(name).get_weights()[0]
    np.savez_compressed(path,**weights)


class AuctionSelectorWeights(SelectorWeights):
    def predict(self,x):
        w=self.weights
        if 'v5_mode' in w:
            from .policy_v5 import raw_scores
            value, scores = raw_scores(w, x)
            scores -= (scores*x['mask']).sum(1,keepdims=True)/x['mask'].sum(1,keepdims=True)
            return x['q'] + value + scores
        full=dict(x,state=np.concatenate([x['state'],w['call_embedding'][x['calls']].reshape(len(x['state']),-1),
                 w['seat_embedding'][x['seats']].reshape(len(x['state']),-1)],1))
        return super().predict(full)

    def choose(self,o,details,rng):
        x,cards=encode_decision(o,details)
        values=self.predict(x)[0];valid=x['mask'][0]>0;best=values[valid].max()
        ties=np.flatnonzero(valid & np.isclose(values,best,rtol=0,atol=1e-7))
        return int(cards[0,rng.choice(ties.tolist())]),{int(c):float(v) for c,v in zip(cards[0,valid],values[valid])}


from .public_belief_player import PublicBeliefPlayer


class AuctionPolicyPlayer(PublicBeliefPlayer):
    def __init__(self,belief,policy,**kwargs):
        super().__init__(belief,policy,**kwargs)
        self.selector=AuctionSelectorWeights(policy)
