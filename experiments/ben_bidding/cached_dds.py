"""Request-local memoization of exact scalar DDS queries in BEN bidding.

BEN's search can evaluate the same world/strain/leader under several candidate
contracts. This proxy preserves every requested value and its original order.
No approximation, sample reduction or cross-request state is introduced.
"""
import hashlib
import json


class ScalarDDSCache:
    def __init__(self, solver, enabled=True):
        self.solver=solver
        self.enabled=enabled
        self.cache={}
        self.seen=set()
        self.requested=0
        self.unique=0
        self.solved=0
        self.value_digest=hashlib.sha256()

    def __getattr__(self,name):
        return getattr(self.solver,name)

    def solve(self,strain_i,leader_i,current_trick,hands_pbn,solutions,purpose=''):
        # Only scalar bidding/contract evaluations are eligible. Card-play
        # all-move results have a different representation and pass through.
        if solutions!=1 or purpose not in ('bid','contract'):
            return self.solver.solve(strain_i,leader_i,current_trick,hands_pbn,solutions,purpose)
        prefix=(strain_i,leader_i,tuple(current_trick),solutions,self.solver.dds_mode)
        keys=[prefix+(pbn,) for pbn in hands_pbn]
        self.requested+=len(keys)
        self.seen.update(keys);self.unique=len(self.seen)
        if not self.enabled:
            self.solved+=len(keys)
            result=self.solver.solve(strain_i,leader_i,current_trick,hands_pbn,solutions,purpose)
        else:
            missing={key:pbn for key,pbn in zip(keys,hands_pbn) if key not in self.cache}
            if missing:
                self.solved+=len(missing)
                answer=self.solver.solve(strain_i,leader_i,current_trick,list(missing.values()),solutions,purpose)
                if answer is None:return None
                if set(answer)!= {'max','min'} or any(len(v)!=len(missing) for v in answer.values()):
                    raise ValueError('Unexpected scalar DDS response; refusing to cache it')
                for i,key in enumerate(missing):self.cache[key]=(answer['max'][i],answer['min'][i])
            result={label:[self.cache[key][i] for key in keys] for i,label in enumerate(('max','min'))}
        self.value_digest.update(json.dumps([keys,result],sort_keys=True).encode())
        return result

    def stats(self):
        return dict(requested=self.requested,unique=self.unique,solved=self.solved,
                    reused=self.requested-self.solved,value_sha256=self.value_digest.hexdigest())
