"""Verify the export and restore train.jsonl and dev.jsonl, without dependencies."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate(record, index, split, seen):
    if record['index'] != index or record['dealer'] not in 'NESW' or record['vulnerability'] not in ('None','NS','EW','Both'):
        raise ValueError('Invalid index or deal metadata')
    hands = []
    for text in record['hands']:
        suits = text.split('.')
        if len(suits)!=4:
            raise ValueError('Invalid PBN hand')
        hand = tuple(sorted(13*s+'23456789TJQKA'.index(c) for s,suit in enumerate(suits) for c in suit))
        if len(hand)!=13:
            raise ValueError('Hand does not contain 13 cards')
        hands.append(hand)
    if len(hands)!=4 or sorted(c for h in hands for c in h)!=list(range(52)):
        raise ValueError('Invalid full deal')
    hands = tuple(hands)
    canonical = min(hands[i:]+hands[:i] for i in range(4))
    family = sha(bytes(c for h in canonical for c in h))
    if family != record['family'] or family in seen:
        raise ValueError('Duplicate or invalid canonical family')
    seen.add(family)
    bucket = int(family[:8],16)%100
    if not (bucket<80 if split=='train' else 80<=bucket<90):
        raise ValueError('Original family split changed')
    table = record['dds']
    if len(table)!=5 or any(len(row)!=4 for row in table) or any(type(t) is not int or not 0<=t<=13 for row in table for t in row):
        raise ValueError('Invalid DDS table')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root/'manifest.json').read_text())
    if manifest['schema']!='bridge-dds-bidding-40000-v1':
        raise ValueError('Unknown export schema')
    seen = set(); validated = {}
    for split in ('train','dev'):
        item = manifest['splits'][split]
        blocks = []
        for chunk in item['chunks']:
            data = (root/chunk['file']).read_bytes()
            if len(data)!=chunk['bytes'] or sha(data)!=chunk['sha256']:
                raise ValueError('Changed/missing chunk: '+chunk['file'])
            blocks.append(data)
        packed = b''.join(blocks)
        if len(packed)!=item['gzip_bytes'] or sha(packed)!=item['gzip_sha256']:
            raise ValueError('Compressed corpus mismatch')
        raw = gzip.decompress(packed)
        if len(raw)!=item['jsonl_bytes'] or sha(raw)!=item['jsonl_sha256']:
            raise ValueError('Uncompressed corpus mismatch')
        lines = raw.splitlines()
        if len(lines)!=item['records'] or len(lines)!=(40000 if split=='train' else 1000):
            raise ValueError('Wrong record count')
        for i,line in enumerate(lines):
            validate(json.loads(line),i,split,seen)
        validated[split] = raw
    a.out.mkdir(parents=True,exist_ok=True)
    for split,raw in validated.items():
        destination = a.out/(split+'.jsonl')
        if destination.exists() and destination.read_bytes()!=raw:
            raise ValueError('Refusing to replace a different file: '+str(destination))
    for split,raw in validated.items():
        (a.out/(split+'.jsonl')).write_bytes(raw)
    print(json.dumps(dict(train=40000,dev=1000,unique_families=len(seen),checksums='verified',out=str(a.out.resolve())),indent=2))


if __name__=='__main__':
    main()
