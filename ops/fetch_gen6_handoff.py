"""Download the pinned raw Gen5 manifests, episodes and receipts for Gen6.

Uses Git sparse checkout to fetch records in bulk, then verifies every file
against the handoff's SHA256 inventory. Requires Python 3 and Git only.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(path, expected):
    if sha(path) != expected:
        raise ValueError(f'SHA256 mismatch: {path}')


def verify(root, source, rows):
    check(root / 'manifest.json', source['manifest_sha256'])
    check(root / 'corpus.jsonl', source['corpus_sha256'])
    expected = {Path(row['episode']).name for row in rows}
    actual = {p.name for p in (root / 'episodes').glob('*.json.gz')}
    if actual != expected:
        raise ValueError(f'Episode set differs from frozen inventory: {source["source_id"]}')
    for row in rows:
        check(root / 'episodes' / Path(row['episode']).name, row['episode_sha256'])
        check(root / 'receipts' / Path(row['receipt']).name, row['receipt_sha256'])


def fetch(manifest_path, out, phase):
    manifest = json.loads(manifest_path.read_text())
    if manifest['schema'] != 'gen6-arena-handoff-v1':
        raise ValueError('Unsupported handoff schema')
    out.mkdir(parents=True, exist_ok=True)
    sources = [s for s in manifest['sources'] if phase is None or s['source_id'] == phase]
    if not sources:
        raise ValueError(f'Unknown phase: {phase}')
    for source in sources:
        inventory = manifest_path.parent / source['inventory']
        check(inventory, source['inventory_sha256'])
        rows = [json.loads(line) for line in gzip.decompress(inventory.read_bytes()).splitlines()]
        if len(rows) != source['counts']['records']:
            raise ValueError('Inventory count mismatch')
        target = out / source['source_id']
        if target.exists():
            verify(target, source, rows)
            print(f'{source["source_id"]}: existing {len(rows)} records verified', flush=True)
            continue
        temporary = Path(tempfile.mkdtemp(prefix='.' + source['source_id'] + '-', dir=out))
        def git(*args):
            subprocess.run(['git', '-C', str(temporary), *args], check=True)
        print(f'{source["source_id"]}: downloading commit {source["commit"]}', flush=True)
        try:
            git('init', '-q')
            git('remote', 'add', 'origin', f'https://github.com/{manifest["repository"]}.git')
            git('sparse-checkout', 'init', '--no-cone')
            git('sparse-checkout', 'set', '--no-cone', '/recovery/manifest.json',
                '/recovery/corpus.jsonl', '/recovery/episodes/', '/recovery/receipts/')
            git('fetch', '--depth=1', '--filter=blob:none', 'origin', source['commit'])
            git('checkout', '--detach', 'FETCH_HEAD')
            verify(temporary / 'recovery', source, rows)
            os.replace(temporary / 'recovery', target)
        finally:
            shutil.rmtree(temporary)
        print(f'{source["source_id"]}: {len(rows)} complete raw records verified', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'reports/gen6-handoff-20261110/manifest.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--phase', help='Optional single source_id from the handoff manifest')
    args = parser.parse_args()
    fetch(args.manifest, args.out, args.phase)
