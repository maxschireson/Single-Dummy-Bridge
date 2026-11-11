import os,sys,json,time,resource,multiprocessing as mp,fcntl
from pathlib import Path
BASE=Path('/workspace/scratch/c7932514d17d/gen6-fast-selfplay');sys.path.insert(0,str(BASE))
RUN=BASE/'runs/gen6-chatgpt-fast-selfplay-20261111'
from ops.gen5_runtime import initialize_worker,play
from ops.diagnostic_supervisor import DiagnosticPool,memory_snapshot
from bridge_harness.corpus import load
from bridge_harness.mixed_arena import verify_generation
from concurrent.futures import wait,FIRST_COMPLETED

def probe(root,m,board,index):
 t=time.time();r=play(root,m,board,index)
 return dict(index=index,pid=os.getpid(),seconds=time.time()-t,maxrss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,status='replay_validated',tables=len(r['unique_tables']))

def main():
 locks=[]
 for n in ['.supervisor.lock','.writer.lock']:
  f=open(RUN/n,'a+');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(f)
 assert not (RUN/'STOP').exists() and not (RUN/'WATCHDOG_STOP').exists()
 os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',PYTHONFAULTHANDLER='1',BRIDGE_DDS_CACHE='/tmp/bridge-full-probe.sqlite')
 m=json.loads((RUN/'manifest.json').read_text());verify_generation(RUN,m);boards=load(RUN/m['corpus']);DiagnosticPool.run=RUN
 start=time.time();summary=dict(epoch=start,baseline=memory_snapshot(),production_commits=0);rows=[];jobs=iter([233,234,235]*15)
 try:
  with DiagnosticPool(max_workers=3,mp_context=mp.get_context('spawn'),initializer=initialize_worker,initargs=(str(RUN),)) as pool, DiagnosticPool(max_workers=1,mp_context=mp.get_context('spawn'),initializer=initialize_worker,initargs=(str(RUN),)) as benpool:
   pending={benpool.submit(probe,str(RUN),m,boards[376].to_dict(),376):376}
   def submit():
    i=next(jobs,None)
    if i is not None:pending[pool.submit(probe,str(RUN),m,boards[i].to_dict(),i)]=i
   for _ in range(3):submit()
   while pending:
    done,_=wait(pending,timeout=10,return_when=FIRST_COMPLETED)
    for f in done:
     i=pending.pop(f);row=f.result();rows.append(row);print(json.dumps(row),flush=True)
     if i!=376 and time.time()-start<300:submit()
  summary['status']='passed'
 except BaseException as e:summary.update(status='failed',error=repr(e))
 summary.update(completed=len(rows),seconds=time.time()-start,rows=rows,final=memory_snapshot());(RUN/'diagnostics/full-concurrent-probe-summary.json').write_text(json.dumps(summary));print(json.dumps({k:v for k,v in summary.items() if k!='rows'}),flush=True)
if __name__=='__main__':
 import subprocess,urllib.request,urllib.error
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1')
 log=(RUN/'diagnostics/ben-full-probe.log').open('w')
 ben=subprocess.Popen([str(BASE/'.venv/bin/python'),'src/gameapi.py','--config',str(RUN/'assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false'],cwd=BASE.parent/'ben',env=env,stdout=log,stderr=subprocess.STDOUT)
 try:
  for _ in range(60):
   if ben.poll() is not None:raise RuntimeError('Diagnostic BEN exited')
   try:urllib.request.urlopen('http://127.0.0.1:8087/',timeout=2);break
   except urllib.error.HTTPError:break
   except urllib.error.URLError:time.sleep(1)
  else:raise RuntimeError('BEN timeout')
  main()
 finally:
  ben.terminate();ben.wait(timeout=30);log.close()

