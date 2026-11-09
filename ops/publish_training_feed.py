#!/usr/bin/env python3
"""Publish immutable, compressed training-only snapshots via a separate Git branch."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ops.publish_arena_pages import git
from ops.export_training_feed import export, pack


RESTORE = '''#!/usr/bin/env python3
"""Restore one immutable training supplement; no third-party packages needed."""
import argparse,hashlib,json,tarfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--snapshot',type=Path)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();root=Path(__file__).resolve().parent
latest=json.loads((root/'latest.json').read_text())
folder=a.snapshot or root/latest['path']
m=json.loads((folder/'manifest.json').read_text())
if a.out.exists():raise SystemExit('Output already exists; refusing overwrite')
archive=a.out.with_suffix('.tar.gz');archive.parent.mkdir(parents=True,exist_ok=True)
if archive.exists():raise SystemExit('Archive already exists; refusing overwrite')
h=hashlib.sha256();size=0
with archive.open('xb') as f:
    for part in m['chunks']:
        if Path(part['file']).name!=part['file']:raise ValueError('Unsafe chunk path')
        data=(folder/part['file']).read_bytes()
        if len(data)!=part['size_bytes'] or hashlib.sha256(data).hexdigest()!=part['sha256']:raise ValueError('Chunk verification failed')
        f.write(data);h.update(data);size+=len(data)
if size!=m['size_bytes'] or h.hexdigest()!=m['sha256']:raise ValueError('Archive verification failed')
with tarfile.open(archive,'r:gz') as tar:
    for member in tar.getmembers():
        path=Path(member.name)
        if path.is_absolute() or '..' in path.parts or not member.isfile():raise ValueError('Unsafe archive member')
    a.out.mkdir();tar.extractall(a.out,filter='data')
for domain in ('belief','policy'):
    ds=json.loads((a.out/domain/'dataset.json').read_text())
    for shard in ds['shards']:
        path=a.out/domain/shard['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=shard['sha256']:raise ValueError('Shard verification failed')
sources=a.out/'sources.json'
if hashlib.sha256(sources.read_bytes()).hexdigest()!=m['training']['source_files_sha256']:raise ValueError('Sources verification failed')
print(json.dumps(dict(restored=str(a.out),boards=m['training']['boards'],rows=m['training']['counts']),indent=2))
'''

README = '''# Gen 3.5 arena training feed

Additional full frozen deals and auctions are listed at
[cohorts/cold-fresh-24000/README.md](cohorts/cold-fresh-24000/README.md).
Those 24,000 hand sets include unplayed boards; do not count them as extra played
pairs or add their count to the incremental played-board count.

This branch contains **training-only supplements**, not a restored campaign or
complete base dataset. Collection continues in the original environment.

Restore the latest increment after checking out this branch:

    python training/restore_training.py --out /path/to/new-supplement

`training/latest.json` lists **all** immutable increments in order. The default
command restores the latest increment only; restore earlier increments with
`--snapshot training/snapshots/snapshot-0001`. Every increment is disjoint from
earlier increments in this feed, even when a straggling board finishes later.
An app receiving this feed for the first time must import every listed increment.
All binary chunks and the reassembled archive have SHA256 and byte-count checks.

The archive supplies `belief/` and `policy/` compressed NPZ tensors, their schema
and shard manifests, `sources.json` (canonical families, indices, splits, hashes),
and `provenance.json` (models and extraction rules). No logs, DDS caches, full
decision traces, model weights or optimizer states are shipped.

Merge the belief `shards` entries into the existing base belief dataset as source
`play`; retain previous BEN/bidding data and the selected parent model/Adam state.
Merge policy shards into the audited-IMP policy dataset. Copy shards under unique
increment paths and update their `file` paths; preserve hashes and all values.
Use canonical family IDs to reject duplicates against the old 3,700 and all other
training imports. Keep each supplied train/validation split and per-family weight.
The policy target `y` is the local audited chosen-minus-reference IMP contrast,
not the whole board outcome. BC boards have belief data but no A-policy labels.
Do not pool legacy/direct IMPs or report trained-on families as held-out v4 evidence.

The encoding, deterministic position selection, 128-belief-row family cap and
policy family weights match `scripts/prepare_mixed_training.py`. This feed is a
partial campaign snapshot and does not assert that the 21,300-board run finished.
Keep exporting-model hashes when training v4. A future v4 will require a distinct
manifest and evaluation cohort; do not overwrite the running Gen 3.5 weights.
'''


def _publish_snapshot(transfer, state, remote):
    from bridge_harness.improvement import read
    state.mkdir(parents=True, exist_ok=True)
    db = state/'git'
    if not db.exists():
        import subprocess
        subprocess.run(['git', 'init', '--bare', str(db)], check=True, capture_output=True)
    env = dict(os.environ, GIT_INDEX_FILE=str(state/'index'),
               GIT_AUTHOR_NAME='Bridge training feed', GIT_COMMITTER_NAME='Bridge training feed',
               GIT_AUTHOR_EMAIL='training-feed@users.noreply.github.com',
               GIT_COMMITTER_EMAIL='training-feed@users.noreply.github.com')
    ref = 'refs/heads/transfer/gen3-training-feed'
    found = git(db, 'ls-remote', remote, ref)
    parent = None
    latest = dict(format='bridge-training-feed-v1', increments=[])
    if found:
        git(db, 'fetch', '--no-tags', remote, ref)
        parent = git(db, 'rev-parse', 'FETCH_HEAD')
        git(db, 'read-tree', parent, env=env)
        files = git(db, 'ls-tree', '-r', '--name-only', parent).splitlines()
        if 'training/latest.json' in files:
            latest = json.loads(git(db, 'show', parent+':training/latest.json'))
    else:
        git(db, 'read-tree', '--empty', env=env)
    manifest = read(transfer/'manifest.json')
    name = transfer.name.removesuffix('-transfer')
    path = f'snapshots/{name}'
    existing = next((i for i in latest['increments'] if i['path'] == path), None)
    if existing:
        if existing['sha256'] != manifest['sha256']:
            raise ValueError('Immutable snapshot name already used for different data')
        return latest
    parts = [(f'training/{path}/{p.name}', p.read_bytes())
             for p in sorted(transfer.glob('*.part*'))]
    final = [(f'training/{path}/manifest.json', (transfer/'manifest.json').read_bytes()),
             ('training/restore_training.py', RESTORE.encode()), ('training/README.md', README.encode())]
    item = dict(path=path, sha256=manifest['sha256'], size_bytes=manifest['size_bytes'],
                boards=manifest['training']['boards'], rows=manifest['training']['counts'],
                manifest_identity=manifest['training']['manifest_identity'])
    latest.update(path=path, updated_epoch=time.time())
    latest['increments'].append(item)
    latest['total_exported_boards'] = sum(i['boards'] for i in latest['increments'])
    final.append(('training/latest.json', (json.dumps(latest, indent=2)+'\n').encode()))
    # Small incremental pushes accommodate proxy request limits. The manifest and
    # latest pointer appear only after every chunk has been uploaded.
    groups = [parts[i:i+2] for i in range(0, len(parts), 2)] + [final]
    for number, group in enumerate(groups, 1):
        for filename, content in group:
            blob = git(db, 'hash-object', '-w', '--stdin', data=content)
            git(db, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{filename}', env=env)
        tree = git(db, 'write-tree', env=env)
        args = ['commit-tree', tree] + (['-p', parent] if parent else [])
        commit = git(db, *args, data=f'Training {name}: upload {number}/{len(groups)}\n'.encode(), env=env)
        git(db, 'push', remote, f'{commit}:{ref}')
        parent = commit
        print(json.dumps(dict(snapshot=name, upload=number, uploads=len(groups))), flush=True)
    (state/'last-publish.json').write_text(json.dumps(latest, indent=2)+'\n')
    return latest



def publish_snapshot(transfer, state, remote):
    state.parent.mkdir(parents=True, exist_ok=True)
    with (state.parent/'.github-training-feed.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _publish_snapshot(transfer, state, remote)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--transfer', type=Path)
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--remote', required=True)
    p.add_argument('--run', type=Path)
    p.add_argument('--exports', type=Path)
    p.add_argument('--interval', type=float, default=0)
    p.add_argument('--minimum-new', type=int, default=250)
    a = p.parse_args()
    a.state.mkdir(parents=True, exist_ok=True)
    with (a.state/'.publisher.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if a.transfer:
            publish_snapshot(a.transfer.resolve(), a.state.resolve(), a.remote)
        if not a.interval:
            return
        if not a.run or not a.exports or a.interval < 300 or a.minimum_new < 1:
            p.error('Automatic feed requires --run, --exports, interval >=300 and positive minimum-new')
        while not (a.state/'STOP').exists():
            # Exclude every already exported family, including out-of-order
            # completions, rather than assuming a high-water index is complete.
            # Retry completed-but-unpublished increments before making more data.
            try:
                for snapshot in sorted(a.exports.glob('snapshot-*')):
                    if not (snapshot/'complete.json').exists():
                        continue
                    transfer = snapshot.parent/(snapshot.name+'-transfer')
                    if not (transfer/'manifest.json').exists():
                        if transfer.exists():
                            transfer.rename(transfer.with_name('failed-'+transfer.name+'-'+str(time.time_ns())))
                        pack(snapshot)
                for transfer in sorted(a.exports.glob('snapshot-*-transfer')):
                    if (transfer/'manifest.json').exists():
                        publish_snapshot(transfer, a.state, a.remote)
            except Exception as exc:
                print(json.dumps(dict(status='upload-retry-needed', error=str(exc))), flush=True)
                time.sleep(min(30, a.interval))
                continue
            source_files = sorted(f for f in a.exports.glob('snapshot-*/sources.json')
                                  if (f.parent/'complete.json').exists())
            excluded = {r['family'] for f in source_files for r in json.loads(f.read_text())}
            pending = [f for f in (a.run/'receipts').glob('*.json')
                       if json.loads(f.read_text())['family'] not in excluded]
            if len(pending) >= a.minimum_new:
                n = max([int(f.parent.name.split('-')[-1]) for f in source_files]+[0])+1
                out = a.exports/f'snapshot-{n:04}'
                if out.exists():
                    # Preserve an interrupted, incomplete export for diagnosis.
                    out.rename(out.with_name('failed-'+out.name+'-'+str(time.time_ns())))
                export(a.run, out, excluded)
                transfer = pack(out)
                publish_snapshot(transfer, a.state, a.remote)
            deadline = time.monotonic()+a.interval
            while time.monotonic() < deadline and not (a.state/'STOP').exists():
                time.sleep(min(2, max(0, deadline-time.monotonic())))


if __name__ == '__main__':
    main()
