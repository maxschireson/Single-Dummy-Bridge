#!/usr/bin/env python3
import sys, tempfile, subprocess, time, json, importlib.util, os, argparse
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description="P01 synthetic parity check; not R4c acceptance")
parser.add_argument("checkout", type=Path, help="isolated research checkout with P01 applied")
args=parser.parse_args()
root=args.checkout.resolve()
base="5addd826af8b10d7343df51ada528a7327d059b6"
env=dict(os.environ, PYTHONPATH=str(root)+os.pathsep+os.environ.get("PYTHONPATH", ""))
sys.path.insert(0,str(root))
from bridge_harness import gen7_net as net
spec=importlib.util.spec_from_file_location('tr',root/'scripts/train_rollout_net.py'); tr=importlib.util.module_from_spec(spec); spec.loader.exec_module(tr)
w=Path(tempfile.mkdtemp(prefix='p01-')); rng=np.random.default_rng(8)
reference=w/'reference.py'
reference.write_bytes(subprocess.check_output(['git','show',base+':scripts/train_rollout_net.py'],cwd=root))
def data(n):
    meta=np.zeros((n,11),np.int32); meta[:,0]=rng.integers(0,13,n); meta[:,1]=rng.integers(0,14,n); meta[:,3]=np.arange(n)%52; meta[:,8]=1; meta[::2,8]=2; meta[:,9]=1; meta[:,10]=1
    return dict(state=rng.integers(0,11,(n,52),dtype=np.int8),order=rng.integers(0,53,(n,52),dtype=np.int8),legal=np.tile(np.arange(52)<13,(n,1)),ctx=rng.random((n,net.N_CTX),dtype=np.float32),auction=np.zeros((n,net.N_AUCTION),np.int8),shown=rng.random((n,net.N_SHOWN),dtype=np.float32),gap=rng.random((n,52),dtype=np.float32),owner=rng.integers(-1,3,(n,52),dtype=np.int8),meta=meta,deal=np.arange(n,dtype=np.int32),deal_split=np.zeros(n,np.int8),bot_names=np.array(['','stup0','8s-32']),**{k:np.zeros((1,),np.float32) for k in net.BANK_KEYS})
np.savez(w/'train.npz',**data(128));np.savez(w/'val.npz',**data(32))
np.savez(w/'init.npz',**tr.init(1,rng,32,3),kind=np.array(1),bot_vocab=np.array(['','stup0','8s-32']))
common=['--data',str(w/'train.npz'),'--all-train','--val-data',str(w/'val.npz'),'--width','32','--batch','16','--epochs','1','--init',str(w/'init.npz'),'--id-dropout','0','--select','stup0']
for name,script,lr in [('before',reference,'1e-12'),('control',reference,'1e-4'),('new',root/'scripts/train_rollout_net.py','1e-4')]:
    args=[sys.executable,str(script),*common,'--lr',lr,'--out',str(w/name)]
    if name=='new':args+=['--before-metrics',str(w/'starting.json')]
    t=time.perf_counter()
    with open(w/(name+'.log'),'w') as log:subprocess.run(args,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    print(name,round(time.perf_counter()-t,3))
b=json.loads((w/'before/metrics.json').read_text());s=json.loads((w/'starting.json').read_text())
assert b['validation']==s['validation']
assert b['who_use']['blank']['all']=={k:s['who_use']['blank']['all'][k] for k in b['who_use']['blank']['all']}
assert s['optimizer_steps']==0
assert json.loads((w/'control/metrics.json').read_text())['selected_epoch']==1
assert json.loads((w/'new/metrics.json').read_text())['selected_epoch']==1
with np.load(w/'control/policy.npz') as c,np.load(w/'new/policy.npz') as n:
    for k in c.files:np.testing.assert_array_equal(c[k],n[k],err_msg=k)
print('PASS: before tables identical; blank-ID scores identical; zero-step snapshot; trained export bit-identical to original trainer')
print('fixtures',w)
