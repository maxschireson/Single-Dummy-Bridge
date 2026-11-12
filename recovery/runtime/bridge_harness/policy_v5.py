"""Small scalar policy capacity experiments, with NumPy-only inference.

The attention variant adds one cross-attention block from candidate moves and
a value query to visible-card, ordered auction and public-context tokens.
Zero residual readouts preserve the later-v3 function at initialization.
"""
import numpy as np
from .auction_policy import LAYERS, build_model as base_model, restore_parent

MODE = 'baseline'
WIDTH = 64

def build_model(state_size, action_size):
    import tensorflow as tf
    from .auction_belief import CALLS
    k = tf.keras
    if MODE == 'baseline':
        return base_model(state_size, action_size)
    if MODE == 'wide':
        base = base_model(state_size, action_size)
        config = base.get_config()
        for layer in config['layers']:
            layer.pop('build_config', None)
            name = layer['config']['name']
            if name in ('state_hidden', 'action_hidden', 'action_hidden_2'):
                layer['config']['units'] *= 2
        return k.Model.from_config(config)
    if state_size != 737:
        raise ValueError('Attention token offsets require the audited 737-field encoding')
    base = base_model(state_size, action_size)
    state, actions, calls, seats = [base.input[n] for n in ('state','actions','calls','seats')]
    ops = k.ops
    card_fields = ops.transpose(ops.reshape(state[:,:624],(-1,12,52)),(0,2,1))
    card_fields = ops.concatenate([card_fields,state[:,678:730,None]],axis=-1)
    card_tokens = k.layers.Dense(WIDTH,name='att_card')(card_fields)
    card_ids = ops.arange(52)[None,:] + ops.zeros_like(calls[:,:1])
    card_tokens = card_tokens + k.layers.Embedding(52,WIDTH,name='att_card_id')(card_ids)
    positions = ops.arange(64)[None,:] + ops.zeros_like(calls[:,:1])
    auction = (k.layers.Embedding(len(CALLS)+1,WIDTH,name='att_call')(calls)
        + k.layers.Embedding(5,WIDTH,name='att_seat')(seats)
        + k.layers.Embedding(64,WIDTH,name='att_position')(positions))
    context = k.layers.Dense(WIDTH,name='att_context')(ops.concatenate([state[:,624:678],state[:,730:]],axis=-1))
    memory = ops.concatenate([card_tokens,auction,context[:,None,:]],axis=1)
    query = ops.concatenate([context[:,None,:],k.layers.Dense(WIDTH,name='att_move')(actions)],axis=1)
    q = k.layers.Dense(WIDTH,name='att_q')(query)
    key = k.layers.Dense(WIDTH,name='att_k')(memory)
    value = k.layers.Dense(WIDTH,name='att_v')(memory)
    def heads(x, length):
        return ops.transpose(ops.reshape(x,(-1,length,2,WIDTH//2)),(0,2,1,3))
    logits = ops.matmul(heads(q,14),ops.transpose(heads(key,117),(0,1,3,2))) / np.sqrt(WIDTH//2)
    valid = ops.concatenate([ops.ones_like(calls[:,:52]),ops.cast(calls>0,'int32'),ops.ones_like(calls[:,:1])],axis=1)
    logits = logits + (1-ops.cast(valid[:,None,None,:],'float32')) * -1e9
    attended = ops.matmul(ops.softmax(logits,axis=-1),heads(value,117))
    attended = ops.reshape(ops.transpose(attended,(0,2,1,3)),(-1,14,WIDTH))
    h = k.layers.LayerNormalization(epsilon=1e-5,name='att_norm1')(query+k.layers.Dense(WIDTH,name='att_out')(attended))
    ff = k.layers.Dense(2*WIDTH,activation='relu',name='att_ff1')(h)
    h = k.layers.LayerNormalization(epsilon=1e-5,name='att_norm2')(h+k.layers.Dense(WIDTH,name='att_ff2')(ff))
    delta = k.layers.Dense(1,kernel_initializer='zeros',bias_initializer='zeros',name='att_readout')(h)
    return k.Model(base.input,dict(value=base.output['value']+delta[:,0,:],score=base.output['score']+delta[:,1:,:]))

def restore(model,path):
    with np.load(path,allow_pickle=False) as z:
        if 'v5_mode' in z:
            for layer in model.layers:
                ws = layer.get_weights()
                if ws: layer.set_weights([z[f'layer_{layer.name}_{i}'] for i in range(len(ws))])
            return
        if MODE != 'wide':
            restore_parent(model,path)
            return
        # Net2Wider: duplicate units and split outgoing weights, keeping the
        # exact parent function. Zero-sum outgoing perturbations break symmetry.
        rng=np.random.default_rng(20261110)
        def expanded(w, imap, omap):
            count=np.bincount(imap,minlength=w.shape[0])
            out=w[imap][:,omap]/count[imap,None]
            noise=rng.normal(0,1e-3,out.shape).astype(np.float32)
            for i in range(w.shape[0]):
                ix=np.flatnonzero(imap==i)
                noise[ix]-=noise[ix].mean(axis=0)
            return out+noise
        for name in ('call_embedding','seat_embedding'):
            model.get_layer(name).set_weights([z[name]])
        for name in LAYERS:
            w,b=z[name+'_kernel'],z[name+'_bias']
            target=model.get_layer(name).get_weights()[0]
            omap=np.arange(target.shape[1])%len(b)
            if name=='state_hidden': imap=np.arange(len(w))
            elif name=='action_hidden':
                action_size=len(w)-32
                imap=np.r_[np.arange(action_size),action_size+np.arange(64)%32]
            else: imap=np.arange(target.shape[0])%len(w)
            model.get_layer(name).set_weights([expanded(w,imap,omap),b[omap]])

def export(model,path):
    arrays={'v5_mode':np.array(MODE)}
    for layer in model.layers:
        for i,w in enumerate(layer.get_weights()):arrays[f'layer_{layer.name}_{i}']=w
    for name in LAYERS:
        arrays[name+'_kernel'],arrays[name+'_bias']=model.get_layer(name).get_weights()
    for name in ('call_embedding','seat_embedding'):
        arrays[name]=model.get_layer(name).get_weights()[0]
    np.savez_compressed(path,**arrays)

def raw_scores(w,x):
    def dense(x,n,relu=False):
        y=x@w[n+'_kernel']+w[n+'_bias']
        return np.maximum(y,0) if relu else y
    n=len(x['state']);na=x['actions'].shape[1]
    state=np.concatenate([x['state'],w['call_embedding'][x['calls']].reshape(n,-1),w['seat_embedding'][x['seats']].reshape(n,-1)],axis=1)
    h=dense(state,'state_hidden',True)
    val=dense(h,'state_value')
    a=dense(np.concatenate([x['actions'],np.broadcast_to(h[:,None,:],(n,na,h.shape[-1]))],axis=-1),'action_hidden',True)
    a=dense(a,'action_hidden_2',True)
    score=dense(a,'action_score')[...,0]
    if str(w.get('v5_mode','baseline'))!='attention':return val,score
    def d(x,name,relu=False):
        y=x@w['layer_'+name+'_0']+w['layer_'+name+'_1']
        return np.maximum(y,0) if relu else y
    def emb(name,indices):return w['layer_'+name+'_0'][indices]
    def norm(x,name):
        return (x-x.mean(-1,keepdims=True))/np.sqrt(x.var(-1,keepdims=True)+1e-5)*w['layer_'+name+'_0']+w['layer_'+name+'_1']
    s=x['state'];c=x['calls']
    cards=np.concatenate([s[:,:624].reshape(n,12,52).transpose(0,2,1),s[:,678:730,None]],axis=-1)
    cards=d(cards,'att_card')+emb('att_card_id',np.arange(52))[None,:,:]
    auction=emb('att_call',c)+emb('att_seat',x['seats'])+emb('att_position',np.arange(64))[None,:,:]
    context=d(np.concatenate([s[:,624:678],s[:,730:]],axis=-1),'att_context')
    memory=np.concatenate([cards,auction,context[:,None,:]],axis=1)
    query=np.concatenate([context[:,None,:],d(x['actions'],'att_move')],axis=1)
    def heads(x):return x.reshape(n,-1,2,WIDTH//2).transpose(0,2,1,3)
    q,key,value=heads(d(query,'att_q')),heads(d(memory,'att_k')),heads(d(memory,'att_v'))
    logits=q@key.transpose(0,1,3,2)/np.sqrt(WIDTH//2)
    valid=np.concatenate([np.ones((n,52)),c>0,np.ones((n,1))],axis=1)
    logits+=(1-valid[:,None,None,:])*-1e9
    probs=np.exp(logits-logits.max(-1,keepdims=True));probs/=probs.sum(-1,keepdims=True)
    attended=(probs@value).transpose(0,2,1,3).reshape(n,na+1,WIDTH)
    h=norm(query+d(attended,'att_out'),'att_norm1')
    h=norm(h+d(d(h,'att_ff1',True),'att_ff2'),'att_norm2')
    delta=d(h,'att_readout')[...,0]
    return val+delta[:,:1],score+delta[:,1:]

class V5Weights:
    def __init__(self,path):
        with np.load(path,allow_pickle=False) as z:self.weights={k:z[k] for k in z.files}
    def predict(self,x):
        val,score=raw_scores(self.weights,x)
        score-=(score*x['mask']).sum(1,keepdims=True)/x['mask'].sum(1,keepdims=True)
        return x['q']+val+score

def scores(w,x,mode):
    if 'v5_mode' not in w:
        from scripts.policy_choice_data import scores as original
        return original(w,x,mode)
    return x['q']+raw_scores(w,x)[1]
