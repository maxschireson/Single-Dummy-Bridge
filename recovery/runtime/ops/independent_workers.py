"""Independent spawned board workers: bounded crash retry, single parent writer."""
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import multiprocessing as mp
import os
import signal
import time
import traceback
from ops.telemetry_supervisor import worker_telemetry
from ops.diagnostic_supervisor import Recorder, memory_snapshot

def execute(conn,run,fn,args,kwargs):
    worker_telemetry(run)
    try:
        value=fn(*args,**kwargs)
        conn.send(('ok',value))
    except BaseException:
        conn.send(('error',traceback.format_exc()))
    finally:conn.close()

class IndependentWorkers:
    run=None
    def __init__(self,max_workers,mp_context=None,**kwargs):
        self.threads=ThreadPoolExecutor(max_workers=max_workers)
        self.context=mp_context or mp.get_context('spawn')
        self.record=Recorder(self.run,'independent-workers')
        self.record.emit('start',workers=max_workers)
    def submit(self,fn,*args,**kwargs):
        return self.threads.submit(self.attempt,fn,args,kwargs)
    def attempt(self,fn,args,kwargs):
        index=args[-1] if args else None
        for retry in range(3):
            receive,send=self.context.Pipe(duplex=False)
            child=self.context.Process(target=execute,args=(send,self.run,fn,args,kwargs))
            child.start();send.close()
            self.record.emit('board-start',index=index,pid=child.pid,attempt=retry+1,resources=memory_snapshot())
            message=None
            try:
                while True:
                    if receive.poll(.25):
                        try:message=receive.recv()
                        except EOFError:pass
                        break
                    if not child.is_alive():break
                child.join()
            finally:receive.close()
            self.record.emit('board-exit',index=index,pid=child.pid,attempt=retry+1,exitcode=child.exitcode,signal=signal.Signals(-child.exitcode).name if child.exitcode<0 else None,resources=memory_snapshot())
            if message is not None:
                if message[0]=='error':raise RuntimeError(message[1])
                if child.exitcode==0:return message[1]
            if child.exitcode not in (-signal.SIGKILL,-signal.SIGTERM):
                raise RuntimeError(f'Unrecognized worker exit {child.exitcode} on board {index}')
            self.record.emit('retry-crashed-board',index=index,attempt=retry+1,note='Healthy peers continue; no completed record is written by workers.')
        raise BrokenProcessPool(f'Board {index}: three independent worker terminations')
    def __enter__(self):return self
    def __exit__(self,*args):self.shutdown()
    def shutdown(self,*args,**kwargs):self.threads.shutdown(wait=True)
