"""Single-owner fast-only collector supervision; publication uses the connector."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.selfplay import atomic_json
from bridge_harness.mixed_arena import verify_generation

def supervise(run):
    run=Path(run).resolve();attempts={}
    with (run/'.watchdog.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        m=json.loads((run/'manifest.json').read_text())
        assert m['pair_weights']=={'6-32~6-32':1}
        while not (run/'WATCHDOG_STOP').exists():
            if (run/'STOP').exists():return
            verify_generation(run,m)
            s=json.loads((run/'state.json').read_text());n=s['completed']
            if n>=m['target']:return
            if list((run/'failures').glob('*.json')):raise RuntimeError('Preserved failure requires inspection')
            if shutil.disk_usage(run).free<3*1024**3:raise RuntimeError('Disk space guard')
            with (run/'.writer.lock').open('a+') as writer:
                fcntl.flock(writer,fcntl.LOCK_EX|fcntl.LOCK_NB)
            attempts[n]=attempts.get(n,0)+1
            if attempts[n]>3:raise RuntimeError('Repeated failure to advance')
            with (run/'collector.log').open('a') as log:
                child=subprocess.Popen([sys.executable,'-u','ops/gen5_runtime.py','--run',str(run),'--workers','3'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3'))
                atomic_json(run/'process.json',dict(pid=child.pid,epoch=time.time()))
                rotating=False
                while child.poll() is None:
                    cache=run/'dds-cache.sqlite'
                    if not (run/'STOP').exists() and cache.exists() and cache.stat().st_size>2*1024**3:
                        (run/'STOP').write_text('CLOUD_CACHE_ROTATION\n');rotating=True
                    if shutil.disk_usage(run).free<3*1024**3 and not (run/'STOP').exists():
                        (run/'STOP').write_text('Disk space guard\n')
                    if (run/'WATCHDOG_STOP').exists() and not (run/'STOP').exists():(run/'STOP').write_text('Watchdog stopped\n')
                    atomic_json(run/'watchdog-status.json',dict(epoch=time.time(),pid=child.pid,status='draining' if (run/'STOP').exists() else 'running',publication='connector scheduled separately'))
                    time.sleep(10)
                if rotating and (run/'STOP').read_text()=='CLOUD_CACHE_ROTATION\n':
                    with (run/'.writer.lock').open('a+') as writer:
                        fcntl.flock(writer,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        for p in run.glob('dds-cache.sqlite*'):p.unlink()
                        (run/'STOP').unlink()
                if child.returncode and list((run/'failures').glob('*.json')):raise RuntimeError('Collector failed; records preserved')

if __name__=='__main__':supervise(sys.argv[1])
