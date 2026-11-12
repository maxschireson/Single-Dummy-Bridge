#!/usr/bin/env python3
"""Split a model file into 512 KB parts with a manifest and a restore script, in the layout the other model folders use.

  python scripts/chunk_model.py FILE --description "..." [--status "..."] [--extra key=value ...]

Writes next to FILE: FILE.partNNN, manifest.json and restore_model.py. FILE itself stays out of git (see .gitignore
rules for model folders); `python restore_model.py` in that folder rebuilds it and verifies every hash.
"""
import argparse
import hashlib
import json
from pathlib import Path

PART = 512 * 1024
RESTORE = '''"""Verify chunk hashes and reconstruct the model file(s) listed in manifest.json."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    for spec in manifest['files']:
        output = ROOT / spec['output']
        temporary = output.with_suffix(output.suffix + '.tmp')
        with temporary.open('wb') as destination:
            for part in spec['parts']:
                source = ROOT / part['file']
                if source.stat().st_size != part['size_bytes'] or sha(source) != part['sha256']:
                    raise ValueError('Part verification failed: ' + part['file'])
                destination.write(source.read_bytes())
        if temporary.stat().st_size != spec['size_bytes'] or sha(temporary) != spec['sha256']:
            raise ValueError('Reconstructed file verification failed: ' + spec['output'])
        temporary.replace(output)
        print('restored', output.name)


if __name__ == '__main__':
    main()
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file', type=Path)
    ap.add_argument('--description', required=True)
    ap.add_argument('--status', default='research prototype: no arena bot uses it')
    ap.add_argument('--schema', default='chunked-model-artifact-v1')
    ap.add_argument('--extra', nargs='*', default=[], help='key=value pairs added to the manifest')
    args = ap.parse_args()
    data = args.file.read_bytes()
    folder = args.file.parent
    for old in folder.glob(args.file.name + '.part*'):
        old.unlink()
    parts = []
    for k in range(0, len(data), PART):
        chunk = data[k:k + PART]
        name = f'{args.file.name}.part{k // PART:03d}'
        (folder / name).write_bytes(chunk)
        parts.append(dict(file=name, size_bytes=len(chunk), sha256=hashlib.sha256(chunk).hexdigest()))
    manifest = dict(schema=args.schema, status=args.status, description=args.description)
    manifest.update(dict(item.split('=', 1) for item in args.extra))
    manifest['files'] = [dict(output=args.file.name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), parts=parts)]
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    (folder / 'restore_model.py').write_text(RESTORE)
    print(f'{args.file.name}: {len(data)} bytes in {len(parts)} parts')


if __name__ == '__main__':
    main()
