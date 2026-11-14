import os,sys,subprocess,json,time,hashlib,argparse
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('checkout',type=Path)
parser.add_argument('inputs',type=Path,help='disposable directory containing val.npz, init.npz, inputs.json; results written here')
args=parser.parse_args()
w=args.inputs.resolve();root=args.checkout.resolve()
reference=w/'reference.py'
reference.write_bytes(subprocess.check_output(['git','show','5addd826af8b10d7343df51ada528a7327d059b6:scripts/train_rollout_net.py'],cwd=root))
wrapper=w/'baseline_only_wrapper.py'
wrapper.write_text('''import sys,runpy,optax\nfrom pathlib import Path\noriginal=Path.write_text\ndef write(self,text,*args,**kwargs):\n result=original(self,text,*args,**kwargs)\n if self.name=="before.json": raise SystemExit(0)\n return result\ndef forbidden(*args,**kwargs): raise AssertionError("optimizer step before baseline")\nPath.write_text=write\noptax.apply_updates=forbidden\nscript=sys.argv.pop(1)\nrunpy.run_path(script,run_name="__main__")\n''')
args=[sys.executable,str(wrapper),str(root/'scripts/train_rollout_net.py'),'--data',str(w/'val.npz'),'--val-data',str(w/'val.npz'),'--all-train','--width','768','--batch','256','--id-dropout','0','--init',str(w/'init.npz'),'--init-as','stup0=stu0,9a-32=8s-32,8x3-32=8s-32','--select','stup0','--forget','0.02','--epochs','1','--lr','1e-4','--before-metrics',str(w/'before.json'),'--out',str(w/'new')]
env=dict(os.environ,PYTHONPATH=str(root),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
old_args=[sys.executable,str(reference),*args[3:]]
i=old_args.index('--lr');old_args[i+1]='1e-12'
i=old_args.index('--before-metrics');del old_args[i:i+2]
i=old_args.index('--out');old_args[i+1]=str(w/'old')
start=time.perf_counter()
with (w/'old.log').open('w') as f:subprocess.run(old_args,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
old_seconds=time.perf_counter()-start
t=time.perf_counter()
with (w/'new.log').open('w') as f:subprocess.run(args,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
elapsed=time.perf_counter()-t
a=json.loads((w/'old/metrics.json').read_text());b=json.loads((w/'before.json').read_text())
def compare(x,y,path=''):
 if isinstance(x,dict):
  for k in x:compare(x[k],y[k],path+'/'+k)
 elif isinstance(x,list):
  assert len(x)==len(y),path
  for i,(xx,yy) in enumerate(zip(x,y)):compare(xx,yy,path+'/'+str(i))
 elif isinstance(x,float):assert round(x,4)==round(y,4),(path,x,y)
 else:assert x==y,(path,x,y)
compare(a['validation'],b['validation'],'validation');compare(a['who_use']['blank'],dict(all=b['who_use']['blank']['all'],**b['who_use']['blank']['by_phase']),'blank')
assert b['optimizer_steps']==0
result=dict(passed=True,reference_commit='5addd826af8b10d7343df51ada528a7327d059b6',transfer_commit='ac2886b97487a8e4717a0d05a1aa642d9ba41ded',seconds=dict(old_full_process=old_seconds,new_until_baseline_written=elapsed),optimizer_steps=0,validation=a['validation']['all'],exact_validation=a['validation']==b['validation'],input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [w/'val.npz',w/'init.npz',w/'inputs.json']},notes='Test wrapper exits after before.json is written and rejects any optax.apply_updates call. Timings include startup; old includes final ablations, new only baseline scoring. Not a production full-cycle speedup.')
(w/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
