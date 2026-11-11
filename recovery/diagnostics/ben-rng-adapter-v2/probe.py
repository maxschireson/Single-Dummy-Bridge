"""Diagnostic adapter v2; real receipt/validator/export functions, archived fixtures only."""
import sys,os,json,hashlib,gzip,fcntl,shutil,tempfile,time,signal
from pathlib import Path
OUT=Path(__file__).resolve().parent;RUN=OUT.parents[1];ROOT=OUT.parents[3]
sys.path.insert(0,str(ROOT))
from ops.gen5_runtime import validate,receipt,state
from ops.export_gen5 import export
sys.path.insert(0,str(OUT.parent/'ben-rng-broader'))
from transaction_probe import durable,syncdir,sha

def cut(stage):
 if os.environ.get('RNG_DIAGNOSTIC_CUT')==stage:os.kill(os.getpid(),signal.SIGKILL)

def accepted(root):
 root=Path(root);p=root/'CURRENT'
 if not p.exists():return [],None
 marker=json.loads(p.read_bytes());latest=None;rows=[];seen=set()
 while marker:
  generation=marker['generation'];assert generation not in seen;seen.add(generation)
  d=root/generation;assert json.loads((d/'manifest.json').read_bytes())==marker
  blobs={n:(d/n).read_bytes() for n in marker['hashes']}
  assert all(sha(blobs[n])==h for n,h in marker['hashes'].items())
  r=json.loads(blobs['receipt.json']);assert r['episode_sha256']==sha(blobs['episode.json.gz'])
  assert marker['post_rng']==sha(blobs['rng.json'])
  if latest is None:latest=blobs['rng.json']
  rows.append((r,blobs['episode.json.gz'],blobs['rng.json'],marker))
  prev=marker['previous']
  if prev:assert marker['pre_rng']==prev['post_rng']
  marker=prev
 rows.reverse();assert len({r[0]['index'] for r in rows})==len(rows)
 return rows,latest

