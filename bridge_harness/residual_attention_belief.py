"""Dense ownership model plus a zero-initialized public-evidence correction."""
import numpy as np
from .belief_capacity import INPUTS,Weights as DenseWeights,make_model as dense_model

def make_model(parent,width=64,heads=2):
    import tensorflow as tf
    from .auction_belief import CALLS
    if width%heads:raise ValueError('Width must be divisible by heads')
    k=tf.keras;ops=k.ops
    inputs=dict(state=k.Input((64,),name='state'),calls=k.Input((64,),dtype='int32',name='calls'),
        seats=k.Input((64,),dtype='int32',name='seats'),play=k.Input((523,),name='play'))
    original=dense_model((256,128))
    base=k.Model(original.input,original.output,name='dense_base');base.set_weights(DenseWeights(parent).weights)
    state,calls,seats,play=[inputs[n] for n in INPUTS]
    # Four known owners, four played owners, per-card play order and own hand.
    fields=ops.concatenate([ops.transpose(ops.reshape(play[:,:416],(-1,8,52)),(0,2,1)),
        play[:,416:468,None],state[:,:52,None]],axis=-1)
    ids=ops.arange(52)[None,:]+ops.zeros_like(calls[:,:1])
    cards=k.layers.Dense(width,name='att_card')(fields)+k.layers.Embedding(52,width,name='att_card_id')(ids)
    pos=ops.arange(64)[None,:]+ops.zeros_like(calls[:,:1])
    auction=(k.layers.Embedding(len(CALLS)+1,width,name='att_call')(calls)
        +k.layers.Embedding(5,width,name='att_seat')(seats)
        +k.layers.Embedding(64,width,name='att_position')(pos))
    context=k.layers.Dense(width,name='att_context')(ops.concatenate([state[:,52:],play[:,468:]],axis=-1))
    memory=ops.concatenate([cards,auction,context[:,None,:]],axis=1)
    q=k.layers.Dense(width,name='att_q')(cards)
    keys=k.layers.Dense(width,name='att_k')(memory);values=k.layers.Dense(width,name='att_v')(memory)
    def split(x,length):return ops.transpose(ops.reshape(x,(-1,length,heads,width//heads)),(0,2,1,3))
    logits=ops.matmul(split(q,52),ops.transpose(split(keys,117),(0,1,3,2)))/np.sqrt(width//heads)
    valid=ops.concatenate([ops.ones_like(calls[:,:52]),ops.cast(calls>0,'int32'),ops.ones_like(calls[:,:1])],axis=1)
    logits+=(1-ops.cast(valid[:,None,None,:],'float32'))*-1e9
    attended=ops.matmul(ops.softmax(logits,axis=-1),split(values,117))
    attended=ops.reshape(ops.transpose(attended,(0,2,1,3)),(-1,52,width))
    h=k.layers.LayerNormalization(epsilon=1e-5,name='att_norm1')(cards+k.layers.Dense(width,name='att_out')(attended))
    ff=k.layers.Dense(2*width,activation='relu',name='att_ff1')(h)
    h=k.layers.LayerNormalization(epsilon=1e-5,name='att_norm2')(h+k.layers.Dense(width,name='att_ff2')(ff))
    delta=k.layers.Dense(4,kernel_initializer='zeros',bias_initializer='zeros',name='att_readout')(h)
    model=k.Model(inputs,base(inputs)+delta,name='residual_attention_belief')
    model.attention_width=width;model.attention_heads=heads
    return model

def build(parent,mode):
    if mode=='attention':return make_model(parent)
    if mode!='dense':raise ValueError('Unknown architecture')
    model=dense_model((256,128));model.set_weights(DenseWeights(parent).weights);return model

def dropout_generator(model):
    layers=[]
    def visit(layer):
        if getattr(layer,'seed_generator',None) is not None:layers.append(layer.seed_generator)
        for child in getattr(layer,'layers',[]):visit(child)
    visit(model)
    if len(layers)!=1:raise ValueError('Expected one dense dropout generator')
    return layers[0]

def export(model,path,mode):
    from pathlib import Path
    path=Path(path);tmp=path.with_suffix('.tmp')
    if mode=='dense':arrays={f'w{i}':w for i,w in enumerate(model.get_weights())}
    else:
        arrays=dict(schema=np.array('residual-attention-belief-v1'),width=np.array(model.attention_width),heads=np.array(model.attention_heads))
        arrays.update({f'base_w{i}':w for i,w in enumerate(model.get_layer('dense_base').get_weights())})
        for layer in model.layers:
            if layer.name.startswith('att_'):
                arrays.update({f'{layer.name}_{i}':w for i,w in enumerate(layer.get_weights())})
    with tmp.open('wb') as f:np.savez_compressed(f,**arrays)
    tmp.replace(path)

class Weights:
    """Portable inference; hybrid files intentionally reject the legacy loader."""
    def __init__(self,path):
        with np.load(path,allow_pickle=False) as z:self.arrays={k:z[k] for k in z.files}
        self.hybrid='schema' in self.arrays
        if self.hybrid and str(self.arrays['schema'])!='residual-attention-belief-v1':raise ValueError('Unknown schema')
        self.weights=[self.arrays[('base_w' if self.hybrid else 'w')+str(i)] for i in range(8)]

    def predict(self,x):
        z=DenseWeights.predict(self,x)
        if not self.hybrid:return z
        w=self.arrays;width=int(w['width']);heads=int(w['heads']);n=len(x['state'])
        def dense(v,name,relu=False):
            y=v@w[name+'_0']+w[name+'_1'];return np.maximum(y,0) if relu else y
        def norm(v,name):
            return (v-v.mean(-1,keepdims=True))/np.sqrt(v.var(-1,keepdims=True)+1e-5)*w[name+'_0']+w[name+'_1']
        def split(v):return v.reshape(n,-1,heads,width//heads).transpose(0,2,1,3)
        state,play,calls,seats=x['state'],x['play'],x['calls'],x['seats']
        fields=np.concatenate([play[:,:416].reshape(n,8,52).transpose(0,2,1),play[:,416:468,None],state[:,:52,None]],-1)
        cards=dense(fields,'att_card')+w['att_card_id_0'][np.arange(52)][None]
        auction=w['att_call_0'][calls]+w['att_seat_0'][seats]+w['att_position_0'][np.arange(64)][None]
        context=dense(np.concatenate([state[:,52:],play[:,468:]],-1),'att_context')
        memory=np.concatenate([cards,auction,context[:,None]],1)
        q,keys,values=split(dense(cards,'att_q')),split(dense(memory,'att_k')),split(dense(memory,'att_v'))
        logits=q@keys.transpose(0,1,3,2)/np.sqrt(width//heads)
        valid=np.concatenate([np.ones((n,52),bool),calls>0,np.ones((n,1),bool)],1)
        logits=np.where(valid[:,None,None,:],logits,-1e9)
        p=np.exp(logits-logits.max(-1,keepdims=True));p/=p.sum(-1,keepdims=True)
        attended=(p@values).transpose(0,2,1,3).reshape(n,52,width)
        h=norm(cards+dense(attended,'att_out'),'att_norm1')
        h=norm(h+dense(dense(h,'att_ff1',True),'att_ff2'),'att_norm2')
        return z+dense(h,'att_readout')

    def logits(self,observation):
        from .belief_capacity import encode_play
        x,_=encode_play(observation);relative=self.predict({k:v[None] for k,v in x.items()})[0]
        return relative[:,[(s-observation.controller)%4 for s in range(4)]]
