"""Restore the verified pre-Gen4 tensors and optional raw PIMC game archives."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
import zipfile

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def safe(name):
    p=Path(name)
    if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe archive path')
    return p

def unpack(folder,dest):
    m=json.loads((folder/'manifest.json').read_text())
    with tempfile.TemporaryDirectory(dir=dest.parent,prefix='legacy-restore-') as temp:
        archive=Path(temp)/'archive'
        with archive.open('wb') as output:
            for part in m['chunks']:
                path=folder/safe(part['file'])
                if path.stat().st_size!=part['size_bytes'] or sha(path)!=part['sha256']:raise ValueError('Part checksum mismatch')
                with path.open('rb') as source:shutil.copyfileobj(source,output)
        if archive.stat().st_size!=m['size_bytes'] or sha(archive)!=m['sha256']:raise ValueError('Archive checksum mismatch')
        payload=Path(temp)/'payload';payload.mkdir()
        if m['archive'].endswith('.zip'):
            with zipfile.ZipFile(archive) as z:
                if z.testzip() is not None:raise ValueError('ZIP integrity failure')
                for entry in z.infolist():
                    path=safe(entry.filename)
                    if stat.S_ISLNK(entry.external_attr>>16):raise ValueError('Symbolic link in archive')
                    if entry.is_dir():(payload/path).mkdir(parents=True,exist_ok=True);continue
                    target=payload/path;target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(entry) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
        else:
            with tarfile.open(archive,'r:gz') as tar:
                for entry in tar.getmembers():
                    path=safe(entry.name)
                    if not entry.isfile():raise ValueError('Non-file archive entry')
                    target=payload/path;target.parent.mkdir(parents=True,exist_ok=True)
                    with tar.extractfile(entry) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
            for domain in ('belief','policy'):
                ds=json.loads((payload/domain/'dataset.json').read_text())
                for shard in ds['shards']:
                    if sha(payload/domain/safe(shard['file']))!=shard['sha256']:raise ValueError('Tensor shard checksum mismatch')
            if sha(payload/'sources.json')!=m['training']['source_files_sha256']:raise ValueError('Source manifest checksum mismatch')
        payload.rename(dest)
    return m

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--group',choices=['all','gen2-gen3','pimc'],default='all');a=p.parse_args()
    root=Path(__file__).resolve().parent;dest=a.output.resolve()
    if dest.exists():raise FileExistsError('Refusing to overwrite output')
    meta=json.loads((root/'legacy/manifest.json').read_text());dest.mkdir(parents=True)
    shutil.copy2(root/'legacy/manifest.json',dest/'manifest.json')
    if a.group in ('all','gen2-gen3'):
        home=dest/'gen2-gen3';home.mkdir()
        for item in meta['snapshots']:
            folder=root/safe(item['path']);unpack(folder,home/folder.name)
        shutil.copy2(root/'legacy/gen2-gen3/family-splits.json',home/'family-splits.json')
        print('Verified Gen2/Gen3 tensors:',meta['unique_families'],'families;',sum(meta['counts'][k] for k in ('policy_train','policy_validation')),'policy rows',flush=True)
    if a.group in ('all','pimc'):
        home=dest/'pimc-baseline';home.mkdir()
        for item in meta['raw_pimc_artifacts']:
            folder=root/safe(item['path']);unpack(folder,home/folder.name)
        shutil.copy2(root/'legacy/pimc-baseline/family-splits.json',home/'family-splits.json')
        print('Verified raw PIMC games:',meta['raw_pimc_counts']['games'],flush=True)

if __name__=='__main__':main()
