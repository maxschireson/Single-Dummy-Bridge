"""Archive new complete DDS replay records, preserving exact bytes and hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--previous',type=Path,action='append',default=[])
    a=p.parse_args()
    if a.out.exists():raise ValueError('Refusing to overwrite archive')
    previous={}
    for path in a.previous:
        with zipfile.ZipFile(path) as z:
            for row in json.loads(z.read('dds-capture-index.json'))['files']:
                previous[row['file']]=row['sha256']
    files=[]
    for path in sorted((a.run/'dds-expensive').glob('*.json.gz')):
        checksum=hashlib.sha256(path.read_bytes()).hexdigest()
        if path.name in previous:
            if previous[path.name]!=checksum:raise ValueError('Changed immutable capture')
        else:files.append((path,checksum))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    index=dict(schema='dds-expensive-archive-v1',created_epoch=time.time(),
               run=str(a.run.resolve()),previous_archives=[str(p) for p in a.previous],
               files=[dict(file=p.name,sha256=h) for p,h in files])
    with zipfile.ZipFile(a.out,'x',compression=zipfile.ZIP_STORED) as z:
        z.write(a.run/'manifest.json','run-manifest.json')
        for path,_ in files:z.write(path,'dds-expensive/'+path.name)
        z.writestr('dds-capture-index.json',json.dumps(index,separators=(',',':')))
    with zipfile.ZipFile(a.out) as z:
        assert z.testzip() is None
    print(json.dumps(dict(path=str(a.out.resolve()),new_records=len(files),bytes=a.out.stat().st_size)))

if __name__=='__main__':main()
