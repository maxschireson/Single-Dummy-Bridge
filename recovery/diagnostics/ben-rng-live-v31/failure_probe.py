"""Real BEN results rejected after injected worker or server death; diagnostic only."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
import sys,json,signal
from pathlib import Path
from adapter import OUT,RUN,ROOT,accepted,sha
from live_executor import BenBoardExecutor
from live_server import BenServer
from ops.gen5_runtime import play,initialize_worker
from bridge_harness.corpus import load
from concurrent.futures.process import BrokenProcessPool

def killed_worker(*args):
 play(*args)
 os.kill(os.getpid(),signal.SIGKILL)

class KilledServer(BenServer):
 def stop(self):
  if self.process is not None and self.process.poll() is None:
   self.process.kill();self.process.wait()
  return super().stop()

def main():
 m=json.loads((RUN/'manifest.json').read_text());boards=load(RUN/m['corpus']);initial=(OUT.parent/'ben-rng-broader/initial-state.json').read_bytes();results=[]
 for mode in ['worker','server']:
  d=OUT/('failure-'+mode);d.mkdir();working=d/'working.json';working.write_bytes(initial)
  journal=d/'journal';journal.mkdir()
  os.environ.update(CLAIM_STATE=str(working),CLAIM_START=str(d/'start.json'),BRIDGE_DDS_CACHE=str(d/'cache.sqlite'))
  cls=KilledServer if mode=='server' else BenServer
  factory=lambda:cls(d,command=[sys.executable,str(OUT/'server.py'),'--config',str(RUN/'assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false'],cwd=ROOT.parent/'ben')
  with BenBoardExecutor(d,initialize_worker,(str(RUN),),server_factory=factory) as ex:
   try:ex.submit(killed_worker if mode=='worker' else play,str(RUN),m,boards[1082].to_dict(),1082).result(timeout=600)
   except BrokenProcessPool as exc:error=str(exc)
   else:raise AssertionError('Killed process result accepted')
  assert accepted(journal)==([],None) and not (journal/'CURRENT').exists()
  assert working.read_bytes()!=initial
  expected=(OUT.parent/'ben-rng-live-v3/working-1.json').read_bytes();assert working.read_bytes()==expected
  results.append({'mode':mode,'error':error,'accepted_count':0,'private_rng_advanced':True,'private_rng_matches_reference':True,'production_commits':0})
 (OUT/'failure-result.json').write_text(json.dumps({'status':'passed','cases':results,'scope':'Real full BEN1082 play followed by intentional SIGKILL worker before result delivery or server before lifecycle acceptance. Private state advances but no commit. No in-flight collector death or power-loss test.'},indent=2))
 print(json.dumps(results),flush=True)
if __name__=='__main__':main()
