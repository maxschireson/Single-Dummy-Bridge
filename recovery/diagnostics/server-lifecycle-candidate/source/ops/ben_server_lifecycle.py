"""One BEN server per paired board; no request or board retries."""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from ops.diagnostic_supervisor import Recorder, memory_snapshot

class BenServer:
    def __init__(self, run, command=None, cwd=None, url='http://127.0.0.1:8087/', timeout=60):
        self.run=Path(run); self.recorder=Recorder(run,'ben-server'); self.url=url; self.timeout=timeout
        self.command=command or [sys.executable,'src/gameapi.py','--config',str(self.run/'assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false']
        self.cwd=cwd or Path(__file__).resolve().parents[2]/'ben'
        self.process=None; self.log=None
    def start(self):
        self.log=(self.run/'diagnostics'/f'ben-server-{time.time_ns()}.log').open('w')
        try:
            self.process=subprocess.Popen(self.command,cwd=self.cwd,stdout=self.log,stderr=subprocess.STDOUT,env=dict(os.environ))
            self.recorder.emit('server-start',pid=self.process.pid,resources=memory_snapshot())
            deadline=time.monotonic()+self.timeout
            while time.monotonic()<deadline:
                if self.process.poll() is not None: raise RuntimeError(f'BEN startup exit {self.process.returncode}')
                try: urllib.request.urlopen(self.url,timeout=2).close(); return self
                except urllib.error.HTTPError: return self
                except (urllib.error.URLError,TimeoutError): time.sleep(.1)
            raise TimeoutError('BEN server readiness timeout')
        except BaseException:
            self.stop(); raise
    def stop(self):
        unexpected=None
        if self.process is not None:
            unexpected=self.process.poll()
            if unexpected is None:
                self.process.terminate()
                try:self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            self.recorder.emit('server-exit',pid=self.process.pid,exitcode=self.process.returncode,unexpected_exitcode=unexpected,intentional_stop=unexpected is None,resources=memory_snapshot())
            self.process=None
        if self.log is not None:self.log.close();self.log=None
        return unexpected
