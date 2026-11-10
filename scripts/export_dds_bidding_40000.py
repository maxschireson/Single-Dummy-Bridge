"""Export and audit the exact 40K bidding-training and 1K development deals.

Regenerates original deals and compares every DDS table to the saved SQLite
cache. No DDS solver is invoked. Only standard libraries and NumPy are needed.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_env import make_board, deal_key
from bridge_harness.core import Board


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', required=True, type=Path)
    p.add_argument('--checkpoint', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    original = json.loads((a.checkpoint/'run/manifest.json').read_text())
    state = json.loads((a.checkpoint/'run/state.json').read_text())
    if state['trained_pairs'] != 40000 or state['step'] != 314:
        raise ValueError('Not the exact reviewed 40K checkpoint')
    dataset_bytes = a.dataset.read_bytes()
    source_rows = json.loads(dataset_bytes)
    source = {r['family']:r for r in source_rows if r['source']=='dds'}
    if len(source) != 41000 or Counter(r['split'] for r in source.values()) != {'train':40000,'dev':1000}:
        raise ValueError('Wrong original DDS corpus size/splits')
    db = sqlite3.connect(f'file:{a.checkpoint / "run/dds.sqlite"}?mode=ro', uri=True)
    a.out.mkdir(parents=True, exist_ok=True)
    if list(a.out.glob('*.part*')):
        raise ValueError('Refusing to overwrite an existing export')
    manifest = dict(schema='bridge-dds-bidding-40000-v1',date='2026-11-10',
        description='Exact original 40,000 DDS bidding-training deals and separate 1,000 development deals.',
        fields=dict(index='Original zero-based index within this split',family='SHA256 canonical cyclic-seat-rotation family ID',
            hands='Four exact PBN hands, NESW order, SHDC suit order',dealer='N/E/S/W',
            vulnerability='None/NS/EW/Both',dds='5x4 declarer trick counts: rows S,H,D,C,NT; columns N,E,S,W'),
        chunk_limit_bytes=262144,
        provenance=dict(dataset_sha256=sha(dataset_bytes),original_manifest_sha256=sha((a.checkpoint/'run/manifest.json').read_bytes()),
            original_state_sha256=sha((a.checkpoint/'run/state.json').read_bytes()),
            original_config=original['config'],original_trained_pairs=40000,original_ppo_update=314,
            original_ben_sha256=original['origin_sha256'],original_dds_library_sha256=original['dds_sha256'],
            original_source_sha256=original['source_sha256'],exporter_sha256=sha(Path(__file__).read_bytes())),
        audit=dict(regenerated_deals=0,matching_cached_dds_tables=0,matching_recovered_dataset_rows=0,
                   new_dds_solves=0,split_overlap=0),splits={})
    families = set()
    for split,n,seed in [('train',40000,original['config']['seed']+100003),
                         ('dev',1000,original['config']['seed']+100003+50000000)]:
        records = []
        for i in range(n):
            board = make_board(seed, i, split)
            family = deal_key(board.hands, True)
            if family in families:
                raise ValueError('Duplicate family or train/dev overlap')
            families.add(family)
            row = source[family]
            prior = Board.from_dict(row['board'])
            if (board.hands,board.dealer,board.vulnerability) != (prior.hands,prior.dealer,prior.vulnerability) or row['split'] != split:
                raise ValueError('Recovered deal differs from original generator')
            found = db.execute('SELECT data FROM tables WHERE key=?',(deal_key(board.hands),)).fetchone()
            if found is None:
                raise ValueError('Missing original cached DDS table')
            table = json.loads(found[0])
            if table != row['dds'] or len(table)!=5 or any(len(t)!=4 for t in table):
                raise ValueError('DDS table mismatch')
            if any(type(x) is not int or not 0<=x<=13 for t in table for x in t):
                raise ValueError('Invalid trick count')
            d = board.to_dict()
            # to_dict() supplies a synthetic four-pass placeholder for unbid
            # boards. Do not export it as if it were a recorded training auction.
            records.append(dict(index=i,family=family,hands=d['hands'],dealer=d['dealer'],
                                vulnerability=d['vulnerability'],dds=table))
        raw = ''.join(json.dumps(r,separators=(',',':'))+'\n' for r in records).encode()
        packed = gzip.compress(raw,compresslevel=9,mtime=0)
        shards = []
        for offset in range(0,len(packed),manifest['chunk_limit_bytes']):
            blob = packed[offset:offset+manifest['chunk_limit_bytes']]
            name = f'{split}.jsonl.gz.part{len(shards):03d}'
            (a.out/name).write_bytes(blob)
            git_sha = hashlib.sha1(f'blob {len(blob)}\0'.encode()+blob).hexdigest()
            shards.append(dict(file=name,bytes=len(blob),sha256=sha(blob),git_blob_sha=git_sha))
        manifest['splits'][split] = dict(records=n,generator_seed=seed,gzip_bytes=len(packed),gzip_sha256=sha(packed),
                                         jsonl_bytes=len(raw),jsonl_sha256=sha(raw),chunks=shards)
        for k in ('regenerated_deals','matching_cached_dds_tables','matching_recovered_dataset_rows'):
            manifest['audit'][k] += n
        print(json.dumps(dict(split=split,records=n,gzip_bytes=len(packed),chunks=len(shards))),flush=True)
    db.close()
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':
    main()
