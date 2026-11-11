import os,sys,time,subprocess,urllib.request,urllib.error,fcntl,json
from pathlib import Path
root=Path(__file__).resolve().parent;run=root/'runs/gen6-chatgpt-ben-followups-20261111'
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
with (run/'.supervisor.lock').open('a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (run/'STOP').exists():sys.exit('STOP present')
 servers=[]
 try:
  for samples,port in [(16,8087),(32,8088)]:
   log=(run/f'ben-{samples}-server.log').open('a')
   ben=subprocess.Popen([sys.executable,'src/gameapi.py','--config',str(run/f'assets/ben-{samples}.conf'),'--port',str(port),'--host','127.0.0.1','--record','false'],cwd=root.parent/'ben',env=env,stdout=log,stderr=subprocess.STDOUT);servers.append(ben)
   for attempt in range(60):
    if ben.poll() is not None:raise RuntimeError(f'BEN{samples} exited')
    try:urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=2);break
    except urllib.error.HTTPError:break
    except urllib.error.URLError:time.sleep(1)
   else:raise RuntimeError('BEN readiness timeout')
  print('BEN16 and BEN32 reachable; starting collector',flush=True)
  while not (run/'STOP').exists():
   result=subprocess.run([sys.executable,'ops/gen5_runtime.py','--run',str(run),'--workers','3'],cwd=root,env=env)
   if list((run/'failures').glob('*.json')) or json.loads((run/'state.json').read_text()).get('complete'):break
   if result.returncode:time.sleep(10)
   else:break
 finally:
  for ben in servers:
   ben.terminate();ben.wait(timeout=30)