def commit(root,index,post_rng=None,expected_rng=None):
 root=Path(root)
 with (root/'.writer.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  rows,current=accepted(root)
  if current is None:current=(OUT.parent/'ben-rng-fullboard/initial-state.json').read_bytes()
  assert expected_rng is None or sha(current)==expected_rng,'stale RNG'
  assert index not in {x[0]['index'] for x in rows},'duplicate'
  raw=(RUN/'episodes'/f'{index:06d}.json.gz').read_bytes();record=json.loads(gzip.decompress(raw))
  m=json.loads((RUN/'manifest.json').read_bytes());validate(record,m,index)
  is_ben='ben' in record['pair']
  if is_ben:assert post_rng is not None
  else:assert post_rng is None;post_rng=current
  d=root/f'g{len(rows):06d}';d.mkdir();cut('mkdir')
  durable(d/'episode.json.gz',raw);cut('episode')
  rec=receipt(record,d/'episode.json.gz');original=json.loads((RUN/'receipts'/f'{index:06d}.json').read_bytes());assert rec==original
  blobs={'episode.json.gz':raw,'receipt.json':(RUN/'receipts'/f'{index:06d}.json').read_bytes(),'rng.json':post_rng}
  for n in ('receipt.json','rng.json'):durable(d/n,blobs[n]);cut(n)
  previous=json.loads((root/'CURRENT').read_bytes()) if (root/'CURRENT').exists() else None
  marker={'schema':'diagnostic-rng-adapter-v2','generation':d.name,'previous':previous,'pre_rng':sha(current),'post_rng':sha(post_rng),'hashes':{n:sha(v) for n,v in blobs.items()}}
  encoded=json.dumps(marker,sort_keys=True).encode();durable(d/'manifest.json',encoded);cut('manifest');syncdir(d);cut('generation_fsync');syncdir(root);cut('parent_fsync')
  durable(root/'NEXT',encoded);cut('next_fsync');os.replace(root/'NEXT',root/'CURRENT');cut('pointer_replace');syncdir(root);cut('commit_fsync')
  return sha(post_rng)

def materialize(journal,dest):
 rows,rng=accepted(journal);dest=Path(dest);dest.mkdir()
 for name in ('manifest.json','retained-receipts.json'):shutil.copy2(RUN/name,dest/name)
 (dest/'receipts').mkdir();(dest/'episodes').mkdir()
 # Original retained receipts remain exact; only selected archived episodes are fixtures.
 for name in json.loads((RUN/'retained-receipts.json').read_bytes()):shutil.copy2(RUN/'receipts'/name,dest/'receipts'/name)
 for rec,raw,_,marker in rows:
  stem=f"{rec['index']:06d}";(dest/'episodes'/f'{stem}.json.gz').write_bytes(raw)
  (dest/'receipts'/f'{stem}.json').write_bytes((Path(journal)/marker['generation']/'receipt.json').read_bytes())
 m=json.loads((dest/'manifest.json').read_bytes());(dest/'state.json').write_text(json.dumps(state([x[0] for x in rows],m)))
 (dest/'heartbeat.json').write_text(json.dumps({'epoch':0,'workers':0}))
 (dest/'claim-state.json').write_bytes(rng)
 return rows

def run():
 with tempfile.TemporaryDirectory(prefix='rng-adapter-v2-') as tmp:
  t=Path(tmp);j=t/'journal';j.mkdir()
  initial=commit(j,1600);after_ben=commit(j,2561,(OUT.parent/'ben-rng-broader/baseline-state.json').read_bytes(),initial)
  after_self=commit(j,1601);assert after_self==after_ben
  for index,expected in [(1600,None),(1602,'bad')]:
   before=(j/'CURRENT').read_bytes()
   try:commit(j,index,expected_rng=expected)
   except AssertionError:pass
   else:raise AssertionError('invalid commit accepted')
   assert before==(j/'CURRENT').read_bytes()
  # Simulate an unaccepted/orphan episode: the accepted view must omit it.
  orphan=j/'orphan';orphan.mkdir();shutil.copy2(RUN/'episodes/001602.json.gz',orphan/'episode.json.gz')
  rows=materialize(j,t/'view');assert [x[0]['index'] for x in rows]==[1600,2561,1601]
  export(t/'view',t/'export')
  shutil.copytree(j,t/'snapshot');shutil.copytree(t/'snapshot',t/'restored')
  restored=materialize(t/'restored',t/'restored-view');export(t/'restored-view',t/'restored-export')
  a=json.loads((t/'export/arena/data.json').read_bytes());b=json.loads((t/'restored-export/arena/data.json').read_bytes())
  for key in ('completed','views','own_views','difference_views','allocation','manifest_identity'):assert a[key]==b[key],key
  assert a['completed']==3 and (t/'view/claim-state.json').read_bytes()==(t/'restored-view/claim-state.json').read_bytes()
  for p in (t/'view/receipts').glob('*.json'):assert p.read_bytes()==(RUN/'receipts'/p.name).read_bytes()
  (OUT/'export-summary.json').write_text(json.dumps({k:a[k] for k in ('completed','views','own_views','allocation','manifest_identity')},indent=2))
 report={'status':'passed','schema':'diagnostic-rng-adapter-v2','fixture_indices':[1600,2561,1601],'normal_preserved_rng':True,'receipt_bytes_preserved':True,'real_runtime_validate_receipt_export':True,'snapshot_restore_export_equal':True,'orphan_ignored':True,'duplicate_and_stale_rejected':True,'production_commits':0,'scope':'Archived fixtures, not newly played boards. BEN post-state is a prior diagnostic fixture, not generated by these records. Uses actual runtime validation/receipt and export functions through an accepted-record materialization adapter. No production run-loop/server wiring, no integrated crash test, no adoption.'}
 (OUT/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':run()
