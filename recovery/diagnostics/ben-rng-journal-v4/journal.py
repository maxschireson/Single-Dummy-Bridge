"""Diagnostic only: immutable objects, SHA parent links and one atomic head.

No garbage collection. A snapshot captures CURRENT once, then follows only that
immutable chain. Single writer enforced for the lifetime of Writer.
"""
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import uuid

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
ROOT = HERE.parents[3]
SCHEMA = 'diagnostic-rng-journal-v4'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()

def syncdir(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def durable(path, data):
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

def cut(stage):
    if os.environ.get('RNG_DIAGNOSTIC_CUT') == stage:
        os.kill(os.getpid(), signal.SIGKILL)

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def specification(mode):
    require(mode in ('real-records', 'synthetic-scaling'), 'mode')
    paths = [HERE/'journal.py', ROOT/'ops/gen5_runtime.py', ROOT/'ops/export_gen5.py',
             RUN/'manifest.json', RUN/'retained-receipts.json']
    paths += [HERE.parent/'ben-rng-live-v31'/n for n in
              ('collect.py','live_executor.py','live_server.py','server.py','semantics.py')]
    return dict(schema=SCHEMA, eligible=False, mode=mode,
                runtime={str(p):sha(p.read_bytes()) for p in paths},
                initial_rng=sha((HERE.parent/'ben-rng-broader/initial-state.json').read_bytes()))

def verify_spec(root):
    raw = (root/'PROTOCOL.json').read_bytes()
    spec = json.loads(raw)
    require(spec == specification(spec['mode']), 'protocol/runtime mismatch')
    import sys
    sys.path.insert(0,str(ROOT))
    from bridge_harness.mixed_arena import verify_generation
    verify_generation(RUN,json.loads((RUN/'manifest.json').read_bytes()))
    return spec, sha(raw)

def object_path(root, digest):
    require(isinstance(digest, str) and len(digest)==64 and all(c in '0123456789abcdef' for c in digest), 'object digest')
    return root/'objects'/digest

def put(root, data):
    digest = sha(data)
    target = object_path(root, digest)
    if target.exists():
        require(target.read_bytes()==data, 'existing object corrupt')
        return digest
    temp = root/'objects'/('tmp-'+uuid.uuid4().hex)
    durable(temp, data)
    # Atomic install; orphan temps are never referenced by a head.
    os.replace(temp, target)
    return digest

def get(root, digest):
    data = object_path(root, digest).read_bytes()
    require(sha(data)==digest, 'object hash mismatch')
    return data

def initialize(root, mode='real-records'):
    root=Path(root); root.mkdir()
    (root/'objects').mkdir()
    spec=specification(mode); raw=encode(spec)
    durable(root/'PROTOCOL.json',raw)
    initial=(HERE.parent/'ben-rng-broader/initial-state.json').read_bytes()
    put(root,initial);syncdir(root/'objects')
    durable(root/'CURRENT',encode(dict(schema=SCHEMA,protocol=sha(raw),tip=None,count=0,rng=sha(initial))))
    syncdir(root);syncdir(root.parent)

def read(root, head_raw=None):
    """Iterative full verification. O(records + bytes), no ancestor embedding."""
    root=Path(root);spec,identity=verify_spec(root)
    if head_raw is None:head_raw=(root/'CURRENT').read_bytes()
    head=json.loads(head_raw)
    require(head['schema']==SCHEMA and head['protocol']==identity, 'head identity')
    rows=[];seen=set();indices=set();tip=head['tip'];count=head['count'];rng=head['rng']
    latest=get(root,rng)
    while tip is not None:
        require(tip not in seen, 'cycle');seen.add(tip)
        node=json.loads(get(root,tip))
        require(node['protocol']==identity and node['sequence']==count, 'node identity/order')
        require(node['post_rng']==rng, 'RNG chain')
        raw=get(root,node['episode']);recraw=get(root,node['receipt']);post=get(root,rng)
        rec=json.loads(recraw)
        require(rec['index']==node['index'] and rec['episode_sha256']==sha(raw), 'receipt binding')
        require(node['index'] not in indices, 'duplicate');indices.add(node['index'])
        if node['kind']=='normal':require(node['pre_rng']==rng, 'normal changed RNG')
        else:require(node['kind']=='BEN', 'kind')
        rows.append((node,raw,recraw,post,tip))
        tip=node['parent'];rng=node['pre_rng'];count-=1
    require(count==0 and rng==spec['initial_rng'], 'initial chain')
    get(root,rng)
    rows.reverse()
    return rows,latest,head_raw

class Writer:
    """Validate once; hold lock and cached accepted set for O(1) chain append."""
    def __init__(self, root):
        self.root=Path(root)
        self.lock=(self.root/'.writer.lock').open('a+')
        try:
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.spec,self.identity=verify_spec(self.root)
            rows,self.rng,self.head_raw=read(self.root)
            self.indices={r[0]['index'] for r in rows}
        except BaseException:
            self.lock.close();raise
    def __enter__(self):return self
    def __exit__(self,*args):self.lock.close()
    def append(self,index,raw,post_rng=None,expected_rng=None):
        require(self.spec['mode']=='real-records','real append in synthetic journal')
        import sys
        sys.path.insert(0,str(ROOT))
        from ops.gen5_runtime import validate, receipt
        record=json.loads(gzip.decompress(raw))
        validate(record,json.loads((RUN/'manifest.json').read_bytes()),index)
        kind='BEN' if 'ben' in record['pair'] else 'normal'
        # receipt() reads the episode bytes; create an unaccepted staging object.
        ep=put(self.root,raw)
        rec=receipt(record,object_path(self.root,ep))
        return self._append(index,raw,encode(rec),kind,post_rng,expected_rng)
    def append_synthetic(self,index):
        require(self.spec['mode']=='synthetic-scaling','synthetic append in real journal')
        raw=encode({'synthetic_index':index})
        return self._append(index,raw,encode(dict(index=index,episode_sha256=sha(raw))), 'normal',None,sha(self.rng))
    def _append(self,index,raw,recraw,kind,post_rng,expected_rng):
        require((self.root/'CURRENT').read_bytes()==self.head_raw,'head changed')
        require(index not in self.indices,'duplicate')
        require(expected_rng==sha(self.rng),'stale RNG')
        if kind=='normal':
            require(post_rng is None,'normal poststate');post_rng=self.rng
        else:require(post_rng is not None,'missing BEN RNG')
        # Validate Python RNG representation without changing process-global RNG.
        import random
        def tup(x):return tuple(map(tup,x)) if isinstance(x,list) else x
        random.Random().setstate(tup(json.loads(post_rng)))
        head=json.loads(self.head_raw)
        ep=put(self.root,raw);cut('episode')
        rec=put(self.root,recraw);cut('receipt')
        rng=put(self.root,post_rng);cut('rng')
        node=dict(protocol=self.identity,sequence=head['count']+1,index=index,kind=kind,
                  parent=head['tip'],pre_rng=sha(self.rng),post_rng=rng,episode=ep,receipt=rec)
        tip=put(self.root,encode(node));cut('node')
        syncdir(self.root/'objects');cut('objects_fsync')
        new=encode(dict(schema=SCHEMA,protocol=self.identity,tip=tip,count=head['count']+1,rng=rng))
        temp=self.root/('NEXT-'+uuid.uuid4().hex);durable(temp,new);cut('next_fsync')
        os.replace(temp,self.root/'CURRENT');cut('pointer_replace')
        syncdir(self.root);cut('commit_fsync')
        self.head_raw=new;self.rng=post_rng;self.indices.add(index)
        return rng

def snapshot(root,dest):
    """Snapshot one captured head; concurrent appends cannot extend this view."""
    root=Path(root);dest=Path(dest)
    rows,rng,head_raw=read(root)
    spec,identity=verify_spec(root)
    dest.mkdir();(dest/'objects').mkdir()
    wanted={spec['initial_rng']}
    for node,raw,recraw,post,tip in rows:
        wanted.update((tip,node['episode'],node['receipt'],node['post_rng'],node['pre_rng']))
    for digest in wanted:durable(object_path(dest,digest),get(root,digest))
    syncdir(dest/'objects')
    durable(dest/'PROTOCOL.json',(root/'PROTOCOL.json').read_bytes())
    durable(dest/'CURRENT',head_raw);syncdir(dest);syncdir(dest.parent)
    copied,copyrng,copyhead=read(dest)
    require(copyhead==head_raw and copyrng==rng and len(copied)==len(rows),'snapshot mismatch')
    return len(rows)

def materialize(root,dest):
    import sys,shutil
    sys.path.insert(0,str(ROOT))
    from ops.gen5_runtime import state
    root=Path(root);dest=Path(dest)
    require(verify_spec(root)[0]['mode']=='real-records','synthetic export forbidden')
    rows,rng,_=read(root);dest.mkdir()
    for name in ('manifest.json','retained-receipts.json'):shutil.copy2(RUN/name,dest/name)
    (dest/'episodes').mkdir();(dest/'receipts').mkdir()
    for name in json.loads((RUN/'retained-receipts.json').read_bytes()):shutil.copy2(RUN/'receipts'/name,dest/'receipts'/name)
    for node,raw,recraw,_,_ in rows:
        stem=f"{node['index']:06d}"
        (dest/'episodes'/f'{stem}.json.gz').write_bytes(raw)
        (dest/'receipts'/f'{stem}.json').write_bytes(recraw)
    (dest/'state.json').write_bytes(encode(state([json.loads(r[2]) for r in rows],json.loads((RUN/'manifest.json').read_bytes()))))
    (dest/'heartbeat.json').write_bytes(encode(dict(epoch=0,workers=0)))
    (dest/'claim-state.json').write_bytes(rng)
    return len(rows)
