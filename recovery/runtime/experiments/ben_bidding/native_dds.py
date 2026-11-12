"""Experimental scalar adapter for the harness's optimized DDS library.

Keeps BEN's sampled worlds and scalar search objective; one context per worker.
Only complete, unplayed bidding deals are handled here. Other solves delegate.
"""
from concurrent.futures import ThreadPoolExecutor
import ctypes as C
from pathlib import Path
import sys
import threading
import time


class NativeScalarDDS:
    def __init__(self, fallback, workers=2):
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from bridge_harness.dds import DDS, Future
        from bridge_harness.core import parse_hand
        self.DDS,self.Future,self.parse_hand=DDS,Future,parse_hand
        self.fallback=fallback
        self.dds_mode=fallback.dds_mode
        self.pool=ThreadPoolExecutor(max_workers=workers)
        self.local=threading.local()
        self.contexts=[]

    def __getattr__(self,name):return getattr(self.fallback,name)

    def solve(self,strain_i,leader_i,current_trick,hands_pbn,solutions,purpose=''):
        if solutions!=1 or current_trick or purpose not in ('bid','contract'):
            return self.fallback.solve(strain_i,leader_i,current_trick,hands_pbn,solutions,purpose)
        from nn.timing import ModelTimer
        def one(pbn):
            if not hasattr(self.local,'solver'):
                self.local.solver=self.DDS();self.contexts.append(self.local.solver)
            solver=self.local.solver
            seat,body=pbn.split(':',1)
            if seat not in 'NESW' or len(seat)!=1:raise ValueError('Invalid PBN seat')
            parsed=[self.parse_hand(h) for h in body.split()]
            if len(parsed)!=4 or any(len(h)!=13 for h in parsed):raise ValueError('Expected four full hands')
            hands=[None]*4
            for i,h in enumerate(parsed):hands[('NESW'.index(seat)+i)%4]=h
            deal=solver._deal(hands,(strain_i-1)%5,leader_i,())
            future=self.Future()
            status=solver.lib.dds_c_solve_board(solver.ctx,C.byref(deal),-1,1,self.dds_mode,C.byref(future))
            if status!=1:
                msg=C.create_string_buffer(80);solver.lib.dds_c_error_message(status,msg)
                raise RuntimeError(f'DDS {status}: {msg.value.decode()}')
            if future.cards<1:raise ValueError('Missing scalar DDS result')
            return future.score[0],future.score[future.cards-1]
        with ModelTimer.time_call('dds_solve_t01_'+purpose,items=len(hands_pbn)):
            values=list(self.pool.map(one,hands_pbn))
        return dict(max=[v[0] for v in values],min=[v[1] for v in values])

    def close(self):
        self.pool.shutdown(wait=True)
        for solver in self.contexts:solver.close()
