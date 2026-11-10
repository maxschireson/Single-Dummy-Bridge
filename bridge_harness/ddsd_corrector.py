"""Experimental Gen 6 full-deal DD-to-single-dummy residual critic.

No player receives the true deal. Search supplies sampled remaining hands to
encode(); training supplies the actual remaining hands. Only past actions are
encoded. Values and labels are remaining tricks for the acting partnership.
"""
import numpy as np
from .auction_belief import CALL_ID, MAX_CALLS
from .core import vulnerable

SCHEMA = 'ddsd-full-deal-residual-v1'

def mask_hidden_features(x):
    """Remove unseen ownership, retaining observed hands, history, and DD."""
    x=np.array(x,copy=True)
    flat=x.reshape(-1,x.shape[-1]);owners=flat[:,:208].reshape(-1,4,52)
    public=flat[:,260:312]>0
    declarer=np.argmax(flat[:,476:480],axis=1);dummy=(declarer+2)%4
    visible=np.zeros((len(flat),4),bool);visible[:,0]=True
    visible[np.arange(len(flat)),dummy]=public.any(1)
    owners*=visible[:,:,None]|public[:,None,:]
    return x


def encode(o, hands, action, dd, policy_features=None):
    if action not in o.legal or len(o.auction) > MAX_CALLS:
        raise ValueError('Illegal action or unsupported auction length')
    original = np.zeros((4, 52), np.float32)
    remaining = np.zeros(52, np.float32)
    for seat, hand in enumerate(hands):
        original[(seat-o.controller)%4, list(hand)] = 1
        remaining[list(hand)] = 1
    history = np.zeros(52, np.float32)
    for i, (seat, c) in enumerate(o.history):
        original[(seat-o.controller)%4, c] = 1
        history[c] = (i+1)/52
    if not np.all(original.sum(0) == 1):
        raise ValueError('Hands plus history must partition the deck')
    trick = np.zeros(52, np.float32)
    for i, (_, c) in enumerate(o.trick): trick[c] = (i+1)/4
    chosen = np.zeros(52, np.float32); chosen[action] = 1
    legal = np.zeros(52, np.float32); legal[list(o.legal)] = 1
    declaring = o.actor % 2 == o.contract.declarer % 2
    rem = 13-len(o.history)//4
    already = o.declarer_tricks if declaring else len(o.history)//4-o.declarer_tricks
    seat_features = np.concatenate([np.eye(4)[(s-o.controller)%4] for s in
                                  (o.actor,o.leader,o.contract.declarer,o.dealer)])
    policies = np.zeros(16, np.float32) if policy_features is None else np.asarray(policy_features,np.float32)
    state = np.concatenate([original.ravel(), remaining, history, trick, chosen, legal,
        seat_features, np.eye(5)[o.contract.trump],
        [dd/13,rem/13,already/13,o.declarer_tricks/13,len(o.history)/52,
         o.contract.level/7,o.contract.doubled/2,declaring,
         vulnerable(o.vulnerability,o.controller),vulnerable(o.vulnerability,(o.controller+1)%4),
         len(o.auction)/MAX_CALLS], policies]).astype(np.float32)
    calls = np.zeros(MAX_CALLS,np.uint8)
    for i,c in enumerate(o.auction): calls[i] = CALL_ID[c]
    return state,calls


def make_model(state_size, width=128):
    import torch
    from torch import nn
    class Critic(nn.Module):
        def __init__(self):
            super().__init__()
            self.calls = nn.Embedding(len(CALL_ID)+1,4,padding_idx=0)
            self.net = nn.Sequential(nn.Linear(state_size+MAX_CALLS*4,width),nn.ReLU(),
                nn.Dropout(.1),nn.Linear(width,64),nn.ReLU(),nn.Linear(64,1))
            nn.init.zeros_(self.net[-1].weight); nn.init.zeros_(self.net[-1].bias)
        def forward(self,x,calls):
            return self.net(torch.cat([x,self.calls(calls).flatten(1)],1)).squeeze(1)
    return Critic()


class Corrector:
    """Inference-only adapter. Lambda zero always preserves exact DD scores."""
    def __init__(self,path):
        import torch
        checkpoint=torch.load(path,map_location='cpu',weights_only=False)
        self.model=make_model(checkpoint['state_size'],checkpoint['width'])
        self.model.load_state_dict(checkpoint['model']);self.model.eval()
        self.mask_hidden=checkpoint.get('mask_hidden',False)
    def predict(self,x,calls):
        import torch
        if self.mask_hidden:x=mask_hidden_features(x)
        with torch.no_grad():
            return self.model(torch.as_tensor(np.asarray(x),dtype=torch.float32),
                torch.as_tensor(np.asarray(calls),dtype=torch.long)).numpy()

