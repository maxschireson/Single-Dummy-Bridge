"""Experimental ownership constraints and portable model recipes."""
import json
from pathlib import Path
import numpy as np
from .belief_capacity import Weights as DenseWeights, make_model, widen
from .residual_attention_belief import Weights as ResidualWeights, make_model as attention_model, export

def public_support(x):
    p=x['play'];n=len(p);known=p[:,:208].reshape(n,4,52);played=p[:,208:416].reshape(n,4,52)
    void=p[:,468:484].reshape(n,4,4);remaining=p[:,484:488]*13;visible=p[:,488:492]
    support=(visible[:,None,:]==0)&(void.transpose(0,2,1)[:,np.arange(52)//13,:]==0)&(remaining[:,None,:]>0)
    support=np.where(known.any(1)[:,:,None],known.transpose(0,2,1)>0,support)
    support &= ~played.any(1)[:,:,None]
    auction=np.ones((n,52,4),bool);auction[:,:,0]=False
    auction=np.where(x['state'][:,:52,None]>0,np.array([True,False,False,False]),auction)
    return np.where(p[:,-1,None,None]>0,support,auction)

def probabilities(z,support):
    z=np.where(support,z,-1e9);p=np.exp(z-z.max(-1,keepdims=True))*support
    return p/np.maximum(p.sum(-1,keepdims=True),1e-30)

def swap_loss_numpy(z,y,mask,support):
    """Conditional log loss for the true world against each legal two-card swap.

    Targets are used only for loss computation. Card and seat additive offsets
    cancel, exactly as they do in the capacity-conditioned sampling distribution.
    """
    n,c,_=z.shape;rows=np.arange(n)[:,None];cards=np.arange(c)[None,:]
    truth=z[rows,cards,y]
    zi_b=z[np.arange(n)[:,None,None],np.arange(c)[None,:,None],y[:,None,:]]
    allowed=support[np.arange(n)[:,None,None],np.arange(c)[None,:,None],y[:,None,:]]
    valid=mask[:,:,None]&mask[:,None,:]&(y[:,:,None]!=y[:,None,:])&allowed&allowed.transpose(0,2,1)
    margin=zi_b+zi_b.transpose(0,2,1)-truth[:,:,None]-truth[:,None,:]
    return (np.logaddexp(0,margin)*valid).sum((1,2))/np.maximum(valid.sum((1,2)),1)*mask.sum(1)

def project(z,x,support=None,iterations=12,temperature=1.):
    """Iterative row/seat balancing using only public remaining-card counts."""
    if support is None:support=public_support(x)
    p=probabilities(z/temperature,support);uncertain=support.sum(-1)>1
    forced=(support&(support.sum(-1)==1)[:,:,None]).sum(1)
    remaining=np.where(x['play'][:,-1,None]>0,x['play'][:,484:488]*13,13.)
    capacity=np.maximum(remaining-forced,0);q=p*uncertain[:,:,None]
    for _ in range(iterations):
        q*=capacity[:,None,:]/np.maximum(q.sum(1,keepdims=True),1e-20)
        q/=np.maximum(q.sum(-1,keepdims=True),1e-20)
    p=np.where(uncertain[:,:,None],q,p)
    return np.log(np.maximum(p,1e-30))

class Weights:
    def __init__(self,path):
        path=Path(path)
        self.recipe=json.loads(path.read_text()) if path.suffix=='.json' else {'model':str(path.resolve())}
        mp=Path(self.recipe['model']);mp=mp if mp.is_absolute() else path.parent/mp
        self.base=ResidualWeights(mp)
    def predict(self,x):
        z=self.base.predict(x);temp=self.recipe.get('temperature',1.)
        if self.recipe.get('projection',False):return project(z,x,temperature=temp)
        return z/temp
    def logits(self,observation):
        from .belief_capacity import encode_play
        x,_=encode_play(observation);relative=self.predict({k:v[None] for k,v in x.items()})[0]
        return relative[:,[(s-observation.controller)%4 for s in range(4)]]

def initialize(cfg,out):
    """All experiment initializations are saved before fitting."""
    import tensorflow as tf
    out=Path(out);parent=out/'initial.npz'
    widths=tuple(cfg.get('widths',[256,128]));dense=make_model(widths)
    if cfg.get('parent'):
        w=DenseWeights(cfg['parent']).weights
        dense.set_weights(widen(w,widths,seed=cfg['seed']))
    if not parent.exists():export(dense,parent,'dense')
    if cfg['mode']=='attention':
        if widths!=(256,128):raise ValueError('Attention base widths')
        model=attention_model(parent,width=cfg.get('attention_width',64),heads=2)
        base=model.get_layer('dense_base');base.trainable=not cfg.get('freeze_base',False)
    else:model=dense;base=model
    for layer in base.layers:
        if isinstance(layer,tf.keras.layers.Dropout):layer.rate=cfg.get('dropout',.15)
    return model
