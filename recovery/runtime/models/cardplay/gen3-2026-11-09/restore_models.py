#!/usr/bin/env python3
"""Reassemble the Gen3 models and verify every chunk and complete artifact."""
import argparse
import hashlib
import json
from pathlib import Path


def verified(data, spec, label):
    if len(data) != spec['size_bytes']:
        raise ValueError(f'{label}: wrong byte count')
    if hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise ValueError(f'{label}: SHA256 mismatch')
    return data


def restore(root, output, repository):
    manifest = json.loads((root / 'manifest.json').read_text())
    models = []
    for model in manifest['models']:
        parts = [verified((root / part['file']).read_bytes(), part, part['file'])
                 for part in model['chunks']]
        data = verified(b''.join(parts), model, model['name'])
        models.append((model, data))
    bidder = manifest['bidding']
    bidder_path = repository / bidder['repository_path']
    verified(bidder_path.read_bytes(), bidder, 'bidding model')
    output.mkdir(parents=True, exist_ok=True)
    for model, data in models:
        dest = output / model['output']
        if dest.exists() and dest.read_bytes() != data:
            raise FileExistsError(f'Refusing to replace a different model: {dest}')
        temp = dest.with_suffix(dest.suffix + '.tmp')
        temp.write_bytes(data)
        temp.replace(dest)
        print(f"Verified {dest.name}: {len(data):,} bytes, SHA256 {model['sha256']}")
    print(f'Verified shared bidder: {bidder_path}')


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=root / 'restored')
    parser.add_argument('--repository', type=Path, default=root.parents[2])
    args = parser.parse_args()
    restore(root, args.output.resolve(), args.repository.resolve())


if __name__ == '__main__':
    main()
