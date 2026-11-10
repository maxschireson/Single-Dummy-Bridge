"""Dense ownership model plus a zero-initialized public-evidence correction."""
import numpy as np
from .belief_capacity import INPUTS,Weights,make_model as dense_model

def make_model(parent,width=64,heads=2):
    import tensorflow as tf
    from .auction_belief import CALLS
    if width%heads:raise ValueError('Width must be divisible by heads')
    k=tf.keras;ops=k.ops
    inputs=dict(state=k.Input((64,),name='state'),calls=k.Input((64,),dtype='int32',name='calls'),
        seats=k.Input((64,),dtype='int32',name='seats'),play=k.Input((523,),name='play'))
    original=dense_model((256,128))
    base=k.Model(original.input,original.output,name='dense_base');base.set_weights(Weights(parent).weights)
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
    return k.Model(inputs,base(inputs)+delta,name='residual_attention_belief')
