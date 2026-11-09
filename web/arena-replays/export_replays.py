#!/usr/bin/env python3
"""Export compact root-table replays from a direct arena run or checkpoint ZIP.

Only completed root tables enter the public viewer. Audit branches and neural
diagnostics remain private to the training archive. Existing cohorts and shards
are retained, so the same destination can combine historical and current runs.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time
import zipfile

LABELS = {'A': 'Gen 3.5', 'B': 'Gen 3', 'C': 'Gen 2'}
ROLES = {'candidate': 'A', 'reference': 'B', 'original': 'C'}


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, value):
    data = json.dumps(value, separators=(',', ':'), ensure_ascii=True) + '\n'
    if path.exists() and path.read_text() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(data)
    tmp.replace(path)


def compact(episode, manifest, digest):
    assert episode['schema'] == 'direct-fork-pair-v1' and episode['status'] == 'ok'
    assert episode['manifest_identity'] == manifest['identity']
    assert episode['pair'] in ('AB', 'AC', 'BC')
    tables = []
    for swapped, side in enumerate(('focal', 'control')):
        table = episode[side]['tables'][0]
        actions = table['actions']
        assert table['status'] == 'ok' and len(actions) == 52
        assert len({a['card'] for a in actions}) == 52
        assert all(a['seat'] in 'NESW' and a['ply'] == i for i, a in enumerate(actions))
        x, y = episode['pair']
        expected = [y, x, y, x] if swapped else [x, y, x, y]
        assignments = [ROLES[x] for x in episode[side]['assignments']]
        assert assignments == expected
        board = {**episode['board'], **episode[side].get('board', {}), **table.get('board', {})}
        tables.append({'contract': table.get('contract', board['contract']),
                       'declarer': table.get('declarer', board['declarer']),
                       'auction': table.get('auction', board['auction']),
                       'assignments': assignments, 'ns_score': table['ns_score'],
                       'declarer_tricks': table['declarer_tricks'],
                       'plays': [a['seat'] + a['card'] for a in actions]})
    assert tables[0]['ns_score'] - tables[1]['ns_score'] == episode['score_difference']
    return {'id': str(episode['index']), 'index': episode['index'], 'pair': episode['pair'],
            'imps': episode['imps'], 'completed_epoch': episode['completed_epoch'],
            'family': episode['family'], 'episode_sha256': digest,
            'board': {k: episode['board'][k] for k in
                      ('id', 'hands', 'contract', 'declarer', 'dealer', 'vulnerability', 'auction')},
            'tables': tables}


def export(manifest, names, get_bytes, output, title, receipt_hash):
    assert manifest['protocol'] == 'direct-pairs-v1'
    cohort = manifest['identity']
    dest = output / 'data' / cohort
    previous = read_json(dest / 'index.json', {'records': []})
    rows = {r['index']: r for r in previous['records']}
    shards = {}
    count = 0
    for name in names:
        index = int(Path(name).name.split('.')[0])
        expected_sha = receipt_hash(index)
        if index in rows and expected_sha and rows[index]['episode_sha256'] == expected_sha:
            continue
        data = get_bytes(name)
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha and digest != expected_sha:
            raise ValueError(f'Changed committed episode {index}')
        record = compact(json.loads(gzip.decompress(data)), manifest, digest)
        assert record['index'] == index
        shard = f'boards-{index // 100:05d}.json'
        if shard not in shards:
            shards[shard] = read_json(dest / shard, {})
        shards[shard][str(index)] = record
        rows[index] = {k: record[k] for k in
                       ('id', 'index', 'pair', 'imps', 'completed_epoch', 'family', 'episode_sha256')}
        rows[index].update(shard=shard, board_id=record['board']['id'],
                           contract=record['board']['contract'], declarer=record['board']['declarer'],
                           scores=[t['ns_score'] for t in record['tables']],
                           contracts=[{'contract': t['contract'], 'declarer': t['declarer']} for t in record['tables']])
        count += 1
    for name, records in shards.items():
        write_json(dest / name, records)
    ordered = sorted(rows.values(), key=lambda r: r['index'])
    # Duplicate index snapshots are replaced, never counted again.
    assert len({r['family'] for r in ordered}) == len(ordered)
    metadata = {'schema': 'bridge-replay-index-v1', 'cohort': cohort, 'title': title,
                'labels': LABELS, 'versions': manifest['direct_versions'], 'records': ordered}
    write_json(dest / 'index.json', metadata)
    catalog = read_json(output / 'catalog.json', {'schema': 'bridge-replay-catalog-v1', 'cohorts': []})
    entry = {'id': cohort, 'title': title, 'count': len(ordered),
             'index_url': f'data/{cohort}/index.json',
             'last_completed_epoch': max((r['completed_epoch'] for r in ordered), default=None)}
    catalog['cohorts'] = [c for c in catalog['cohorts'] if c['id'] != cohort] + [entry]
    write_json(output / 'catalog.json', catalog)
    print(json.dumps({'cohort': cohort, 'records': len(ordered), 'new_or_changed': count,
                      'shards_written': len(shards)}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--run', type=Path)
    group.add_argument('--archive', type=Path)
    p.add_argument('--archive-run', default='workspace/scratch/a1f2b806f0ac/bridge-arena/runs/mixed-fork-25k/g0001-direct')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--title', default='Direct matches')
    args = p.parse_args()
    if args.run:
        manifest = json.loads((args.run / 'manifest.json').read_text())
        def receipt(index):
            path = args.run / 'receipts' / f'{index:06d}.json'
            value = read_json(path)
            if value and value['manifest_identity'] != manifest['identity']:
                raise ValueError('Receipt belongs to another cohort')
            return value['episode_sha256'] if value else None
        export(manifest, sorted((args.run / 'episodes').glob('*.json.gz')),
               lambda name: Path(name).read_bytes(), args.output, args.title, receipt)
    else:
        with zipfile.ZipFile(args.archive) as z:
            prefix = args.archive_run.rstrip('/') + '/'
            checksums = json.loads(z.read('FILE_SHA256.json'))
            def checked(name):
                data = z.read(name)
                if hashlib.sha256(data).hexdigest() != checksums[name]:
                    raise ValueError(f'Archive checksum mismatch: {name}')
                return data
            manifest = json.loads(checked(prefix + 'manifest.json'))
            def receipt(index):
                r = json.loads(checked(prefix + f'receipts/{index:06d}.json'))
                assert r['manifest_identity'] == manifest['identity']
                return r['episode_sha256']
            export(manifest, sorted(n for n in z.namelist() if
                   n.startswith(prefix + 'episodes/') and n.endswith('.json.gz')),
                   checked, args.output, args.title, receipt)


if __name__ == '__main__':
    main()
