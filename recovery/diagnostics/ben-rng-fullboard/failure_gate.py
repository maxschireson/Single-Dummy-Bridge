"""Diagnostic transaction sketch: real HTTP response then server SIGKILL.
No arena collector commit path or production files are changed.
"""
import os, sys, json, shutil, signal, time, hashlib
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
NEW=ROOT.parent/'gen6-ben-server-recycled'
sys.path.insert(0,str(NEW))
from ops.ben_board_executor import BenBoardExecutor
from ops.ben_server_lifecycle import BenServer
from concurrent.futures.process import BrokenProcessPool

def initialize(): pass

def request_then_exit(kill):
 import urllib.request
 url=json.loads((OUT.parent/'ben-card-repeat/summary.json').read_text())['request']
 response=json.load(urllib.request.urlopen(url,timeout=120))
 (OUT/'failure-request-response.json').write_text(json.dumps(response))
 if kill:
  os.kill(int((OUT/'test-server.pid').read_text()),signal.SIGKILL)
  time.sleep(.5)
 return response

class TestServer(BenServer):
 def start(self):
  super().start()
  (OUT/'test-server.pid').write_text(str(self.process.pid))
  return self

def run():
 initial=json.loads((OUT/'initial-state.json').read_text())
 checkpoint=OUT/'test-committed-checkpoint.json'
 checkpoint.write_text(json.dumps({'accepted':None,'claim_state':initial}))
 before=checkpoint.read_bytes()
 rows=[]
 for kill in (True,False):
  working=OUT/('failed-working-state.json' if kill else 'accepted-working-state.json')
  working.write_text(json.dumps(json.loads(checkpoint.read_text())['claim_state']))
  initial_working=working.read_bytes()
  os.environ['CLAIM_STATE']=str(working)
  os.environ['CLAIM_START']=str(OUT/('failed-start.json' if kill else 'accepted-start.json'))
  factory=lambda:TestServer(OUT,command=[sys.executable,str(OUT/'server.py'),'--config',str(ROOT/'runs/gen6-chatgpt-ben-recycled-20261111/assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false'],cwd=ROOT.parent/'ben')
  accepted=False;error=None
  with BenBoardExecutor(OUT,initialize,(),server_factory=factory) as executor:
   try:
    result=executor.submit(request_then_exit,kill).result(timeout=180)
    temp=checkpoint.with_suffix('.tmp')
    temp.write_text(json.dumps({'accepted':result,'claim_state':json.loads(working.read_text())}))
    os.replace(temp,checkpoint);accepted=True
   except BrokenProcessPool as exc: error=str(exc)
  advanced=json.loads(working.read_text())!=json.loads(initial_working)
  assert advanced,'Request did not exercise claim RNG'
  if kill:
   assert not accepted and checkpoint.read_bytes()==before
   assert 'server exited unexpectedly: -9' in error,error
  else:
   assert accepted and json.loads(checkpoint.read_text())['claim_state']==json.loads(working.read_text())
  rows.append(dict(injected_sigkill=kill,accepted=accepted,error=error,private_claim_state_advanced=advanced,committed_checkpoint_changed=checkpoint.read_bytes()!=before))
 report=dict(status='passed',cases=rows,production_commits=0,scope='Real BEN HTTP request and actual candidate executor/server exit gate. Diagnostic single-file result+RNG checkpoint sketch only; production episode/receipt/RNG transaction and crash recovery are not implemented or validated.')
 (OUT/'failure-gate-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':run()
