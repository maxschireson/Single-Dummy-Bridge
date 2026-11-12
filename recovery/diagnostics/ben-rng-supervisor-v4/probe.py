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
  os.environ.update(CLAIM_STATE=str(working),CLAIM_START=str(OUT/(name+'-start.json')),BRIDGE_DDS_CACHE='/workspace/scratch/171a0eb26892/supervisor-v4-'+name+'.sqlite')
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

def supervisor():
 rd,wr=os.pipe()
 with (OUT/'interrupted.log').open('w') as log:
  p=subprocess.Popen([sys.executable,__file__,'interrupted'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  g=subprocess.Popen([sys.executable,__file__,'guard',str(rd),str(p.pid)],pass_fds=(rd,))
  os.close(rd)
  (OUT/'supervisor.json').write_text(json.dumps({'supervisor':os.getpid(),'collector':p.pid,'guard':g.pid}))
  p.wait();os.close(wr);g.wait()

def guard():
 fd,pgid=map(int,sys.argv[2:4])
 while os.read(fd,1):pass
 try:os.killpg(pgid,signal.SIGKILL)
 except ProcessLookupError:pass
 (OUT/'guard-cleanup.json').write_text(json.dumps({'eof':True,'group':pgid,'epoch':time.time()}))

def main():
 (OUT/'binding.json').write_bytes(j.encode({'driver':j.sha(Path(__file__).read_bytes()),'journal':j.sha((j.HERE/'journal.py').read_bytes())}))
 j.snapshot(OUT.parent/'ben-rng-live-v4/restored',OUT/'interrupted')
 prior,rng,_=j.read(OUT/'interrupted')
 sup=subprocess.Popen([sys.executable,__file__,'supervisor'])
 owned=[];injected=False
 try:
  deadline=time.monotonic()+180
  while time.monotonic()<deadline and sup.poll() is None:
   meta=OUT/'supervisor.json';w=OUT/'interrupted-working.json'
   if meta.exists() and w.exists() and w.read_bytes()!=rng:
    rows,_,_=j.read(OUT/'interrupted')
    if 2561 not in {r[0]['index'] for r in rows}:
     ids=json.loads(meta.read_bytes());p=psutil.Process(ids['collector'])
     owned=[{'pid':q.pid,'created':q.create_time()} for q in [p]+p.children(recursive=True)]
     sup.kill();sup.wait();injected=True;break
   time.sleep(.02)
  assert injected,'No in-flight BEN RNG advancement observed'
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   active=[]
   for ident in owned:
    try:
     q=psutil.Process(ident['pid'])
     if q.create_time()==ident['created'] and q.status()!=psutil.STATUS_ZOMBIE:active.append(ident)
    except psutil.NoSuchProcess:pass
   if not active and (OUT/'guard-cleanup.json').exists():break
   time.sleep(.05)
  assert not active,active
  cut,cutrng,_=j.read(OUT/'interrupted');assert cutrng==rng
  assert all(r in cut for r in prior)
  j.snapshot(OUT/'interrupted',OUT/'restored')
  with (OUT/'continuation.log').open('w') as log:
   subprocess.run([sys.executable,__file__,'restored'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
  final,finalrng,_=j.read(OUT/'restored');assert len(final)==8 and all(r in final for r in cut)
  for node,raw,_,_,_ in final:validate(json.loads(gzip.decompress(raw)),json.loads((j.RUN/'manifest.json').read_bytes()),node['index'])
  import adapter
  assert finalrng==adapter.accepted(OUT.parent/'ben-rng-live-v31/restored')[1]
  j.materialize(OUT/'restored',OUT/'view');export(OUT/'view',OUT/'export')
  result={'status':'passed','supervisor_exit':sup.returncode,'guard_eof_cleanup':True,'owned_identities':owned,'all_inactive':True,'prefix':len(cut),'restored':len(final),'final_rng_exact':True,'full_replay':True,'production_commits':0,'scope':'Independent diagnostic guard survives supervisor SIGKILL; not guard-death, host-death, power loss, production integration or unchanged-production equivalence. Zombies count inactive, not reaped.'}
  (OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
 finally:
  if sup.poll() is None:sup.kill();sup.wait()
  # Emergency cleanup of only this test-owned group, after assertions.
  if (OUT/'supervisor.json').exists():
   ids=json.loads((OUT/'supervisor.json').read_bytes())
   try:os.killpg(ids['collector'],signal.SIGKILL)
   except ProcessLookupError:pass

if __name__=='__main__':
 if len(sys.argv)==1:main()
 elif sys.argv[1]=='supervisor':supervisor()
 elif sys.argv[1]=='guard':guard()
 else:
  b=json.loads((OUT/'binding.json').read_bytes());assert b=={'driver':j.sha(Path(__file__).read_bytes()),'journal':j.sha((j.HERE/'journal.py').read_bytes())}
  collect(sys.argv[1])
