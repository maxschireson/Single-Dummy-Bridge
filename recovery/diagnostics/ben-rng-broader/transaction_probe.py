"""Diagnostic v1 commit-marker protocol. NOT used by the arena collector."""
import json,hashlib,os,signal,subprocess,sys,tempfile
from pathlib import Path
OUT=Path(__file__).resolve().parent
RUN=OUT.parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def syncdir(p):
 fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def durable(p,data):
 with p.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def cut(stage,target):
 if stage==target:os.kill(os.getpid(),signal.SIGKILL)
def commit(root,generation,episode,receipt,rng,pre_hash,target=''):
 root=Path(root)
 if (root/'CURRENT').exists():assert pre_hash==sha(recover(root)[2]),'Stale pre-state'
 d=root/generation;d.mkdir();cut('mkdir',target)
 receipt=dict(receipt,diagnostic_rng_protocol={'version':1,'pre_sha256':pre_hash,'post_sha256':sha(rng)})
 blobs={'episode.json.gz':episode,'receipt.json':json.dumps(receipt,sort_keys=True).encode(),'rng.json':rng}
 for name,data in blobs.items():durable(d/name,data);cut(name,target)
 marker=json.dumps({'generation':generation,'hashes':{n:sha(v) for n,v in blobs.items()}},sort_keys=True).encode()
 durable(d/'manifest.json',marker);cut('manifest',target);syncdir(d);cut('generation_fsync',target)
 syncdir(root);cut('parent_fsync',target)
 durable(root/'NEXT',marker);cut('next_fsync',target)
 os.replace(root/'NEXT',root/'CURRENT');cut('pointer_replace',target)
 syncdir(root);cut('commit_fsync',target)
def recover(root):
 root=Path(root);m=json.loads((root/'CURRENT').read_bytes());d=root/m['generation']
 assert (d/'manifest.json').read_bytes()==(root/'CURRENT').read_bytes()
 b={n:(d/n).read_bytes() for n in m['hashes']}
 assert all(sha(b[n])==h for n,h in m['hashes'].items())
 r=json.loads(b['receipt.json']);assert sha(b['episode.json.gz'])==r['episode_sha256']
 assert sha(b['rng.json'])==r['diagnostic_rng_protocol']['post_sha256']
 return m['generation'],r,b['rng.json']
def fixtures():
 r=json.loads((RUN/'receipts/001082.json').read_bytes());e=(RUN/'episodes/001082.json.gz').read_bytes()
 old=(OUT.parent/'ben-rng-fullboard/initial-state.json').read_bytes();new=(OUT.parent/'ben-rng-fullboard/baseline-state.json').read_bytes()
 return e,r,old,new
if __name__=='__main__':
 e,r,old,new=fixtures()
 if len(sys.argv)>1:
  commit(sys.argv[1],'g1',e,r,new,sha(old),sys.argv[2]);sys.exit(0)
 stages=['mkdir','episode.json.gz','receipt.json','rng.json','manifest','generation_fsync','parent_fsync','next_fsync','pointer_replace','commit_fsync']
 results=[]
 for stage in stages:
  with tempfile.TemporaryDirectory(prefix='rng-commit-') as tmp:
   commit(tmp,'g0',e,r,old,sha(old))
   child=subprocess.run([sys.executable,__file__,tmp,stage]);assert child.returncode==-signal.SIGKILL
   generation,receipt,state=recover(tmp)
   expected='g1' if stage in ('pointer_replace','commit_fsync') else 'g0'
   assert generation==expected and state==(new if expected=='g1' else old)
   results.append({'cut':stage,'exitcode':child.returncode,'recovered':generation,'coherent':True})
 with tempfile.TemporaryDirectory(prefix='rng-corrupt-') as tmp:
  commit(tmp,'g0',e,r,old,sha(old));(Path(tmp)/'g0/rng.json').write_text('corrupt')
  try:recover(tmp)
  except AssertionError:corruption_rejected=True
  else:raise AssertionError('Corruption accepted')
 with tempfile.TemporaryDirectory(prefix='rng-stale-') as tmp:
  commit(tmp,'g0',e,r,old,sha(old))
  try:commit(tmp,'g1',e,r,new,'wrong')
  except AssertionError:stale_rejected=True
  else:raise AssertionError('Stale state accepted')
  (Path(tmp)/'g0/rng.json').unlink()
  try:recover(tmp)
  except FileNotFoundError:missing_rejected=True
  else:raise AssertionError('Missing state accepted')
 report={'stale_pre_state_rejected':stale_rejected,'missing_rng_rejected':missing_rejected,'status':'passed','schema':'diagnostic-rng-marker-v1','crash_cases':results,'corruption_rejected':corruption_rejected,'production_commits':0,'scope':'Real SIGKILL process interruptions, existing episode/receipt fixture, and captured diagnostic RNG states. Recovery sees old or complete new generation, never mixed. No power-loss simulation; no production collector/export integration; single serial writer assumed; no retry; initial lost production RNG not recovered.'}
 (OUT/'transaction-result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
