"""Restore the complete policy-clean play snapshot and verify every file."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def restore(root,output):
    m=json.loads((root/'manifest.json').read_text())
    if output.exists():raise FileExistsError('Refusing to overwrite output')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='policy-restore-') as temp:
        archive=Path(temp)/'records.tar.gz'
        with archive.open('wb') as out:
            for part in m['chunks']:
                if Path(part['file']).name!=part['file']:raise ValueError('Unsafe part path')
                path=root/part['file']
                if path.stat().st_size!=part['size_bytes'] or sha(path)!=part['sha256']:raise ValueError('Part verification failed')
                with path.open('rb') as source:shutil.copyfileobj(source,out)
        if archive.stat().st_size!=m['size_bytes'] or sha(archive)!=m['sha256']:raise ValueError('Archive verification failed')
        unpacked=Path(temp)/'data';unpacked.mkdir()
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar.getmembers():
                path=Path(member.name)
                if path.is_absolute() or '..' in path.parts or not member.isfile():raise ValueError('Unsafe archive entry')
                target=unpacked/path;target.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(member) as source,target.open('wb') as dest:shutil.copyfileobj(source,dest)
        hashes=json.loads((unpacked/'FILE_SHA256.json').read_text())
        for name,expected in hashes.items():
            path=Path(name)
            if path.is_absolute() or '..' in path.parts or sha(unpacked/path)!=expected:raise ValueError('Payload verification failed')
        unpacked.rename(output)
    summary=json.loads((output/'export.json').read_text())
    print(json.dumps(dict(output=str(output),games=summary['counts']['games'],families=summary['unique_families'],actions_with_pimc=summary['counts']['actions_with_pimc'],status='all-checksums-verified'),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    restore(Path(__file__).resolve().parent,a.output.resolve())
