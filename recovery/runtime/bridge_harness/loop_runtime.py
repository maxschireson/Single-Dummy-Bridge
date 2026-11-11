"""Lazily launch one pinned BEN reference, respecting shared experiment locks."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen


@contextmanager
def managed_ben(settings,log,notify=lambda **kw:None):
    if not settings:
        yield;return
    handles=[];process=None
    try:
        # Never terminate/reconfigure another experiment's server.
        for path in sorted(settings.get('resource_locks',[])):
            f=Path(path).open('a');handles.append(f)
            while True:
                try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    notify(status='waiting-for-ben-resource');time.sleep(10)
        port=settings['port']
        with socket.socket() as s:
            s.bind(('127.0.0.1',port))  # fail rather than connect to an unrelated server
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
                 TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
        log=Path(log);log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('a') as stream:
            process=subprocess.Popen([settings['python'],'-u','src/gameapi.py','--config',settings['config'],
                '--host','127.0.0.1','--port',str(port),'--nolimit','true','--record','false'],
                cwd=settings['ben_dir'],env=env,stdout=stream,stderr=subprocess.STDOUT)
            ready=False
            for _ in range(240):
                if process.poll() is not None:raise RuntimeError('BEN startup failed; inspect managed server log')
                try:
                    with urlopen(f'http://127.0.0.1:{port}',timeout=1) as response:response.read()
                    ready=True;break
                except OSError:time.sleep(.5)
            if not ready:raise TimeoutError('BEN startup timed out')
            notify(status='evaluating-ben')
            yield
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        for f in handles:
            fcntl.flock(f,fcntl.LOCK_UN);f.close()
