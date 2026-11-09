"""Read-only live arena snapshots in reusable chunks of at most 512 KiB.

Export never pauses or edits a collector. Only completed atomic episode files
are included. Publish chunks first and the snapshot manifest last. The same
transport supports trained models and optimizer checkpoints in the return path.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile

CHUNK_BYTES = 512 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(path):
    p = PurePosixPath(path)
    if not path or p.is_absolute() or '..' in p.parts or '\\' in path or ':' in path:
        raise ValueError('Unsafe snapshot path')
    return str(p)


def pack(files, destination, metadata):
    destination = Path(destination)
    chunks = destination / 'chunks'
    chunks.mkdir(parents=True, exist_ok=True)
    entries = []
    seen = set()
    for target, source in sorted(files.items()):
        target = relative(target)
        if target in seen:
            raise ValueError('Duplicate snapshot path')
        seen.add(target)
        source = Path(source)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f'Expected regular file: {source}')
        before = source.stat()
        full = hashlib.sha256()
        parts = []
        total = 0
        with source.open('rb') as stream:
            while data := stream.read(CHUNK_BYTES):
                key = digest(data)
                path = chunks / key
                if path.exists():
                    if digest(path.read_bytes()) != key:
                        raise ValueError('Existing chunk is corrupt')
                else:
                    with tempfile.NamedTemporaryFile(dir=chunks, delete=False) as temporary:
                        temporary.write(data)
                        temporary_path = Path(temporary.name)
                    temporary_path.replace(path)
                parts.append(dict(sha256=key, bytes=len(data)))
                full.update(data)
                total += len(data)
        after = source.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError(f'Source changed during snapshot: {source}')
        entries.append(dict(path=target, bytes=total, sha256=full.hexdigest(), chunks=parts))
    catalog = json.dumps(dict(files=entries, metadata=metadata), sort_keys=True, separators=(',', ':')).encode()
    catalog_chunks = []
    for start in range(0, len(catalog), CHUNK_BYTES):
        part = catalog[start:start + CHUNK_BYTES]
        key = digest(part)
        path = chunks / key
        if path.exists() and digest(path.read_bytes()) != key:
            raise ValueError('Corrupt catalog chunk')
        if not path.exists():
            path.write_bytes(part)
        catalog_chunks.append(dict(sha256=key, bytes=len(part)))
    manifest = dict(schema='bridge-training-exchange-v1', chunk_bytes=CHUNK_BYTES,
                    catalog_sha256=digest(catalog), catalog_chunks=catalog_chunks)
    encoded = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
    identity = digest(encoded)
    snapshots = destination / 'snapshots'
    snapshots.mkdir(exist_ok=True)
    path = snapshots / (identity + '.json')
    if not path.exists():
        path.write_bytes(encoded)
    return path


def restore(manifest_path, destination):
    manifest_path, destination = Path(manifest_path), Path(destination)
    encoded = manifest_path.read_bytes()
    if manifest_path.stem != digest(encoded):
        raise ValueError('Snapshot manifest hash mismatch')
    manifest = json.loads(encoded)
    if manifest.get('schema') != 'bridge-training-exchange-v1' or manifest.get('chunk_bytes') != CHUNK_BYTES:
        raise ValueError('Unsupported snapshot schema')
    catalog_parts = []
    for part in manifest['catalog_chunks']:
        key = part['sha256']
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Invalid catalog chunk identity')
        data = (manifest_path.parent.parent / 'chunks' / key).read_bytes()
        if len(data) != part['bytes'] or not 0 < len(data) <= CHUNK_BYTES or digest(data) != key:
            raise ValueError('Corrupt catalog chunk')
        catalog_parts.append(data)
    catalog = b''.join(catalog_parts)
    if digest(catalog) != manifest['catalog_sha256']:
        raise ValueError('Catalog hash mismatch')
    manifest.update(json.loads(catalog))
    if destination.exists():
        raise ValueError('Restore into a new directory; existing data is never overwritten')
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='training-restore-', dir=destination.parent))
    seen = set()
    try:
        for entry in manifest['files']:
            target = relative(entry['path'])
            if target in seen:
                raise ValueError('Duplicate snapshot path')
            seen.add(target)
            path = staging / target
            path.parent.mkdir(parents=True, exist_ok=True)
            full = hashlib.sha256()
            size = 0
            with path.open('xb') as stream:
                for part in entry['chunks']:
                    key = part['sha256']
                    if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
                        raise ValueError('Invalid chunk identity')
                    data = (manifest_path.parent.parent / 'chunks' / key).read_bytes()
                    if len(data) != part['bytes'] or not 0 < len(data) <= CHUNK_BYTES or digest(data) != key:
                        raise ValueError('Corrupt or missing chunk')
                    stream.write(data)
                    full.update(data)
                    size += len(data)
            if size != entry['bytes'] or full.hexdigest() != entry['sha256']:
                raise ValueError('Restored file differs from snapshot')
        (staging / 'exchange.json').write_text(json.dumps(manifest['metadata'], indent=2) + '\n')
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return manifest['metadata']


def snapshot_run(run, base=None, checkpoint=None):
    run = Path(run).resolve()
    active = json.loads((run / 'manifest.json').read_text())
    sources = [Path(p) for p in active.get('retained_training_runs', [])] + [run]
    files, runs = {}, []
    seen_runs = set()
    for source in sources:
        manifest = json.loads((source / 'manifest.json').read_text())
        identity = manifest['identity']
        if identity in seen_runs:
            continue
        seen_runs.add(identity)
        prefix = 'runs/' + identity
        files[prefix + '/manifest.json'] = source / 'manifest.json'
        indices = []
        # Capture the file list once. Later commits belong to the next snapshot.
        for path in sorted((source / 'episodes').glob('*.json.gz')):
            if path.is_symlink():
                raise ValueError('Symlinked episode')
            with gzip.open(path, 'rt') as stream:
                record = json.load(stream)
            if record.get('status') != 'ok' or record.get('manifest_identity') != identity:
                raise ValueError('Episode is not a completed record from this run')
            indices.append(record['index'])
            files[prefix + '/episodes/' + path.name] = path
        if len(indices) != len(set(indices)):
            raise ValueError('Duplicate completed index')
        runs.append(dict(identity=identity, path=prefix, indices=indices, boards=len(indices)))
    for spec in active['bots'].values():
        for component in ('belief', 'policy', 'bidding'):
            if not spec.get(component):
                continue
            path = run / spec[component]
            expected = spec['artifact_sha256'][component]
            if digest(path.read_bytes()) != expected:
                raise ValueError('Parent model hash mismatch')
            files['parents/' + relative(spec[component])] = path
    if base:
        base = Path(base)
        dataset = json.loads((base / 'dataset.json').read_text())
        files['base-belief/dataset.json'] = base / 'dataset.json'
        for shard in dataset['shards']:
            path = base / relative(shard['file'])
            if digest(path.read_bytes()) != shard['sha256']:
                raise ValueError('Base shard changed')
            files['base-belief/' + relative(shard['file'])] = path
    if checkpoint:
        checkpoint = Path(checkpoint)
        parts = sorted(checkpoint.parent.glob(checkpoint.name + '.*'))
        if not any(p.suffix == '.index' for p in parts) or not any('.data-' in p.name for p in parts):
            raise ValueError('Selected model/optimizer checkpoint is incomplete')
        for path in parts:
            files['belief-checkpoint/' + path.name] = path
    metadata = dict(kind='live-arena-training-snapshot', active_identity=active['identity'],
                    runs=runs, parent_bot=active['candidate'], parent_spec=active['bots'][active['candidate']],
                    checkpoint='belief-checkpoint/' + Path(checkpoint).name if checkpoint else None,
                    base_belief_included=bool(base), created_utc=datetime.now(timezone.utc).isoformat(),
                    source_sha256=active.get('source_sha256'),
                    purpose='Train elsewhere; retain canonical splits and verify full replays before fitting. No collector mutation.')
    return files, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export')
    export.add_argument('--run', type=Path, required=True)
    export.add_argument('--base-belief-data', type=Path)
    export.add_argument('--belief-checkpoint', type=Path)
    export.add_argument('--out', type=Path, required=True)
    unpack = sub.add_parser('restore')
    unpack.add_argument('--manifest', type=Path, required=True)
    unpack.add_argument('--out', type=Path, required=True)
    package = sub.add_parser('pack')
    package.add_argument('--spec', type=Path, required=True, help='JSON containing explicit files mapping and metadata')
    package.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'restore':
        print(json.dumps(restore(args.manifest, args.out)))
    elif args.command == 'export':
        files, metadata = snapshot_run(args.run, args.base_belief_data, args.belief_checkpoint)
        print(pack(files, args.out, metadata))
    else:
        spec = json.loads(args.spec.read_text())
        print(pack(spec['files'], args.out, spec['metadata']))


if __name__ == '__main__':
    main()
