#!/usr/bin/env python3
"""Restore one immutable training supplement; no third-party packages needed."""
import argparse,hashlib,json,tarfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--snapshot',type=Path)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();root=Path(__file__).resolve().parent
latest=json.loads((root/'latest.json').read_text())
folder=a.snapshot or root/latest['path']
m=json.loads((folder/'manifest.json').read_text())
if a.out.exists():raise SystemExit('Output already exists; refusing overwrite')
archive=a.out.with_suffix('.tar.gz');archive.parent.mkdir(parents=True,exist_ok=True)
if archive.exists():raise SystemExit('Archive already exists; refusing overwrite')
h=hashlib.sha256();size=0
with archive.open('xb') as f:
    for part in m['chunks']:
        if Path(part['file']).name!=part['file']:raise ValueError('Unsafe chunk path')
        data=(folder/part['file']).read_bytes()
        if len(data)!=part['size_bytes'] or hashlib.sha256(data).hexdigest()!=part['sha256']:raise ValueError('Chunk verification failed')
        f.write(data);h.update(data);size+=len(data)
if size!=m['size_bytes'] or h.hexdigest()!=m['sha256']:raise ValueError('Archive verification failed')
with tarfile.open(archive,'r:gz') as tar:
    for member in tar.getmembers():
        path=Path(member.name)
        if path.is_absolute() or '..' in path.parts or not member.isfile():raise ValueError('Unsafe archive member')
    a.out.mkdir();tar.extractall(a.out,filter='data')
for domain in ('belief','policy'):
    ds=json.loads((a.out/domain/'dataset.json').read_text())
    for shard in ds['shards']:
        path=a.out/domain/shard['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=shard['sha256']:raise ValueError('Shard verification failed')
sources=a.out/'sources.json'
if hashlib.sha256(sources.read_bytes()).hexdigest()!=m['training']['source_files_sha256']:raise ValueError('Sources verification failed')
print(json.dumps(dict(restored=str(a.out),boards=m['training']['boards'],rows=m['training']['counts']),indent=2))
