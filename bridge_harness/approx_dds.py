"""Approximate DD values, explicitly separate from exact DDS and its cache."""
import ctypes as C
import numpy as np
from .dds import DDS,Deal
from .core import winner

def rollout_guess(hands,trump,leader,trick):
    """Cheap full-information greedy rollout, used only as an unproved estimate.

    Averaging two deterministic lead rules reduces arbitrary suit-order effects.
    This is a baseline leaf evaluator, not a learned approximate DDS network.
    """
    actor=(leader+len(trick))%4;values=[]
    for variant in range(2):
        hs=[set(h) for h in hands];tr=list(trick);lead=leader;won=0
        while any(hs):
            s=(lead+len(tr))%4;legal=sorted(hs[s])
            if tr:
                follow=[c for c in legal if c//13==tr[0][1]//13]
                if follow:legal=follow
                best=winner(tr,trump)
                wins=[c for c in legal if winner(tr+[(s,c)],trump)==s]
                choice=min(wins,key=lambda c:(c//13==trump,c%13)) if wins and best%2!=s%2 else min(legal,key=lambda c:(c//13==trump,c%13))
            else:
                # Cash top cards; second rollout favors the longest suit.
                choice=max(legal,key=lambda c:(c%13+(2*sum(x//13==c//13 for x in hs[s]) if variant else 0),c//13!=trump))
            hs[s].remove(choice);tr.append((s,choice))
            if len(tr)==4:
                lead=winner(tr,trump);won+=lead%2==actor%2;tr=[]
        values.append(won)
    return float(np.mean(values))

class ApproxDDS(DDS):
    def __init__(self,path=None):
        super().__init__(path=path,cache_path='')
        self.lib.bridge_dds_approx_value.argtypes=[C.c_void_p,C.POINTER(Deal),C.c_ulonglong,C.c_double,C.POINTER(C.c_double),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_ulonglong),C.POINTER(C.c_int)]
        self.lib.bridge_dds_approx_value.restype=C.c_int
    def value(self,hands,trump,leader,trick,budget=1000,guess=None):
        if not any(hands):return dict(estimate=0.,lower=0,upper=0,nodes=0,exact=True)
        if guess is None:guess=-1. # Native rollout avoids Python work per search leaf.
        d=self._deal(hands,trump,leader,trick);v=C.c_double();lo=C.c_int();hi=C.c_int();nodes=C.c_ulonglong();exact=C.c_int()
        status=self.lib.bridge_dds_approx_value(self.ctx,C.byref(d),budget,guess,C.byref(v),C.byref(lo),C.byref(hi),C.byref(nodes),C.byref(exact))
        if status!=1:raise RuntimeError(f'Approx DDS status {status}')
        return dict(estimate=v.value,lower=lo.value,upper=hi.value,nodes=nodes.value,exact=bool(exact.value))
    def all_moves(self,hands,trump,leader,trick,budget=1000,guesses=None):
        actor=(leader+len(trick))%4;legal=sorted(hands[actor]);out={}
        if trick:
            follow=[c for c in legal if c//13==trick[0][1]//13]
            if follow:legal=follow
        if guesses is not None and any(c not in guesses or not np.isfinite(guesses[c]) for c in legal):
            raise ValueError('A finite actor-partnership guess is required for every legal move')
        live=set(c for hand in hands for c in hand)|set(c for _,c in trick)
        representative={};previous=None
        for c in sorted(live):
            if c in legal and previous is not None and previous//13==c//13 and previous in legal:representative[c]=representative[previous]
            else:representative[c]=c
            previous=c
        for c in legal:
            if representative[c]!=c:
                out[c]=dict(out[representative[c]],nodes=0);continue
            hs=[list(h) for h in hands];hs[actor].remove(c);tr=list(trick)+[(actor,c)];lead=leader;reward=0
            if len(tr)==4:
                lead=winner(tr,trump);reward=int(lead%2==actor%2);tr=[]
            child=(lead+len(tr))%4;remaining=(sum(map(len,hs))+len(tr))//4
            guess=None
            if guesses is not None:
                guess=float(guesses[c])-reward
                if child%2!=actor%2:guess=remaining-guess
                guess=float(np.clip(guess,0,remaining))
            r=self.value(hs,trump,lead,tr,budget,guess)
            if child%2!=actor%2:r=dict(r,estimate=remaining-r['estimate'],lower=remaining-r['upper'],upper=remaining-r['lower'])
            out[c]=dict(r,estimate=reward+r['estimate'],lower=reward+r['lower'],upper=reward+r['upper'])
        return out

from .players import PIMCPlayer
class ApproximatePIMCPlayer(PIMCPlayer):
    """Keep 32 belief samples; replace only early per-world DD evaluation."""
    def __init__(self,belief,budget=1000,exact_remaining=7,samples=32):
        from .bidding_sampling import WeightedSampler
        super().__init__(samples=samples,objective='tricks',batch=True,near_tie=0.,sampler_factory=lambda o:WeightedSampler(o,belief.logits(o),1.))
        self.approx=ApproxDDS();self.budget=budget;self.exact_remaining=exact_remaining
    def choose(self,o,rng):
        from .players import Decision
        if len(o.legal)==1 or 13-len(o.history)//4<=self.exact_remaining:return super().choose(o,rng)
        sampler=self.sampler_factory(o);totals={c:0. for c in o.legal};nodes=certified=0
        for i in range(self.samples):
            world=sampler.draw(rng);values=self.approx.all_moves(world,o.contract.trump,o.leader,o.trick,self.budget)
            for c,z in values.items():totals[c]+=z['estimate'];nodes+=z['nodes'];certified+=z['exact']
        best=max(totals.values());chosen=rng.choice([c for c,v in totals.items() if abs(v-best)<1e-8])
        return Decision(chosen,dict(selector='approximate-dds-pimc',samples=self.samples,approx_nodes=nodes,certified_moves=certified,dds_calls=0))
    def close(self):
        super().close()
        if hasattr(self,'approx'):self.approx.close()
