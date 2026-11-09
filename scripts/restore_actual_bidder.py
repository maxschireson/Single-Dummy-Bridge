"""Reassemble and verify a candidate package; does not deploy or start training."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('package',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();meta=json.loads((a.package/'manifest.json').read_text())
    a.output.mkdir(parents=True,exist_ok=True)
    for name,spec in meta['artifacts'].items():
        chunks=[]
        for part in spec['parts']:
            data=(a.package/part['path']).read_bytes()
            if len(data)!=part['size'] or hashlib.sha256(data).hexdigest()!=part['sha256']:
                raise ValueError('Corrupt chunk: '+part['path'])
            chunks.append(data)
        data=b''.join(chunks)
        if len(data)!=spec['size'] or hashlib.sha256(data).hexdigest()!=spec['sha256']:
            raise ValueError('Corrupt joined artifact: '+name)
        target=a.output/name
        if target.exists():raise ValueError('Refusing to overwrite '+str(target))
        target.write_bytes(data)
        print(name,spec['sha256'])


if __name__=='__main__':main()
