import os,sys,time,subprocess,urllib.request,urllib.error,fcntl,json
from pathlib import Path
root=Path(__file__).resolve().parent;run=root/'runs/gen6-chatgpt-fast-selfplay-20261111'
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
with (run/'.supervisor.lock').open('a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (run/'STOP').exists():sys.exit('STOP present')
 servers=[]
 reporter=None
 try:
  for samples,port in [(16,8087)]:
   log=(run/f'ben-{samples}-server.log').open('a')
   ben=subprocess.Popen([sys.executable,'src/gameapi.py','--config',str(run/f'assets/ben-{samples}.conf'),'--port',str(port),'--host','127.0.0.1','--record','false'],cwd=root.parent/'ben',env=env,stdout=log,stderr=subprocess.STDOUT);servers.append(ben)
   for attempt in range(60):
    if ben.poll() is not None:raise RuntimeError(f'BEN{samples} exited')
    try:urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=2);break
    except urllib.error.HTTPError:break
    except urllib.error.URLError:time.sleep(1)
   else:raise RuntimeError('BEN readiness timeout')
  print('BEN16 reachable; validating complete BEN games',flush=True)
  from ops.watch_gen6_ben_gate import preflight
  from bridge_harness.selfplay import atomic_json
  manifest=json.loads((run/'manifest.json').read_text())
  report=run/'ben-preflight.json'
  if not report.exists() or json.loads(report.read_text()).get('manifest')!=manifest['identity']:
   checked=preflight(run)
   atomic_json(report,dict(manifest=manifest['identity'],status='passed',matches=checked))
  print('BEN16 complete-game preflight passed; starting collector',flush=True)
  if not (run/'gen7-capture-report.json').exists():
   report_log=(run/'capture-report.log').open('a')
   reporter=subprocess.Popen([sys.executable,'ops/report_gen7_capture.py','--run',str(run),'--before',str(run/'history/ff3eb3270b9b3e21e7e5f99963293c3044239d3245dca25bfc04b3ca0e29a0cb'),'--watch'],cwd=root,env=env,stdout=report_log,stderr=subprocess.STDOUT)
  while not (run/'STOP').exists():
   result=subprocess.run([sys.executable,'ops/gen5_runtime.py','--run',str(run),'--workers','3'],cwd=root,env=env)
   if list((run/'failures').glob('*.json')) or json.loads((run/'state.json').read_text()).get('complete'):break
   if result.returncode:time.sleep(10)
   else:break
 finally:
  if reporter is not None and reporter.poll() is None:
   reporter.terminate();reporter.wait(timeout=30)
  for ben in servers:
   ben.terminate();ben.wait(timeout=30)
