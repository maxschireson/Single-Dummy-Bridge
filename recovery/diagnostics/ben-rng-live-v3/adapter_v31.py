"""Diagnostic adapter v2; real receipt/validator/export functions, newly played diagnostic records."""
import sys,os,json,hashlib,gzip,fcntl,shutil,tempfile,time,signal,uuid
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

def commit(root,index,post_rng=None,expected_rng=None,raw=None):
 root=Path(root)
 with (root/'.writer.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  rows,current=accepted(root)
  if current is None:current=(OUT.parent/'ben-rng-broader/initial-state.json').read_bytes()
  assert expected_rng is None or sha(current)==expected_rng,'stale RNG'
  assert index not in {x[0]['index'] for x in rows},'duplicate'
  assert raw is not None;record=json.loads(gzip.decompress(raw))
  m=json.loads((RUN/'manifest.json').read_bytes());validate(record,m,index)
  is_ben='ben' in record['pair']
  if is_ben:assert post_rng is not None
  else:assert post_rng is None;post_rng=current
  d=root/f'g{len(rows):06d}-{uuid.uuid4().hex}';d.mkdir();cut('mkdir')
  durable(d/'episode.json.gz',raw);cut('episode')
  rec=receipt(record,d/'episode.json.gz')
  blobs={'episode.json.gz':raw,'receipt.json':json.dumps(rec,sort_keys=True).encode(),'rng.json':post_rng}
  for n in ('receipt.json','rng.json'):durable(d/n,blobs[n]);cut(n)
  previous=json.loads((root/'CURRENT').read_bytes()) if (root/'CURRENT').exists() else None
  marker={'schema':'diagnostic-rng-live-v3.1','generation':d.name,'previous':previous,'pre_rng':sha(current),'post_rng':sha(post_rng),'hashes':{n:sha(v) for n,v in blobs.items()}}
  encoded=json.dumps(marker,sort_keys=True).encode();durable(d/'manifest.json',encoded);cut('manifest');syncdir(d);cut('generation_fsync');syncdir(root);cut('parent_fsync')
  next_path=root/('NEXT-'+uuid.uuid4().hex);durable(next_path,encoded);cut('next_fsync');os.replace(next_path,root/'CURRENT');cut('pointer_replace');syncdir(root);cut('commit_fsync')
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

