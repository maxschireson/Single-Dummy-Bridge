#!/usr/bin/env python3
"""Build each immutable episode once; emit a manifest for existing row consumers."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import numpy as np


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic(path, content):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        f.write(content);f.flush();os.fsync(f.fileno());temp=Path(f.name)
    os.replace(temp, path)


def identity(builder, scorer, alias):
    root = builder.resolve().parents[1]
    dependencies = sorted(set([builder.resolve(), *root.glob('scripts/*.py'), *root.glob('bridge_harness/**/*.py'), *root.glob('bridge_harness/*.so')]))
    return dict(schema=1, builder=str(builder.resolve()), code={str(p.relative_to(root)):sha(p) for p in dependencies},
                scorer_sha256=sha(scorer), alias=alias, flags=['--policy-only','--rollout-gap'], python=platform.python_version(), numpy=np.__version__)


def cached(record, cache, recipe, build):
    raw = record.read_bytes()
    record_hash = hashlib.sha256(raw).hexdigest()
    key = hashlib.sha256(json.dumps(dict(record=record_hash,recipe=recipe),sort_keys=True).encode()).hexdigest()
    cache.mkdir(parents=True,exist_ok=True)
    target, meta = cache/(key+'.npz'), cache/(key+'.json')
    with (cache/(key+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if target.exists() and meta.exists():
            saved=json.loads(meta.read_text())
            if saved['key']==key and sha(target)==saved['sha256']:
                return dict(saved,cache_hit=True)
        with tempfile.TemporaryDirectory(dir=cache) as temp:
            d=Path(temp);eps=d/'episodes';eps.mkdir()
            (eps/'record.json.gz').write_bytes(raw)
            built=d/'built.npz';build(eps,built)
            with np.load(built,allow_pickle=False) as z:
                arrays={k:z[k] for k in z.files}
            for k in ('deal','family','meta','bot_names','deal_split'):
                if k not in arrays:raise ValueError('builder missing '+k)
            packed=d/'packed.npz';np.savez_compressed(packed,**arrays)
            saved=dict(key=key,record_sha256=record_hash,recipe_sha256=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest(),path=str(target.resolve()),sha256=sha(packed),
                       rows=len(arrays['deal']),families=arrays['family'].tolist())
            with packed.open('rb') as f:os.fsync(f.fileno())
            os.replace(packed,target)
            atomic(meta,(json.dumps(saved,sort_keys=True)+'\n').encode())
            return dict(saved,cache_hit=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('episodes','builder','scorer','cache','manifest'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--alias',default='')
    a=p.parse_args();recipe=identity(a.builder,a.scorer,a.alias)
    def build(eps,out):
        subprocess.run([sys.executable,str(a.builder.resolve()),'--episodes',str(eps.resolve()),'--scorer',str(a.scorer.resolve()),'--out',str(out.resolve()),'--workers','1','--policy-only','--rollout-gap','--alias',a.alias],check=True,cwd=a.builder.resolve().parents[1])
    records=sorted(a.episodes.glob('*.json.gz'))
    if not records:p.error('no episode files')
    entries=[dict(source=str(r.resolve()),**cached(r,a.cache,recipe,build)) for r in records]
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    atomic(a.manifest,(json.dumps(dict(schema=1,recipe=recipe,entries=entries,total_rows=sum(e['rows'] for e in entries)),indent=2)+'\n').encode())
    print(json.dumps(dict(records=len(entries),rows=sum(e['rows'] for e in entries),hits=sum(e['cache_hit'] for e in entries))))


if __name__=='__main__':main()
