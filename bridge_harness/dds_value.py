"""Compact full-information DD value model. Public-information beliefs stay separate."""
import struct
import numpy as np
from .dds import DDS
from .dds_cache import position_key

INPUT_SIZE = 373

def corrected_mean(predictions, exact_prefix):
    """Random-prefix exact residual correction; coefficient fixed to one.

    The prefix must be sampled under the same belief distribution as all rows,
    rather than chosen according to confidence or the predicted value.
    """
    p=np.asarray(predictions);y=np.asarray(exact_prefix)
    if p.ndim!=2 or y.ndim!=2 or not 0<len(y)<=len(p) or p.shape[1]!=y.shape[1]:
        raise ValueError('Expected aligned nonempty (world, action) arrays')
    return p.mean(0)+(y-p[:len(y)]).mean(0)

def pack(hands, trump, leader, trick):
    return np.frombuffer(position_key(DDS._deal(hands, trump, leader, trick)), np.uint8).copy()

def unpack(raw):
    trump, leader, *z = struct.unpack('<BB3B16H', bytes(raw))
    hands = [[13*s+r-2 for s in range(4) for r in range(2,15)
              if z[3+4*h+s] & (1 << r)] for h in range(4)]
    trick = [((leader+i)%4, c) for i,c in enumerate(z[:3]) if c != 255]
    return hands, trump, leader, trick

def encode(raw, suit_order=None):
    """Actor-relative hands, ordered current trick, trump, remaining count.

    suit_order maps new suit indices to old ones, for exact symmetry augmentation.
    The returned card order maps network output columns back to original cards.
    """
    raw = np.asarray(raw, np.uint8).reshape(-1,37); n = len(raw)
    words = raw[:,5:].copy().view('<u2').reshape(n,4,4)
    hands = ((words[:,:,:,None] >> np.arange(2,15)) & 1).astype(np.float32)
    partial = raw[:,2:5]; nt = (partial != 255).sum(1)
    actor = (raw[:,1].astype(int)+nt)%4
    hands = hands[np.arange(n)[:,None], (actor[:,None]+np.arange(4))%4]
    order = np.arange(4) if suit_order is None else np.asarray(suit_order)
    cards = (13*order[:,None]+np.arange(13)).ravel()
    inverse = np.argsort(order)
    hands = hands[:,:,order,:]
    current = np.zeros((n,3,53),np.float32)
    mapped = np.full((n,3),52)
    ix = partial != 255
    mapped[ix] = 13*inverse[partial[ix]//13]+partial[ix]%13
    current[np.arange(n)[:,None],np.arange(3),mapped] = 1
    strain = raw[:,0].astype(int).copy()
    strain[strain<4] = inverse[strain[strain<4]]
    remaining = (hands.sum((1,2,3))+nt)/4
    x = np.concatenate([hands.reshape(n,208),current.reshape(n,159),
                        np.eye(5,dtype=np.float32)[strain],remaining[:,None]/13],1)
    return x.astype(np.float32), remaining.astype(np.int32), cards

def build_model():
    import tensorflow as tf
    k = tf.keras
    x = k.Input((INPUT_SIZE,)); h = k.layers.Dense(512,activation='relu')(x)
    h = k.layers.Dense(256,activation='relu')(h)
    return k.Model(x,k.layers.Reshape((52,14))(k.layers.Dense(728)(h)))

def export(model,path):
    np.savez_compressed(path,**{'w'+str(i):w for i,w in enumerate(model.get_weights())})

class Weights:
    def __init__(self,path):
        with np.load(path) as z:self.w = [z['w'+str(i)] for i in range(6)]
    def logits(self,x):
        w = self.w
        h = np.maximum(x@w[0]+w[1],0)
        h = np.maximum(h@w[2]+w[3],0)
        return (h@w[4]+w[5]).reshape(-1,52,14)
    def predict(self,raw):
        x,remaining,_ = encode(raw); logits = self.logits(x)
        logits = np.where(np.arange(14)[None,None,:]<=remaining[:,None,None],logits,-1e9)
        p = np.exp(logits-logits.max(-1,keepdims=True)); p /= p.sum(-1,keepdims=True)
        mean = p@np.arange(14); var = p@(np.arange(14)**2)-mean**2
        return mean, np.maximum(var,0), p
