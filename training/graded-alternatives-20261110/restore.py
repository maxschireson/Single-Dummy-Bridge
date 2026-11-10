"""Verify every chunk and file, then rebuild the two bidder files. Standard library only.

usage: python restore.py --out /tmp/graded-alternatives
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['schema'] != 'bridge-graded-alternatives-20261110-v1':
        raise ValueError('Unknown export schema')
    for name, item in manifest['files'].items():
        data = (root / name).read_bytes()
        if len(data) != item['bytes'] or sha(data) != item['sha256']:
            raise ValueError('Changed or missing file: ' + name)
    a.out.mkdir(parents=True, exist_ok=True)
    for name, item in manifest['models'].items():
        blocks = []
        for chunk in item['chunks']:
            data = (root / chunk['file']).read_bytes()
            if len(data) != chunk['bytes'] or sha(data) != chunk['sha256']:
                raise ValueError('Changed or missing chunk: ' + chunk['file'])
            blocks.append(data)
        data = b''.join(blocks)
        if len(data) != item['bytes'] or sha(data) != item['sha256']:
            raise ValueError('Model mismatch: ' + name)
        target = a.out / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Refusing to overwrite a different file: ' + str(target))
        target.write_bytes(data)
        print('restored', target, item['sha256'])
    print('all checksums verified')


if __name__ == '__main__':
    main()
