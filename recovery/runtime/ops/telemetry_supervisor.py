"""Operational self-sampling workers and attribution of parent cleanup signals."""
import os
from pathlib import Path
import sys
import threading
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import ops.diagnostic_supervisor as diagnostic

def worker_telemetry(run):
    # Linux task name is diagnostic only; it does not alter allocation limits.
    import ctypes
    ctypes.CDLL(None).prctl(15,b'gen3xyz-worker',0,0,0)
    record=diagnostic.Recorder(run,'worker-self')
    record.emit('worker-start',pid=os.getpid(),ppid=os.getppid(),label='gen3xyz-worker')
    def observe():
        while True:
            record.emit('worker-sample',process=diagnostic.process_snapshot(os.getpid()),resources=diagnostic.memory_snapshot())
            time.sleep(1)
    threading.Thread(target=observe,daemon=True).start()

def main():
    import multiprocessing.process
    run=Path(sys.argv[sys.argv.index('--run')+1]).resolve()
    record=diagnostic.Recorder(run,'signal-sender')
    for method in ('terminate','kill'):
        original=getattr(multiprocessing.process.BaseProcess,method)
        def wrapped(self,_original=original,_method=method):
            record.emit('parent-signal-request',target_pid=self.pid,method=_method)
            return _original(self)
        setattr(multiprocessing.process.BaseProcess,method,wrapped)
    original_init=diagnostic.DiagnosticPool.__init__
    def init(self,*args,**kwargs):
        if kwargs.get('initializer') is not None:raise RuntimeError('Unexpected existing worker initializer')
        kwargs.update(initializer=worker_telemetry,initargs=(str(run),))
        original_init(self,*args,**kwargs)
    diagnostic.DiagnosticPool.__init__=init
    # Make the diagnostic supervisor's collector subprocess use this wrapper too.
    import ops.supervise_mixed as supervisor
    command=supervisor.command
    def launch(args,root,timeout):
        args=[str(ROOT/'ops/telemetry_supervisor.py') if x=='ops/diagnostic_supervisor.py' else x for x in args]
        return command(args,root,timeout)
    supervisor.command=launch
    diagnostic.main()

if __name__=='__main__':main()
