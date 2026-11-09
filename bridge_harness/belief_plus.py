"""DDS-free shared belief/action-value network; only Observation enters inference.

Training may use full-deal ownership and logged PIMC values as targets. Neither
is accepted by encode_observation or by the deployed player.
"""
import numpy as np
from .auction_belief import CALLS, MAX_CALLS
from .belief_capacity import encode_play, widen
from .core import symbol, score, imps, vulnerable
from .players import Decision

INPUTS = ('state','calls','seats','play','actions')
WIDTHS = (768,384)

def encode_observation(o):
    x,support=encode_play(o)
    known=np.zeros((4,52),np.float32); played=np.zeros_like(known); current=np.zeros_like(known)
    for s,h in enumerate(o.known_hands):
        if h is not None: known[(s-o.controller)%4,list(h)]=1
    for s,c in o.history: played[(s-o.controller)%4,c]=1
    for s,c in o.trick: current[(s-o.controller)%4,c]=1
    local=np.concatenate([known,played,current]).reshape(12,4,13).transpose(1,0,2).reshape(4,156)
    cards=np.full(13,-1,np.int16);cards[:len(o.legal)]=o.legal
    actions=np.zeros((13,171),np.float32)
    led=o.trick[0][1]//13 if o.trick else 4
    for i,c in enumerate(o.legal):
        actions[i]=np.r_[local[c//13],np.eye(13)[c%13],c//13==o.contract.trump,c//13==led]
    return dict(**x,actions=actions),support,cards

def build_model(parent=None,widths=WIDTHS):
    import tensorflow as tf
    k=tf.keras
    state=k.Input((64,),name='state'); calls=k.Input((64,),dtype='int32',name='calls')
    seats=k.Input((64,),dtype='int32',name='seats');play=k.Input((523,),name='play')
    actions=k.Input((13,171),name='actions')
    ce=k.layers.Embedding(len(CALLS)+1,4,name='call_embedding')(calls)
    se=k.layers.Embedding(5,2,name='seat_embedding')(seats)
    z=k.layers.Concatenate()([state,k.layers.Flatten()(ce),k.layers.Flatten()(se),play])
    z=k.layers.Dense(widths[0],activation='relu',name='encoder0')(z)
    z=k.layers.Dropout(.1)(z)
    h=k.layers.Dense(widths[1],activation='relu',name='encoder1')(z)
    ownership=k.layers.Reshape((52,4))(k.layers.Dense(208,name='ownership')(h))
    a=k.layers.Concatenate()([actions,k.layers.RepeatVector(13)(h)])
    a=k.layers.Dense(128,activation='relu',name='action0')(a)
    a=k.layers.Dense(64,activation='relu',name='action1')(a)
    logits=k.layers.Dense(14,name='tricks')(a)
    model=k.Model(dict(state=state,calls=calls,seats=seats,play=play,actions=actions),dict(ownership=ownership,tricks=logits))
    if parent:
        with np.load(parent) as f: w=widen([f['w'+str(i)] for i in range(8)],widths)
        for name,weights in zip(('call_embedding','seat_embedding','encoder0','encoder1','ownership'),([w[0]],[w[1]],w[2:4],w[4:6],w[6:8])):
            model.get_layer(name).set_weights(weights)
    return model

LAYERS=('call_embedding','seat_embedding','encoder0','encoder1','ownership','action0','action1','tricks')
def export(model,path):
    weights={name+'_'+str(i):w for name in LAYERS for i,w in enumerate(model.get_layer(name).get_weights())}
    np.savez_compressed(path,**weights)

def restore(model,path):
    with np.load(path) as z:
        for name in LAYERS: model.get_layer(name).set_weights([z[name+'_'+str(i)] for i in range(len(model.get_layer(name).get_weights()))])

class Weights:
    def __init__(self,path):
        with np.load(path) as z:self.w={k:z[k] for k in z.files}
    def forward(self,x):
        w=self.w;n=len(x['state'])
        def dense(z,name,relu=False):
            y=z@w[name+'_0']+w[name+'_1'];return np.maximum(y,0) if relu else y
        z=np.concatenate([x['state'],w['call_embedding_0'][x['calls']].reshape(n,-1),w['seat_embedding_0'][x['seats']].reshape(n,-1),x['play']],1)
        h=dense(dense(z,'encoder0',True),'encoder1',True)
        a=np.concatenate([x['actions'],np.broadcast_to(h[:,None,:],(n,13,h.shape[1]))],-1)
        a=dense(dense(a,'action0',True),'action1',True)
        return dict(ownership=dense(h,'ownership').reshape(n,52,4),tricks=dense(a,'tricks'))
    def probabilities(self,x,remaining):
        logits=self.forward(x)['tricks'];logits=np.where(np.arange(14)[None,None,:]<=np.asarray(remaining)[:,None,None],logits,-1e9)
        p=np.exp(logits-logits.max(-1,keepdims=True));return p/p.sum(-1,keepdims=True)
    def logits(self,o):
        x,_,_=encode_observation(o)
        y=self.forward({k:v[None] for k,v in x.items()})['ownership'][0]
        return y[:,[(s-o.controller)%4 for s in range(4)]]

class BeliefPlusPlayer:
    def __init__(self,path,late_player=None,dds_remaining=0,objective='tricks'):
        self.net=Weights(path);self.late=late_player;self.cutoff=dds_remaining;self.objective=objective
        self.neural_decisions=self.dds_decisions=0
    def choose(self,o,rng):
        if len(o.legal)==1:return Decision(o.legal[0],dict(forced=True,dds_calls=0))
        remaining=13-len(o.history)//4
        if self.late is not None and remaining<=self.cutoff:
            self.dds_decisions+=1;return self.late.choose(o,rng)
        x,_,cards=encode_observation(o)
        p=self.net.probabilities({k:v[None] for k,v in x.items()},[remaining])[0]
        values=p@np.arange(14)
        if self.objective=='imps':
            declaring=o.actor%2==o.contract.declarer%2
            already=o.declarer_tricks if declaring else len(o.history)//4-o.declarer_tricks
            scores=np.array([(1 if declaring else -1)*score(o.contract,int(np.clip(already+k if declaring else 13-already-k,0,13)),vulnerable(o.vulnerability,o.contract.declarer)) for k in range(14)])
            # Freeze one common reference before utility reranking.
            best=np.flatnonzero(np.isclose(values[:len(o.legal)],values[:len(o.legal)].max(),atol=1e-7,rtol=0))
            reference=p[best].mean(0)
            payoff=np.array([[imps(int(a-b)) for b in scores] for a in scores])
            values=p@payoff@reference
        valid=values[:len(o.legal)];ties=np.flatnonzero(np.isclose(valid,valid.max(),atol=1e-7,rtol=0))
        chosen=int(cards[rng.choice(ties.tolist())]);self.neural_decisions+=1
        return Decision(chosen,dict(selector='belief-plus-no-dds',dds_calls=0,predictions={symbol(int(c)):float(v) for c,v in zip(cards,values) if c>=0}))
    def close(self):
        if self.late is not None:self.late.close()
