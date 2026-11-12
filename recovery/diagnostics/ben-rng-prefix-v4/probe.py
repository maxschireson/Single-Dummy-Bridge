"""Diagnostic live collector death, external group cleanup, restored continuation."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
import sys,json,gzip,time,subprocess,signal,multiprocessing as mp
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent/'ben-rng-journal-v4'))
import journal as j
sys.path.insert(0,str(j.ROOT));sys.path.insert(0,str(OUT.parent/'ben-rng-live-v31'))
from live_executor import BenBoardExecutor
from live_server import BenServer
from ops.gen5_runtime import initialize_worker,play,validate
from ops.export_gen5 import export
from bridge_harness.corpus import load
import psutil

def collect(name):
 root=OUT/name
 with j.Writer(root) as writer:
  m=json.loads((j.RUN/'manifest.json').read_bytes());boards=load(j.RUN/m['corpus'])
  pending=[i for i in (1933,1934,1935,2561) if i not in writer.indices]
  working=OUT/(name+'-working.json');working.write_bytes(writer.rng)
  os.environ.update(CLAIM_STATE=str(working),CLAIM_START=str(OUT/(name+'-start.json')),BRIDGE_DDS_CACHE='/workspace/scratch/171a0eb26892/live-v4-'+name+'.sqlite')
  factory=lambda:BenServer(OUT,command=[sys.executable,str(OUT.parent/'ben-rng-live-v31/server.py'),'--config',str(j.RUN/'assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false'],cwd=j.ROOT.parent/'ben')
  pre=j.sha(writer.rng)
  with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'),initializer=initialize_worker,initargs=(str(j.RUN),)) as normal,BenBoardExecutor(OUT,initialize_worker,(str(j.RUN),),server_factory=factory) as ben:
   futures={}
   for i in pending:
    executor=ben if i==2561 else normal
    futures[executor.submit(play,str(j.RUN),m,boards[i].to_dict(),i)]=i
   (OUT/(name+'-submitted.json')).write_text(json.dumps({'pid':os.getpid(),'pending':pending}))
   for future in as_completed(futures,timeout=900):
    i=futures[future];record=future.result();raw=gzip.compress(json.dumps(record,sort_keys=True).encode(),mtime=0)
    writer.append(i,raw,working.read_bytes() if i==2561 else None,pre if i==2561 else j.sha(writer.rng))

def main():
 # Separate immutable harness binding, checked by each child before work starts.
 binding={'driver':j.sha(Path(__file__).read_bytes()),'journal':j.sha((j.HERE/'journal.py').read_bytes())}
 (OUT/'binding.json').write_bytes(j.encode(binding));j.snapshot(OUT.parent/'ben-rng-live-v4/restored',OUT/'interrupted')
 start_rng=j.read(OUT/'interrupted')[1];log=(OUT/'interrupted.log').open('w')
 p=subprocess.Popen([sys.executable,__file__,'interrupted'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 killed=False;owned=[];cut_state=None
 try:
  deadline=time.monotonic()+180
  while time.monotonic()<deadline and p.poll() is None:
   w=OUT/'interrupted-working.json'
   if (OUT/'interrupted-submitted.json').exists() and w.exists() and w.read_bytes()!=start_rng:
    rows,_,_=j.read(OUT/'interrupted')
    if 2561 not in {r[0]['index'] for r in rows}:
     owned=[{'pid':c.pid,'created':c.create_time()} for c in psutil.Process(p.pid).children(recursive=True)]
     cut_state={'accepted_indices':[r[0]['index'] for r in rows],'private_rng':j.sha(w.read_bytes()),'initial_rng':j.sha(start_rng),'children':owned}
     p.kill();p.wait();killed=True;break
   time.sleep(.02)
  if not killed:raise RuntimeError('Did not observe an in-flight BEN claim-state advance')
 finally:
  if p.poll() is None:p.kill();p.wait()
  # Only this newly created diagnostic process group; never another collector.
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  log.close()
 deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  alive=[]
  for ident in owned:
   try:
    proc=psutil.Process(ident['pid'])
    if proc.create_time()==ident['created'] and proc.status()!=psutil.STATUS_ZOMBIE:alive.append(ident)
   except psutil.NoSuchProcess:pass
  if not alive:break
  time.sleep(.05)
 assert not alive,alive
 rows,rng,_=j.read(OUT/'interrupted');assert 2561 not in {r[0]['index'] for r in rows} and rng==start_rng
 j.snapshot(OUT/'interrupted',OUT/'restored')
 with (OUT/'continuation.log').open('w') as log:
  subprocess.run([sys.executable,__file__,'restored'],stdout=log,stderr=subprocess.STDOUT,check=True,start_new_session=True,timeout=900)
 rows,rng,_=j.read(OUT/'restored');assert {r[0]['index'] for r in rows}=={1082,1930,1931,1932,2561,1933,1934,1935}
 for node,raw,_,_,_ in rows:validate(json.loads(gzip.decompress(raw)),json.loads((j.RUN/'manifest.json').read_bytes()),node['index'])
 import adapter
 reference=adapter.accepted(OUT.parent/'ben-rng-live-v31/restored')[1]
 assert rng==reference
 j.materialize(OUT/'restored',OUT/'view');export(OUT/'view',OUT/'export')
 assert json.loads((OUT/'export/arena/data.json').read_bytes())['completed']==8
 result={'status':'passed','production_commits':0,'collector_exit':p.returncode,'cut':cut_state,'owned_children_inactive':True,'accepted_after_kill':len(j.read(OUT/'interrupted')[0]),'restored_records':8,'final_rng_exact':True,'all_replay_valid':True,'scope':'Actual live normal/BEN futures. External parent cleans diagnostic process group after collector SIGKILL. Not autonomous orphan cleanup, power loss, unchanged-production equivalence or adoption.'}
 (OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
 if len(sys.argv)==1:main()
 else:
  b=json.loads((OUT/'binding.json').read_bytes());assert b=={'driver':j.sha(Path(__file__).read_bytes()),'journal':j.sha((j.HERE/'journal.py').read_bytes())}
  collect(sys.argv[1])
