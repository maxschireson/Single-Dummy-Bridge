import os,sys,time,subprocess,urllib.request,urllib.error,fcntl,json
from pathlib import Path
root=Path(__file__).resolve().parent
run=root/'runs/gen6-chatgpt-20261111'
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
with (run/'.supervisor.lock').open('a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (run/'STOP').exists():sys.exit('STOP present')
 with (run/'ben-server.log').open('a') as log:
  ben=subprocess.Popen([sys.executable,'src/gameapi.py','--config',str(run/'assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false'],cwd=root.parent/'ben',env=env,stdout=log,stderr=subprocess.STDOUT)
  try:
   for attempt in range(60):
    if ben.poll() is not None:raise RuntimeError('BEN exited: inspect ben-server.log')
    try:
     urllib.request.urlopen('http://127.0.0.1:8087/',timeout=2);break
    except urllib.error.HTTPError:break
    except urllib.error.URLError:time.sleep(1)
   else:raise RuntimeError('BEN readiness timeout')
   print('BEN reachable; starting frozen collector',flush=True)
   while not (run/'STOP').exists():
    result=subprocess.run([sys.executable,'ops/gen5_runtime.py','--run',str(run),'--workers','3'],cwd=root,env=env)
    if list((run/'failures').glob('*.json')) or json.loads((run/'state.json').read_text()).get('complete'):break
    if result.returncode:time.sleep(10)
    else:break
  finally:ben.terminate();ben.wait(timeout=30)
