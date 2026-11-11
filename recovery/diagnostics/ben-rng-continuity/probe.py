import os,sys,json,time,subprocess,urllib.request,urllib.error,shutil,hashlib
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
out=Path(__file__).resolve().parent;root=out.parents[3];run=root/'runs/gen6-chatgpt-ben-recycled-20261111'
url=json.loads((out.parent/'ben-card-repeat/summary.json').read_text())['request']
def batch(name,state,count):
 start=out/(name+'-start.json');env=dict(os.environ,CLAIM_STATE=str(state),CLAIM_START=str(start))
 with (out/(name+'.log')).open('w') as log:
  p=subprocess.Popen([sys.executable,str(out/'server.py'),'--config',str(run/'assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false'],cwd=root.parent/'ben',env=env,stdout=log,stderr=subprocess.STDOUT)
  try:
   for _ in range(120):
    if p.poll() is not None:raise RuntimeError(p.returncode)
    try:urllib.request.urlopen('http://127.0.0.1:8087/',timeout=2);break
    except urllib.error.HTTPError:break
    except urllib.error.URLError:time.sleep(.5)
   else:raise RuntimeError('readiness timeout')
   rows=[]
   for i in range(count):
    data=json.load(urllib.request.urlopen(url,timeout=120));rows.append(data);print(name,i,data['card'],flush=True)
   (out/(name+'-responses.json')).write_text(json.dumps(rows,indent=2));return rows
  finally:p.terminate();p.wait(timeout=30)
a=batch('persistent',out/'persistent-state.json',20)
shutil.copy2(out/'persistent-start.json',out/'recycled-state.json')
b=batch('recycled-a',out/'recycled-state.json',10)+batch('recycled-b',out/'recycled-state.json',10)
report=dict(status='passed' if a==b else 'failed',requests=20,exact_full_responses=a==b,final_python_rng_equal=(out/'persistent-state.json').read_bytes()==(out/'recycled-state.json').read_bytes(),persistent_cards=[x['card'] for x in a],recycled_cards=[x['card'] for x in b],production_commits=0,scope='Isolated single-position request sequence, not full board equivalence or production adoption. No claim seeding; carries actual Python RNG state.')
(out/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
assert report['exact_full_responses'] and report['final_python_rng_equal']
