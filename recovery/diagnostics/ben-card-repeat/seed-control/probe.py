import os,sys,time,json,subprocess,urllib.request,urllib.error
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
root=Path(__file__).resolve().parents[5];run=root/'runs/gen6-chatgpt-ben-recycled-20261111';out=Path(__file__).parent
url='http://127.0.0.1:8087/play?hand=.K9.KQT975432.85&seat=S&dealer=S&vul=Both&ctx=5D------&matchtype=IMP&details=true&dummy=T62.A7543.J8.AT9&played=SAS2S3D2HKH8H3H2H9HTHAHJH4H6D3D6C2CAC3&format=false'
rows=[]
for trial in range(1):
 with (out/f'server-{trial}.log').open('w') as log:
  p=subprocess.Popen([sys.executable,str(out/'server.py'),'--config',str(run/'assets/ben-16.conf'),'--port','8087','--host','127.0.0.1','--record','false'],cwd=root.parent/'ben',stdout=log,stderr=subprocess.STDOUT)
  try:
   for _ in range(90):
    if p.poll() is not None:raise RuntimeError(p.returncode)
    try:urllib.request.urlopen('http://127.0.0.1:8087/',timeout=2);break
    except urllib.error.HTTPError:break
    except urllib.error.URLError:time.sleep(.5)
   for i in range(10):
    data=json.load(urllib.request.urlopen(url,timeout=120));rows.append(dict(server=trial,repeat=i,response=data));(out/'responses.json').write_text(json.dumps(rows,indent=2));print(trial,i,data.get('card'),flush=True)
  finally:p.terminate();p.wait(timeout=30)
(out/'summary.json').write_text(json.dumps(dict(request=url,responses=len(rows),production_commits=0,server_exitcodes='intentional terminate after each 20-request batch'),indent=2))
