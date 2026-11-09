"""Restore and verify the standby worker; never starts collection."""
import argparse,hashlib,json,tarfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=Path(__file__).resolve().parent;m=json.loads((root/'manifest.json').read_text())
if a.output.exists():raise SystemExit('Output exists; refusing overwrite')
archive=a.output.with_suffix('.tar.gz');archive.parent.mkdir(parents=True,exist_ok=True)
if archive.exists():raise SystemExit('Archive already exists; refusing overwrite')
h=hashlib.sha256();n=0
with archive.open('xb') as out:
    for part in m['chunks']:
        if Path(part['file']).name!=part['file']:raise ValueError('Unsafe chunk name')
        b=(root/part['file']).read_bytes()
        if len(b)!=part['size_bytes'] or hashlib.sha256(b).hexdigest()!=part['sha256']:raise ValueError('Chunk hash/size mismatch')
        out.write(b);h.update(b);n+=len(b)
if n!=m['size_bytes'] or h.hexdigest()!=m['sha256']:raise ValueError('Archive verification failed')
with tarfile.open(archive,'r:gz') as tar:
    for member in tar.getmembers():
        name=Path(member.name)
        if name.is_absolute() or '..' in name.parts or not member.isfile():raise ValueError('Unsafe archive member')
    a.output.mkdir();tar.extractall(a.output,filter='data')
assert (a.output/'arena-v4/g0004/STOP').exists()
print('Verified standby restored to',a.output,'— collection remains disabled')
